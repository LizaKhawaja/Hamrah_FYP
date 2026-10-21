from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.database import SessionLocal
from app.config import settings
from app.services.recommendation_service import run_recommendations
import logging

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def recommendation_job():
    db = SessionLocal()
    try:
        logger.info("Scheduler: Running AI ride recommendations...")
        results = run_recommendations(db)
        logger.info(f"Recommendations sent for {len(results)} passenger(s).")
    except Exception as e:
        logger.error(f"Recommendation job failed: {e}")
    finally:
        db.close()


def start_scheduler():
    hour = settings.ai_recommendation_hour
    minute = settings.ai_recommendation_minute
    scheduler.add_job(
        recommendation_job,
        trigger=CronTrigger(hour=hour, minute=minute),
        id="ride_recommendations",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        f"Scheduler started — recommendations will run daily at "
        f"{hour:02d}:{minute:02d}"
    )


def stop_scheduler():
    scheduler.shutdown()
