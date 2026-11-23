import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://root:password@localhost:3306/karnataka_exam?charset=utf8mb4",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}
    TIMEZONE = "Asia/Kolkata"
    ENABLE_SCHEDULER = os.getenv("ENABLE_SCHEDULER", "1") == "1"
    FETCH_HOUR = int(os.getenv("FETCH_HOUR", "6"))
    FETCH_MINUTE = int(os.getenv("FETCH_MINUTE", "0"))
    FETCH_WINDOW_HOURS = int(os.getenv("FETCH_WINDOW_HOURS", "24"))
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
    AI_MAX_PER_RUN = int(os.getenv("AI_MAX_PER_RUN", "25"))
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "ChangeMe#2026")
    PER_PAGE = 15


# Exam profiles used when creating mock tests. Verify the marking scheme
# against the official notification of the exam you are targeting.
EXAM_PROFILES = {
    "FDA": {"mark": 1.0, "negative": 0.25, "duration": 90},
    "SDA": {"mark": 1.0, "negative": 0.25, "duration": 90},
    "KPSC": {"mark": 1.0, "negative": 0.25, "duration": 120},
    "Custom": {"mark": 1.0, "negative": 0.0, "duration": 60},
}
