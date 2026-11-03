from flask import Blueprint, current_app

from agendamed.openapi import build_spec

bp = Blueprint("docs", __name__)

SWAGGER_VERSION = "5.17.14"
# Hashes SRI: o navegador recusa os arquivos do CDN se o conteúdo for alterado.
SWAGGER_CSS_SRI = "sha384-wxLW6kwyHktdDGr6Pv1zgm/VGJh99lfUbzSn6HNHBENZlCN7W602k9VkGdxuFvPn"
SWAGGER_JS_SRI = "sha384-wmyclcVGX/WhUkdkATwhaK1X1JtiNrr2EoYJ+diV3vj4v6OC5yCeSu+yW13SYJep"

# Só a página da documentação libera o CDN do Swagger UI; o restante do site não.
DOCS_CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self' https://cdn.jsdelivr.net",
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
    "img-src 'self' data: https://cdn.jsdelivr.net",
    "connect-src 'self'",
    "frame-ancestors 'none'",
])

SWAGGER_PAGE = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Documentação da API | AgendaMed</title>
  <link rel="icon" href="/static/icon.svg" type="image/svg+xml">
  <link rel="stylesheet"
        href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@{SWAGGER_VERSION}/swagger-ui.css"
        integrity="{SWAGGER_CSS_SRI}" crossorigin="anonymous">
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@{SWAGGER_VERSION}/swagger-ui-bundle.js"
          integrity="{SWAGGER_JS_SRI}" crossorigin="anonymous">
  </script>
  <script src="/static/docs.js"></script>
</body>
</html>
"""


@bp.get("/openapi.json")
def openapi_spec():
    from agendamed import __version__

    return build_spec(__version__)


@bp.get("/docs")
def swagger_ui():
    response = current_app.response_class(SWAGGER_PAGE, mimetype="text/html")
    response.headers["Content-Security-Policy"] = DOCS_CONTENT_SECURITY_POLICY
    return response
