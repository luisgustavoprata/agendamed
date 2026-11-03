"""AgendaMed — API REST para agendamento de consultas médicas."""

from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask, request
from werkzeug.middleware.proxy_fix import ProxyFix

from agendamed import db, errors
from agendamed.config import DEFAULT_SECRET_KEY, Config
from agendamed.ratelimit import LoginRateLimiter
from agendamed.routes import appointments, auth, docs, doctors, patients

__version__ = "1.2.0"

# Política de segurança de conteúdo: scripts, estilos e fontes só do próprio site, e a
# página não pode ser exibida dentro de iframes de outros sites. A página /docs define a
# sua própria política, que libera o CDN do Swagger UI.
CONTENT_SECURITY_POLICY = "; ".join([
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
])

# Recursos do navegador que o site nunca usa ficam bloqueados.
PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=()"

# Limite do corpo das requisições: a API só recebe JSON pequeno.
MAX_CONTENT_LENGTH = 64 * 1024


def clinic_clock(timezone: str):
    """Relógio que devolve o horário local da clínica, sem fuso (como os dados do banco)."""
    zone = ZoneInfo(timezone)
    return lambda: datetime.now(zone).replace(tzinfo=None)


def create_app(config: dict | None = None) -> Flask:
    """Cria e configura a aplicação (padrão *application factory*)."""
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["CLOCK"] = clinic_clock(app.config["CLINIC_TIMEZONE"])
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
    if config:
        app.config.update(config)

    app.json.sort_keys = False
    app.json.ensure_ascii = False

    if app.config["TRUST_PROXY"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    app.extensions["login_limiter"] = LoginRateLimiter(
        app.config["LOGIN_MAX_ATTEMPTS"], app.config["LOGIN_WINDOW_SECONDS"]
    )
    # Segundo limite, só por IP: impede que um único endereço teste muitos e-mails
    # diferentes (cada tentativa custa um cálculo de PBKDF2 caro para o servidor).
    app.extensions["login_ip_limiter"] = LoginRateLimiter(
        app.config["LOGIN_IP_MAX_ATTEMPTS"], app.config["LOGIN_WINDOW_SECONDS"]
    )

    db.init_app(app)
    errors.register_error_handlers(app)

    for blueprint in (auth.bp, doctors.bp, patients.bp, appointments.bp, docs.bp):
        app.register_blueprint(blueprint)

    @app.get("/")
    def web_app():
        """Interface web (HTML, CSS e JS estáticos que consomem a própria API)."""
        return app.send_static_file("index.html")

    @app.get("/health")
    def health():
        # "demo" avisa a interface que existe uma conta de demonstração pronta, e
        # "signup" se a aba de criar conta deve aparecer.
        return {
            "status": "ok",
            "version": __version__,
            "demo": app.config["SEED_DEMO_DATA"],
            "signup": app.config["ALLOW_SIGNUP"],
        }

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if request.is_secure:
            # Navegador passa a usar só HTTPS neste domínio por um ano.
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        if request.path.startswith(("/auth", "/doctors", "/patients", "/appointments")):
            # Dados de pacientes não devem ficar guardados em cache de navegador ou proxy.
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    with app.app_context():
        db.init_db()
        if app.config["SEED_DEMO_DATA"]:
            from agendamed.seed import seed

            seed(db.get_db())

    if not app.config.get("TESTING") and app.config["SECRET_KEY"] == DEFAULT_SECRET_KEY:
        app.logger.warning("SECRET_KEY padrão em uso. Defina a variável de ambiente SECRET_KEY.")

    return app
