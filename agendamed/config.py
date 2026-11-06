"""Configurações lidas de variáveis de ambiente, com padrões para desenvolvimento."""

import os

DEFAULT_SECRET_KEY = "dev-chave-insegura-troque-antes-de-ir-para-producao"


def env_bool(name: str, default: bool = False) -> bool:
    """Lê uma variável de ambiente como sim/não.

    Aceita "1", "true", "yes" e "sim" (sem diferença de maiúsculas) como verdadeiro; qualquer outro
    valor é falso. Sem a variável, vale o `default`.
    """
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "sim"}


class Config:
    """Configurações do sistema, lidas das variáveis de ambiente.

    Cada atributo em MAIÚSCULAS vira `app.config[...]` no Flask. O valor depois de
    `os.environ.get(...)` é o padrão usado quando a variável não existe, pensado para o
    desenvolvimento no computador. Em produção, os valores vêm do Render.
    """

    SECRET_KEY = os.environ.get("SECRET_KEY", DEFAULT_SECRET_KEY)
    DATABASE = os.environ.get("DATABASE_PATH", "agendamed.db")
    TOKEN_EXPIRES_MINUTES = int(os.environ.get("TOKEN_EXPIRES_MINUTES", "60"))
    # Recomendação OWASP (2023) para PBKDF2-HMAC-SHA256. O número de iterações fica gravado
    # em cada hash, então pode ser alterado sem invalidar as senhas já cadastradas.
    PASSWORD_HASH_ITERATIONS = int(os.environ.get("PASSWORD_HASH_ITERATIONS", "600000"))

    # Fuso da clínica: o servidor pode estar em UTC (como no Render), mas "agora" e os
    # horários de consulta são sempre o horário local da clínica.
    CLINIC_TIMEZONE = os.environ.get("CLINIC_TIMEZONE", "America/Sao_Paulo")

    LOGIN_MAX_ATTEMPTS = int(os.environ.get("LOGIN_MAX_ATTEMPTS", "5"))
    LOGIN_WINDOW_SECONDS = int(os.environ.get("LOGIN_WINDOW_SECONDS", "300"))
    # Falhas de login aceitas por IP na mesma janela, somando todos os e-mails.
    LOGIN_IP_MAX_ATTEMPTS = int(os.environ.get("LOGIN_IP_MAX_ATTEMPTS", "30"))

    # Atrás de um proxy reverso (Render, Heroku, Nginx), o IP real do cliente vem no
    # cabeçalho X-Forwarded-For. Só ative quando houver um proxy confiável na frente.
    TRUST_PROXY = env_bool("TRUST_PROXY")

    # Popula o banco com dados de demonstração na inicialização, se ele estiver vazio.
    SEED_DEMO_DATA = env_bool("SEED_DEMO_DATA")

    # Permite que qualquer pessoa crie uma conta pelo site. Nesta versão todos os usuários
    # enxergam os mesmos dados, então em um site público deixe desligado.
    ALLOW_SIGNUP = env_bool("ALLOW_SIGNUP", default=True)
