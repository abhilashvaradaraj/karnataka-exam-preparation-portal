from datetime import datetime, timedelta, timezone
from functools import wraps
from zoneinfo import ZoneInfo

from flask import abort
from flask_login import current_user

IST = ZoneInfo("Asia/Kolkata")
UTC = timezone.utc


def to_ist(dt):
    return dt.replace(tzinfo=UTC).astimezone(IST) if dt else None


def ist_day_range(date_str):
    """'2026-11-22' -> (start_utc, end_utc) naive datetimes for that IST day."""
    d = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=IST)
    s = d.astimezone(UTC).replace(tzinfo=None)
    return s, s + timedelta(days=1)


def admin_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return fn(*a, **kw)
    return wrapper


def to_int(v, default=None, lo=None, hi=None):
    try:
        n = int(v)
    except (TypeError, ValueError):
        return default
    if lo is not None and n < lo:
        return lo
    if hi is not None and n > hi:
        return hi
    return n
