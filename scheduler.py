"""Daily 06:00 IST news job (APScheduler). Works only while the app process runs;
for always-on updates host the app on a server (see README)."""
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

log = logging.getLogger(__name__)
scheduler = None


def _last_due_utc(hour, minute, tz):
    now = datetime.now(tz)
    due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if due > now:
        due -= timedelta(days=1)
    return due.astimezone(timezone.utc).replace(tzinfo=None)


def init_scheduler(app):
    global scheduler
    cfg = app.config
    if not cfg["ENABLE_SCHEDULER"] or scheduler is not None:
        return None
    tz = ZoneInfo(cfg["TIMEZONE"])
    scheduler = BackgroundScheduler(timezone=tz)

    def daily_job(trigger="scheduler"):
        from services.ai import generate_questions
        from services.news_fetcher import fetch_all
        with app.app_context():
            try:
                res = fetch_all(trigger)
                log.info("News job finished: %s", res)
                if cfg["ANTHROPIC_API_KEY"]:
                    log.info("AI questions: %s", generate_questions())
            except Exception:
                log.exception("Daily news job crashed")

    def catch_up():
        """If the PC was off at 6 AM, fetch once as soon as the app starts."""
        from models import FetchLog
        with app.app_context():
            due = _last_due_utc(cfg["FETCH_HOUR"], cfg["FETCH_MINUTE"], tz)
            last = (FetchLog.query.filter_by(status="run").order_by(FetchLog.run_at.desc()).first())
            if not last or last.run_at < due:
                daily_job("catch-up")

    scheduler.add_job(daily_job, CronTrigger(hour=cfg["FETCH_HOUR"], minute=cfg["FETCH_MINUTE"], timezone=tz),
                      id="daily_news", replace_existing=True, misfire_grace_time=6 * 3600,
                      coalesce=True, max_instances=1)
    scheduler.add_job(catch_up, "date", run_date=datetime.now(tz) + timedelta(seconds=15), id="catch_up")
    scheduler.start()
    log.info("Scheduler started: daily at %02d:%02d %s", cfg["FETCH_HOUR"], cfg["FETCH_MINUTE"], cfg["TIMEZONE"])
    return scheduler


def next_run_text():
    if scheduler is None:
        return "Scheduler not running"
    job = scheduler.get_job("daily_news")
    return job.next_run_time.strftime("%d %b %Y, %I:%M %p %Z") if job and job.next_run_time else "—"
