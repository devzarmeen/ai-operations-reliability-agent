from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.scheduler.jobs import run_reliability_check


scheduler = AsyncIOScheduler()


def start_scheduler():
    scheduler.add_job(
        run_reliability_check,
        "interval",
        minutes=1,
        id="reliability_check",
        replace_existing=True,
    )

    scheduler.start()

    print("[SCHEDULER] Started - reliability checks every 1 minute")


def stop_scheduler():
    scheduler.shutdown()

    print("[SCHEDULER] Stopped")