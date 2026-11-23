import threading

_lock = threading.Lock()


def start_refresh(app, trigger="manual"):
    """Run a news fetch in the background. Returns False if one is already running."""
    if not _lock.acquire(blocking=False):
        return False

    def work():
        from services.news_fetcher import fetch_all
        try:
            with app.app_context():
                fetch_all(trigger)
        finally:
            _lock.release()

    threading.Thread(target=work, daemon=True).start()
    return True


def is_running():
    return _lock.locked()
