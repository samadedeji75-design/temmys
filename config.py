import os
from pathlib import Path

from dotenv import load_dotenv

basedir = Path(__file__).resolve().parent
load_dotenv(basedir / ".env")


def _build_database_uri():
    """
    Prefer a single DATABASE_URL if one is set (e.g. you paste Railway's
    MySQL URL in directly, with the dialect prefix fixed up). Otherwise
    build it from Railway's individual MYSQL* variables, which it always
    provides for a linked MySQL plugin. Falls back to a local dev DB if
    neither is present.

    Uses mysql-connector-python (mysql+mysqlconnector://) everywhere,
    matching the single driver actually pinned in requirements.txt.
    """
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    mysql_user = os.getenv("MYSQLUSER")
    mysql_password = os.getenv("MYSQLPASSWORD")
    mysql_host = os.getenv("MYSQLHOST")
    mysql_port = os.getenv("MYSQLPORT")
    mysql_db = os.getenv("MYSQL_DATABASE") or os.getenv("MYSQLDATABASE")

    if mysql_user and mysql_host and mysql_db:
        return (
            f"mysql+mysqlconnector://{mysql_user}:{mysql_password}"
            f"@{mysql_host}:{mysql_port}/{mysql_db}"
        )

    return "mysql+mysqlconnector://root@localhost/temmys_db1"


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = _build_database_uri()

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    LOG_TO_STDOUT = os.getenv("LOG_TO_STDOUT")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Flask-Mail — used to send teacher login-credential emails. All
    # values come from the environment; nothing here works until you set
    # real SMTP credentials on Railway (e.g. a Gmail app password, or a
    # transactional provider like Brevo/SendGrid/Mailgun's SMTP endpoint).
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", MAIL_USERNAME)


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False  # allows plain-http localhost


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True  # requires the app actually served over HTTPS


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}