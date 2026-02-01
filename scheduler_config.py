"""
Start twstock code update scheduler in background.
Runs daily at 6:00 UTC (14:00 Taiwan).
"""
import threading

_scheduler_started = False
_lock = threading.Lock()


def _update_twstock():
    try:
        import twstock
        twstock.__update_codes()
    except Exception:
        pass


def _start_scheduler():
    global _scheduler_started
    with _lock:
        if _scheduler_started:
            return
        _scheduler_started = True

    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler()
    scheduler.add_job(_update_twstock, "cron", hour=6, minute=0)  # 6:00 UTC daily
    scheduler.start()


# Run initial update in background (don't block app startup)
threading.Thread(target=_update_twstock, daemon=True).start()
_start_scheduler()
