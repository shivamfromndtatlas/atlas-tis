from .base import *  # noqa: F403
from .base import BASE_DIR, env

DEBUG = False
SECRET_KEY = "test-only-secret-key-that-is-long-enough-for-hs256"
DATABASES = {"default": env.db("TEST_DATABASE_URL", default="sqlite:///:memory:")}
DATABASES["default"]["ATOMIC_REQUESTS"] = True
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CELERY_TASK_ALWAYS_EAGER = True
AUTH_COOKIE_SECURE = False
MEDIA_ROOT = BASE_DIR / ".test-media"
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_RATES": {"auth": "1000/min", "otp": "1000/min", "anon": "1000/min"},
}
