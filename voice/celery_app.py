# Celery app configured via environment (.env). Initializes Django if DJANGO_SETTINGS_MODULE is set
# or if live_assist.settings is importable. Includes inline signal handlers for concise task logs.
import os
import logging
from celery import Celery
from celery.signals import (
    worker_process_init,
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

# Load Celery configuration from Django settings if available.
# Ensure the settings module is set via environment, but do NOT call django.setup() here
# to avoid re-entrant setup during runserver/import time.
if not os.environ.get("DJANGO_SETTINGS_MODULE"):
    os.environ["DJANGO_SETTINGS_MODULE"] = "live_assist.settings"
try:
    app.config_from_object("django.conf:settings", namespace="CELERY", silent=True)
except Exception as e:
    logger.warning("Could not load Celery config from Django settings (continuing): %s", e)

# Register tasks from this package
app.autodiscover_tasks(["voice"])  # discovers voice.tasks
try:
    # Also discover non-standard module name explicitly
    app.autodiscover_tasks(["voice"], related_name="tasks_reports")
except TypeError:
    # Older Celery versions may not support related_name; import directly as fallback
    try:
        import importlib
        importlib.import_module("voice.tasks_reports")
    except Exception:
        pass

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


# Ensure Django is fully initialized in the worker process context only
@worker_process_init.connect
def _setup_django_in_worker(**_):
    try:
        import django
        django.setup()
        logger.info("Django apps initialized in Celery worker process")
    except Exception as e:
        logger.warning("Failed to initialize Django in worker: %s", e)