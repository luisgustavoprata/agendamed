"""AgendaMed (Clínica Vida) — API REST e interface para agendamento de consultas médicas.

Este arquivo cria a aplicação Flask (`create_app`): lê a configuração, liga o banco,
registra as rotas da API e a página, e aplica os cabeçalhos de segurança em todas as
respostas.

Mapa do pacote `agendamed/`, do mais básico ao mais específico:

    config.py                 configurações lidas das variáveis de ambiente
    db.py                     conexão com o banco SQLite e ajustes de bancos antigos
    schema.sql                tabelas da agenda (usuários, médicos, pacientes, consultas)
    schema_gestao.sql         tabelas da gestão (prontuário, financeiro, estoque...)
    cli.py                    comandos de terminal (flask init-db, flask seed)
    errors.py                 erros do sistema e como viram respostas JSON
    security.py               senhas (hash) e tokens de acesso
    ratelimit.py              limite de tentativas de login (contra força bruta)
    validators.py             CPF e e-mail
    models.py                 entidades: usuário, médico, paciente, consulta
    schemas.py                formato dos dados que a API recebe (validação)
    repositories/             todo o SQL das entidades acima
    services/                 regras de agenda e casos de uso das consultas
    gestao/                   prontuário, prescrições, financeiro, estoque e relatórios
    accounts.py               acessos da equipe vindos das variáveis de ambiente
    seed.py, seed_gestao.py   dados de demonstração
    openapi.py                documentação da API (/docs)
    routes/                   os endereços da API, um arquivo por assunto
    static/                   a interface web (HTML, CSS e JavaScript)

Caminho de uma requisição: rota (routes/) → serviço ou repositório → banco. A resposta
volta como JSON, e a interface em static/ só conversa com o servidor por essa API.
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, request
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.routing import IntegerConverter

from agendamed import cli, db, errors
from agendamed.accounts import configured_accounts, ensure_accounts
from agendamed.config import DEFAULT_SECRET_KEY, Config
from agendamed.ratelimit import LoginRateLimiter
from agendamed.routes import appointments, auth, docs, doctors, gestao, patients
from agendamed.schemas import MAX_ID

__version__ = "1.2.0"

# Política de segurança de conteúdo: scripts, estilos e fontes só do próprio site, e a
# página não pode ser exibida dentro de iframes de outros sites. A página /docs define a
# sua própria política, que libera o CDN do Swagger UI.
CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "font-src 'self'",
        "img-src 'self' data:",
        "connect-src 'self'",
        "base-uri 'none'",
        "form-action 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
    ]
)

# Recursos do navegador que o site nunca usa ficam bloqueados.
PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=()"

# Limite do corpo das requisições: a API só recebe JSON pequeno.
MAX_CONTENT_LENGTH = 64 * 1024


def clinic_clock(timezone: str):
    """Relógio que devolve o horário local da clínica, sem fuso (como os dados do banco)."""
    zone = ZoneInfo(timezone)
    return lambda: datetime.now(zone).replace(tzinfo=None)


# Valor de exemplo do .env.example: parece longo, mas também é público.
EXAMPLE_SECRET_KEY = "troque-por-uma-chave-longa-e-aleatoria"


def _check_secret_key(app: Flask) -> None:
    """Com a chave padrão (que está no código) qualquer pessoa forjaria um login válido.

    Em desenvolvimento (`flask run --debug`) e nos testes, só avisa. Fora disso, não sobe.
    """
    key = app.config["SECRET_KEY"]
    weak = key in (DEFAULT_SECRET_KEY, EXAMPLE_SECRET_KEY) or len(key) < 32
    if not weak or app.config.get("TESTING"):
        return
    if app.debug or os.environ.get("FLASK_DEBUG") == "1":
        app.logger.warning("SECRET_KEY padrão ou curta. Defina SECRET_KEY antes de publicar.")
        return
    raise RuntimeError(
        "SECRET_KEY ausente, padrão ou com menos de 32 caracteres. Gere uma com: "
        'python -c "import secrets; print(secrets.token_urlsafe(48))"'
    )


class BoundedIntConverter(IntegerConverter):
    """`<int:id>` com teto: ids gigantes viram 404 em vez de estourar o banco (erro 500)."""

    def __init__(self, map, *args, **kwargs):
        """Usa o teto MAX_ID quando a rota não informa outro máximo."""
        kwargs.setdefault("max", MAX_ID)
        super().__init__(map, *args, **kwargs)


def create_app(config: dict | None = None) -> Flask:
    """Cria e configura a aplicação (padrão *application factory*).

    `config` sobrescreve as configurações (os testes usam isso para trocar o banco e o
    relógio). O servidor (gunicorn) chama `create_app()` sem nada.
    """
    # 1. Configuração: valores de config.py, o relógio da clínica e o que vier em `config`.
    app = Flask(__name__)
    app.url_map.converters["int"] = BoundedIntConverter
    app.config.from_object(Config)
    app.config["CLOCK"] = clinic_clock(app.config["CLINIC_TIMEZONE"])
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
    if config:
        app.config.update(config)

    # JSON das respostas: campos na ordem em que foram escritos e acentos sem escape.
    app.json.sort_keys = False
    app.json.ensure_ascii = False

    # Atrás do proxy do Render, o IP e o HTTPS verdadeiros vêm nos cabeçalhos X-Forwarded-*.
    if app.config["TRUST_PROXY"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # 2. Limites de tentativas de login (contra força bruta), guardados em app.extensions.
    app.extensions["login_limiter"] = LoginRateLimiter(
        app.config["LOGIN_MAX_ATTEMPTS"], app.config["LOGIN_WINDOW_SECONDS"]
    )
    # Segundo limite, só por IP: impede que um único endereço teste muitos e-mails
    # diferentes (cada tentativa custa um cálculo de PBKDF2 caro para o servidor).
    app.extensions["login_ip_limiter"] = LoginRateLimiter(
        app.config["LOGIN_IP_MAX_ATTEMPTS"], app.config["LOGIN_WINDOW_SECONDS"]
    )

    # 3. Banco, comandos de terminal e tratamento de erros.
    db.init_app(app)
    cli.init_app(app)
    errors.register_error_handlers(app)

    # 4. Rotas da API (cada blueprint é um arquivo de agendamed/routes/).
    for blueprint in (auth.bp, doctors.bp, patients.bp, appointments.bp, docs.bp, gestao.bp):
        app.register_blueprint(blueprint)

    # 5. A página da interface.
    @app.get("/")
    def web_app():
        """Interface web (HTML, CSS e JS estáticos que consomem a própria API)."""
        return app.send_static_file("index.html")

    @app.get("/health")
    def health():
        """GET /health — o servidor está no ar? Também informa os modos da instalação."""
        # "demo" avisa a interface que existe uma conta de demonstração pronta, e
        # "signup" se a aba de criar conta deve aparecer.
        return {
            "status": "ok",
            "version": __version__,
            "demo": app.config["SEED_DEMO_DATA"],
            "signup": app.config["ALLOW_SIGNUP"],
        }

    # 6. Cabeçalhos de segurança, colocados em todas as respostas.
    @app.after_request
    def security_headers(response):
        """Protege as páginas no navegador (setdefault: uma rota pode definir os seus)."""
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if request.is_secure:
            # Navegador passa a usar só HTTPS neste domínio por um ano.
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        if request.path.startswith(
            (
                "/auth",
                "/doctors",
                "/patients",
                "/appointments",
                "/prescriptions",
                "/finance",
                "/stock",
                "/reports",
                "/procedures",
                "/health-plans",
            )
        ):
            # Dados de pacientes não devem ficar guardados em cache de navegador ou proxy.
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    # 7. Banco pronto: tabelas, acessos da equipe e dados de demonstração (se pedidos).
    with app.app_context():
        db.init_db()
        # Contas da equipe (ADMIN_*, DOCTOR_*, SECRETARY_*), criadas ou atualizadas a cada início.
        if "STAFF_ACCOUNTS" not in app.config:
            app.config["STAFF_ACCOUNTS"] = configured_accounts()
        ensure_accounts(db.get_db(), app.config["STAFF_ACCOUNTS"])
        if app.config["SEED_DEMO_DATA"]:
            from agendamed.seed import seed

            # Com contas da equipe configuradas, os exemplos entram sem a conta pública de
            # demonstração (admin@agendamed.dev): só a equipe entra.
            seed(db.get_db(), demo_login=not app.config["STAFF_ACCOUNTS"])

    # 8. Por último: não sobe em produção com a SECRET_KEY de exemplo ou curta.
    _check_secret_key(app)

    return app
