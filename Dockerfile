FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/data/agendamed.db \
    PORT=8000

WORKDIR /app

# Usuário sem privilégios de root para rodar a aplicação.
RUN useradd --create-home appuser && mkdir /data && chown appuser /data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agendamed ./agendamed

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s \
    CMD python -c "import os, urllib.request as u; u.urlopen('http://localhost:%s/health' % os.environ['PORT'])"

# A porta vem da variável PORT (o Render define a sua). --preload cria a aplicação uma
# única vez antes de iniciar os workers, então o banco é criado e populado só uma vez.
CMD ["sh", "-c", "exec gunicorn --preload --bind 0.0.0.0:${PORT} --workers ${WEB_CONCURRENCY:-2} --access-logfile - 'agendamed:create_app()'"]
