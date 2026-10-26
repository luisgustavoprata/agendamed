"""AgendaMed — API REST para agendamento de consultas médicas."""

from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from agendamed import db, errors
from agendamed.config import DEFAULT_SECRET_KEY, Config
from agendamed.ratelimit import LoginRateLimiter
from agendamed.routes import appointments, auth, docs, doctors, patients

__version__ = "1.2.0"

# Política de segurança de conteúdo: só carrega scripts do próprio site e do CDN do
# Swagger UI, e impede que a página seja exibida dentro de iframes de outros sites.
CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self' https://cdn.jsdelivr.net",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: https://cdn.jsdelivr.net",
    "connect-src 'self'",
    "frame-ancestors 'none'",
])


def clinic_clock(timezone: str):
    """Relógio que devolve o horário local da clínica, sem fuso (como os dados do banco)."""
    zone = ZoneInfo(timezone)
    return lambda: datetime.now(zone).replace(tzinfo=None)


def create_app(config: dict | None = None) -> Flask:
    """Cria e configura a aplicação (padrão *application factory*)."""
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["CLOCK"] = clinic_clock(app.config["CLINIC_TIMEZONE"])
    if config:
        app.config.update(config)

    app.json.sort_keys = False
    app.json.ensure_ascii = False

    if app.config["TRUST_PROXY"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    app.extensions["login_limiter"] = LoginRateLimiter(
        app.config["LOGIN_MAX_ATTEMPTS"], app.config["LOGIN_WINDOW_SECONDS"]
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
        # "demo" avisa a interface que existe uma conta de demonstração pronta.
        return {"status": "ok", "version": __version__, "demo": app.config["SEED_DEMO_DATA"]}

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response

    with app.app_context():
        db.init_db()
        if app.config["SEED_DEMO_DATA"]:
            from agendamed.seed import seed

            seed(db.get_db())

    if not app.config.get("TESTING") and app.config["SECRET_KEY"] == DEFAULT_SECRET_KEY:
        app.logger.warning("SECRET_KEY padrão em uso. Defina a variável de ambiente SECRET_KEY.")

    return app
