# Celery app configured via environment (.env). Initializes Django if DJANGO_SETTINGS_MODULE is set
# or if live_assist.settings is importable. Includes inline signal handlers for concise task logs.
import os
import logging
from celery import Celery
from celery.signals import (
    worker_ready,
    task_received,
    task_prerun,
    task_postrun,
    task_retry,
    task_failure,
)

# Optionally load .env if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

logger = logging.getLogger("voice.celery")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

# Use Redis from env (Memurai), fallback to in-memory if not set
BROKER_URL = os.getenv("CELERY_BROKER_URL", "memory://")
RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "cache+memory://")

app = Celery("voice", broker=BROKER_URL, backend=RESULT_BACKEND)

# Eager mode flags (leave unset or 0 in production with Redis)
task_always_eager = os.getenv("CELERY_TASK_ALWAYS_EAGER", "").lower() in ("1", "true", "yes")
task_eager_propagates = os.getenv("CELERY_TASK_EAGER_PROPAGATES", "").lower() in ("1", "true", "yes")

# More informative worker log formats and stable serialization
app.conf.update(
    broker_connection_retry_on_startup=True,
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    enable_utc=True,
    timezone=os.getenv("CELERY_TIMEZONE", "UTC"),
    task_always_eager=task_always_eager,
    task_eager_propagates=task_eager_propagates,
    worker_log_format="%(levelname)s %(asctime)s [%(processName)s] %(name)s: %(message)s",
    worker_task_log_format="%(levelname)s %(asctime)s [%(processName)s] %(name)s:%(task_name)s[%(task_id)s]: %(message)s",
)

# Initialize Django ORM: use provided env var, or auto-detect live_assist.settings
dj_settings = os.environ.get("DJANGO_SETTINGS_MODULE")
if not dj_settings:
    try:
        import importlib
        importlib.import_module("live_assist.settings")
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "live_assist.settings")
        dj_settings = "live_assist.settings"
    except Exception:
        dj_settings = None

if dj_settings:
    try:
        import django
        django.setup()
        try:
            app.config_from_object("django.conf:settings", namespace="CELERY", silent=True)
        except Exception:
            pass
        logger.info("Django configured with settings module: %s", dj_settings)
    except Exception as e:
        logger.warning("Django setup failed; ORM tasks will not work until fixed: %s", e)
else:
    logger.info("DJANGO_SETTINGS_MODULE not set; running without Django ORM.")

# Register tasks from this package
app.autodiscover_tasks(["voice"])

# Inline Celery signal handlers for concise lifecycle logs (no extra files created)
@worker_ready.connect
def _on_worker_ready(sender=None, **kwargs):
    logger.info("Worker is ready. Waiting for tasks...")

@task_received.connect
def _on_task_received(request=None, **kwargs):
    try:
        logger.info("Task received: %s[%s]", request.name, request.id)
    except Exception:
        logger.info("Task received")

@task_prerun.connect
def _on_task_prerun(task_id=None, task=None, args=None, kwargs=None, **_):
    logger.info("Task started: %s[%s]", getattr(task, "name", "unknown"), task_id)

@task_postrun.connect
def _on_task_postrun(task_id=None, task=None, retval=None, state=None, **_):
    logger.info("Task finished: %s[%s] state=%s", getattr(task, "name", "unknown"), task_id, state)

@task_retry.connect
def _on_task_retry(request=None, reason=None, einfo=None, **_):
    if request:
        logger.warning("Task retry: %s[%s] reason=%s", request.task, request.id, reason)

@task_failure.connect
def _on_task_failure(task_id=None, exception=None, args=None, kwargs=None, traceback=None, einfo=None, **_):
    logger.error("Task failure: %s[%s] exc=%s", getattr(einfo, "name", "unknown"), task_id, exception)

logger.info("Celery broker: %s", BROKER_URL)
logger.info("Celery backend: %s", RESULT_BACKEND)
if task_always_eager:
    logger.info("Celery is running in EAGER mode (tasks execute synchronously).")