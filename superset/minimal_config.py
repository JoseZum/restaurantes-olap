import os

# Configuración básica de la base de datos
SQLALCHEMY_DATABASE_URI = os.environ.get('SQLALCHEMY_DATABASE_URI', 'postgresql://superset:superset123@superset-db:5432/superset')

# Clave secreta
SECRET_KEY = os.environ.get('SUPERSET_SECRET_KEY', 'mi_clave_super_secreta_superset_2024')

# Configuración de cache con Redis
CACHE_CONFIG = {
    'CACHE_TYPE': 'RedisCache',
    'CACHE_DEFAULT_TIMEOUT': 300,
    'CACHE_KEY_PREFIX': 'superset_',
    'CACHE_REDIS_HOST': os.environ.get('REDIS_HOST', 'superset-redis'),
    'CACHE_REDIS_PORT': int(os.environ.get('REDIS_PORT', 6379)),
    'CACHE_REDIS_DB': 1,
    'CACHE_REDIS_URL': f"redis://{os.environ.get('REDIS_HOST', 'superset-redis')}:{os.environ.get('REDIS_PORT', 6379)}/1"
}

# Configuración de sesiones
SESSION_TYPE = 'redis'
SESSION_REDIS = f"redis://{os.environ.get('REDIS_HOST', 'superset-redis')}:{os.environ.get('REDIS_PORT', 6379)}/0"

# Configuración de logging - usar configuración por defecto sin archivos
ENABLE_TIME_ROTATE = False

# Configuración de features
FEATURE_FLAGS = {
    "DASHBOARD_NATIVE_FILTERS": True,
    "ENABLE_TEMPLATE_PROCESSING": True,
    "DASHBOARD_CROSS_FILTERS": True,
    "DASHBOARD_RBAC": True,
    "EMBEDDED_SUPERSET": True,
}

# Configuración de uploads
UPLOAD_FOLDER = "/tmp/superset_uploads/"
IMG_UPLOAD_FOLDER = "/tmp/superset_uploads/"
IMG_UPLOAD_URL = "/static/uploads/"

# Configuración de SQL Lab
SQLLAB_CTAS_NO_LIMIT = True
SQLLAB_TIMEOUT = 300
SQLLAB_ASYNC_TIME_LIMIT_SEC = 600

# Configuración de seguridad
WTF_CSRF_ENABLED = True
WTF_CSRF_EXEMPT_LIST = []
WTF_CSRF_TIME_LIMIT = None

# Configuración de emails (opcional)
SMTP_HOST = "localhost"
SMTP_STARTTLS = True
SMTP_SSL = False
SMTP_USER = "superset"
SMTP_PORT = 25
SMTP_PASSWORD = ""
SMTP_MAIL_FROM = "superset@superset.com"

# Configuración de Celery para tareas asíncronas
CELERY_CONFIG = {
    'broker_url': f"redis://{os.environ.get('REDIS_HOST', 'superset-redis')}:{os.environ.get('REDIS_PORT', 6379)}/0",
    'imports': ('superset.sql_lab',),
    'result_backend': f"redis://{os.environ.get('REDIS_HOST', 'superset-redis')}:{os.environ.get('REDIS_PORT', 6379)}/0",
    'worker_prefetch_multiplier': 1,
    'task_acks_late': False,
}

# Configuración de base de datos adicional
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
    'pool_timeout': 20,
    'max_overflow': 0,
}

# Configuración de resultados
RESULTS_BACKEND = {
    'backend': 'cache',
    'cache_config': CACHE_CONFIG
}

# Configuración de webdriver para reportes
WEBDRIVER_BASEURL = "http://superset:8088/" 