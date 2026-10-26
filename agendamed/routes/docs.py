from flask import Blueprint, current_app

from agendamed.openapi import build_spec

bp = Blueprint("docs", __name__)

SWAGGER_VERSION = "5.17.14"

SWAGGER_PAGE = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Documentação da API | AgendaMed</title>
  <link rel="icon" href="/static/icon.svg" type="image/svg+xml">
  <link rel="stylesheet"
        href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@{SWAGGER_VERSION}/swagger-ui.css">
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@{SWAGGER_VERSION}/swagger-ui-bundle.js">
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
    return current_app.response_class(SWAGGER_PAGE, mimetype="text/html")
