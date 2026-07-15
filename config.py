import os
from pathlib import Path

from dotenv import load_dotenv

basedir = Path(__file__).resolve().parent
load_dotenv(basedir / ".env")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

    # Falls back to the local MySQL dev DB only if DATABASE_URL isn't set —
    # in any real deployment, DATABASE_URL from the environment wins.
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "mysql+mysqlconnector://root@localhost/temmys_db1"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    LOG_TO_STDOUT = os.getenv("LOG_TO_STDOUT")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


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
    ADMIN_EMAIL="admin@temmys.com"
    ADMIN_PASSWORD="admin123"
    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://"
        f"{os.getenv('MYSQLUSER')}:"
        f"{os.getenv('MYSQLPASSWORD')}@"
        f"{os.getenv('MYSQLHOST')}:"
        f"{os.getenv('MYSQLPORT')}/"
        f"{os.getenv('MYSQL_DATABASE')}"
)


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}