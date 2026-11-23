"""Production entry point:  waitress-serve --listen=0.0.0.0:8000 wsgi:app
Run ONE process so the daily job is not scheduled twice."""
from app import app
from scheduler import init_scheduler

init_scheduler(app)
