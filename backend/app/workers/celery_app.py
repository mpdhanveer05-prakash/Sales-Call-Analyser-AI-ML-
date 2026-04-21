from celery import Celery
from app.config import settings

celery_app = Celery(
    "sca_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.process_call_task",
        "app.workers.transcribe_task",
        "app.workers.speech_score_task",
        "app.workers.sales_score_task",
        "app.workers.keyword_check_task",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
