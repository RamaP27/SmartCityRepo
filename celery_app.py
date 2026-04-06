from celery import Celery
from celery.schedules import crontab

from shems.config import settings

celery_app = Celery(
    "shems",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "shems.domains.billing.tasks",
        "shems.domains.household.tasks",
        "shems.ml.tasks",
        "shems.core.security.dpdp_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        # ── Phase 1 billing ──────────────────────────────────────────────────
        "check-spending-caps-every-15min": {
            "task": "shems.domains.billing.tasks.check_spending_caps",
            "schedule": crontab(minute="*/15"),
        },
        "compute-daily-usage-summaries": {
            "task": "shems.domains.billing.tasks.compute_daily_usage_summaries",
            "schedule": crontab(hour=1, minute=0),
        },
        # ── Phase 2 ML ───────────────────────────────────────────────────────
        "run-anomaly-detection-every-15min": {
            "task": "shems.ml.tasks.run_anomaly_detection",
            "schedule": crontab(minute="*/15"),
        },
        "run-demand-forecasting-hourly": {
            "task": "shems.ml.tasks.run_demand_forecasting",
            "schedule": crontab(minute=5),
        },
        "run-sustainability-scoring-nightly": {
            "task": "shems.ml.tasks.run_sustainability_scoring",
            "schedule": crontab(hour=2, minute=0),
        },
        "run-model-training-weekly": {
            "task": "shems.ml.tasks.run_model_training",
            "schedule": crontab(hour=3, minute=0, day_of_week="sunday"),
        },
        # ── Phase 3 IoT & device automation ─────────────────────────────────
        "poll-ecosystem-devices-every-5min": {
            "task": "shems.domains.household.tasks.poll_ecosystem_devices",
            "schedule": crontab(minute="*/5"),
        },
        "execute-device-schedules-every-minute": {
            "task": "shems.domains.household.tasks.execute_device_schedules",
            "schedule": crontab(),
        },
        # ── Phase 3 DPDP compliance ──────────────────────────────────────────
        "run-data-retention-weekly": {
            "task": "shems.core.security.dpdp_tasks.run_data_retention",
            "schedule": crontab(hour=4, minute=0, day_of_week="sunday"),
        },
    },
)
