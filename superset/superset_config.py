# Configuración de Apache Superset para Data Warehouse de Restaurantes
import os
from datetime import timedelta

# Configuración de la base de datos
DATABASE_DIALECT = os.environ.get("DATABASE_DIALECT", "postgresql")
DATABASE_USER = os.environ.get("DATABASE_USER", "superset")
DATABASE_PASSWORD = os.environ.get("DATABASE_PASSWORD", "superset123")
DATABASE_HOST = os.environ.get("DATABASE_HOST", "superset-db")
DATABASE_PORT = os.environ.get("DATABASE_PORT", "5432")
DATABASE_DB = os.environ.get("DATABASE_DB", "superset")

SQLALCHEMY_DATABASE_URI = f"{DATABASE_DIALECT}://{DATABASE_USER}:{DATABASE_PASSWORD}@{DATABASE_HOST}:{DATABASE_PORT}/{DATABASE_DB}"

# Configuración de Redis para caché
REDIS_HOST = os.environ.get("REDIS_HOST", "superset-redis")
REDIS_PORT = os.environ.get("REDIS_PORT", "6379")

# Configuración de caché
CACHE_CONFIG = {
    'CACHE_TYPE': 'RedisCache',
    'CACHE_DEFAULT_TIMEOUT': 300,
    'CACHE_KEY_PREFIX': 'superset_',
    'CACHE_REDIS_HOST': REDIS_HOST,
    'CACHE_REDIS_PORT': REDIS_PORT,
    'CACHE_REDIS_DB': 1,
    'CACHE_REDIS_URL': f'redis://{REDIS_HOST}:{REDIS_PORT}/1'
}

# Configuración de seguridad
SECRET_KEY = os.environ.get("SUPERSET_SECRET_KEY", "mi_clave_super_secreta_superset_2024")
WTF_CSRF_ENABLED = True
WTF_CSRF_TIME_LIMIT = None

# Configuración de sesiones
PERMANENT_SESSION_LIFETIME = timedelta(days=1)

# Configuración de logging - usar configuración por defecto

# Configuración de características
FEATURE_FLAGS = {
    "DASHBOARD_NATIVE_FILTERS": True,
    "DASHBOARD_CROSS_FILTERS": True,
    "DASHBOARD_FILTERS_EXPERIMENTAL": True,
    "ENABLE_TEMPLATE_PROCESSING": True,
    "ALERT_REPORTS": True,
    "DYNAMIC_PLUGINS": True,
}

# Configuración de conectores de datos
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'pool_size': 10,
    'max_overflow': 20
}

# Configuración de mapas
MAPBOX_API_KEY = ""

# Configuración de email (opcional)
SMTP_HOST = "localhost"
SMTP_STARTTLS = True
SMTP_SSL = False
SMTP_USER = "superset"
SMTP_PORT = 25
SMTP_PASSWORD = ""
SMTP_MAIL_FROM = "superset@localhost"

# Configuración adicional para desarrollo
DEBUG = True
SUPERSET_WEBSERVER_PORT = 8088
SUPERSET_WEBSERVER_ADDRESS = '0.0.0.0'

# Configuración de timeout para consultas
SUPERSET_WEBSERVER_TIMEOUT = 300
SQLLAB_TIMEOUT = 300
SUPERSET_WORKERS = 4

# Configuración de uploads - usar directorios por defecto
UPLOAD_FOLDER = "/tmp/superset_uploads/"
IMG_UPLOAD_FOLDER = "/tmp/superset_uploads/"
IMG_UPLOAD_URL = "/static/uploads/"

# Configuración de CSP
TALISMAN_ENABLED = False 