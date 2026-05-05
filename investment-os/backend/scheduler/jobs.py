import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def _run_daily_sync():
    logger.info("Scheduled sync triggered")
    from services.sync_service import sync_all
    result = sync_all()
    logger.info(f"Scheduled sync done: {result.status}, {result.records_updated} records")


def start_scheduler():
    global _scheduler
    _scheduler = BackgroundScheduler()
    # 4:30 PM IST = 11:00 UTC. Run Mon–Fri.
    _scheduler.add_job(
        _run_daily_sync,
        CronTrigger(day_of_week="mon-fri", hour=11, minute=0, timezone="UTC"),
        id="daily_sync",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("APScheduler started — daily sync at 4:30 PM IST")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")
