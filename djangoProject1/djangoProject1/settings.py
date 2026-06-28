"""
Django settings for djangoProject1 project.
"""

from pathlib import Path
import os
import datetime
from django.core.exceptions import ImproperlyConfigured
import json
# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
SERVER_BASE_URL = 'https://www.lansik2026.com'

# Quick-start development settings - unsuitable for production
SECRET_KEY = 'django-insecure-6j)67*2#nahe40s-*y#p32vlwpa6)h4vrp!hw_o#=(oel98*w='
DEBUG = True

# 微信小程序配置
WX_APP_ID = 'wx8c245b48cd8672b3'
WX_APP_SECRET = '8a95ce504d765a9753b33ec930a8cc1a'

ALLOWED_HOSTS = [
    'www.lansik2026.com',
    'lansik2026.com',
    '127.0.0.1',
    'localhost',
    '101.42.20.250'
]
AUTH_USER_MODEL = 'app01.User'

# 告诉 Django，Nginx 传过来的请求是 HTTPS 安全的
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# 信任来自你域名的 POST 跨站请求
CSRF_TRUSTED_ORIGINS = [
    'https://www.lansik2026.com',
    'https://lansik2026.com'
]

# Application definition
INSTALLED_APPS = [
    'simpleui',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'app01.apps.App01Config',
    'rest_framework',
    'corsheaders',  # 跨域处理
    'rest_framework_simplejwt',
    'django_filters',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# 跨域配置
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://servicewechat.com", # 小程序官方域名
    'https://www.lansik2026.com',
    'https://lansik2026.com'
]
CORS_ALLOW_CREDENTIALS = False
CORS_ALLOW_ALL_ORIGINS = True

CORS_ALLOW_METHODS = ['GET', 'POST', 'OPTIONS', 'PUT', 'DELETE']
CORS_ALLOW_HEADERS = ['Content-Type', 'Authorization', 'X-Requested-With']

ROOT_URLCONF = 'djangoProject1.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'djangoProject1.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = False

# Static & Media
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

SIMPLEUI_STATIC_OFFLINE = True
X_FRAME_OPTIONS = 'SAMEORIGIN'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# ================= Django REST Framework & JWT 配置 =================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_FILTER_BACKENDS': ['django_filters.rest_framework.DjangoFilterBackend'],
    'UNAUTHENTICATED_USER': None,
    'UNAUTHENTICATED_TOKEN': None,
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': datetime.timedelta(hours=2),
    'REFRESH_TOKEN_LIFETIME': datetime.timedelta(days=7),
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

AUTHENTICATION_BACKENDS = [
    'app01.backends.NicknameAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
]

DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024 * 20  # 100MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024 * 20

# 本地内存缓存
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'lansik-wechat-cache',
    }
}

# 日志追踪系统
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} [{module}.{funcName}] {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'app01': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        }
    },
}

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ================= 1. 定义安全配置文件的路径 =================
# 指向根目录下的 secrets.json
SECRETS_FILE = os.path.join(BASE_DIR, 'secrets.json')

# ================= 2. 读取并解析 JSON =================
try:
    with open(SECRETS_FILE, 'r', encoding='utf-8') as f:
        secrets = json.load(f)
except FileNotFoundError:
    # 启动时如果找不到文件，立刻抛出致命错误
    raise ImproperlyConfigured(f"找不到安全配置文件: {SECRETS_FILE}。请确保该文件存在！")
except json.JSONDecodeError as e:
    # 启动时如果 JSON 语法写错（比如漏了引号、逗号），立刻报错
    raise ImproperlyConfigured(f"安全配置文件 {SECRETS_FILE} 格式错误: {e}")

# ================= 3. 将解析出的配置赋值给 Django 变量 =================
# 你甚至可以把 Django 原生的 SECRET_KEY 也搬到 JSON 里
SECRET_KEY = secrets.get('DJANGO_SECRET_KEY', 'default-unsafe-key-for-dev')

# 提取微信支付大字典 (如果 JSON 里没写，默认给个空字典防崩溃)
WECHAT_PAY = secrets.get('WECHAT_PAY', {})

# 提取京东物流大字典
JD_LOGISTICS = secrets.get('JD_LOGISTICS', {})