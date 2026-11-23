from datetime import datetime
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()
utcnow = datetime.utcnow  # all datetimes stored as naive UTC


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=utcnow)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


class NewsCategory(db.Model):
    __tablename__ = "news_categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    keywords = db.Column(db.Text, default="")  # comma separated, lower case


class NewsSource(db.Model):
    __tablename__ = "news_sources"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    feed_url = db.Column(db.String(700), unique=True, nullable=False)
    default_category_id = db.Column(db.Integer, db.ForeignKey("news_categories.id"))
    default_category = db.relationship("NewsCategory")
    is_active = db.Column(db.Boolean, default=True)
    last_status = db.Column(db.String(20))
    last_message = db.Column(db.String(300))
    last_fetched_at = db.Column(db.DateTime)


class NewsArticle(db.Model):
    __tablename__ = "news_articles"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(500), nullable=False)
    link = db.Column(db.String(1000), nullable=False)
    link_hash = db.Column(db.String(40), unique=True, nullable=False)
    title_hash = db.Column(db.String(40), unique=True, nullable=False)
    source_id = db.Column(db.Integer, db.ForeignKey("news_sources.id", ondelete="SET NULL"))
    source = db.relationship("NewsSource")
    publisher = db.Column(db.String(150))  # original publisher name
    category_id = db.Column(db.Integer, db.ForeignKey("news_categories.id"))
    category = db.relationship("NewsCategory")
    summary = db.Column(db.Text)       # text supplied by the feed
    explanation = db.Column(db.Text)   # short explanation
    key_facts = db.Column(db.Text)     # newline separated
    explanation_origin = db.Column(db.String(20), default="feed")  # feed | title | ai
    published_at = db.Column(db.DateTime, index=True, nullable=False)
    fetched_at = db.Column(db.DateTime, default=utcnow, index=True)


class FetchLog(db.Model):
    __tablename__ = "fetch_logs"
    id = db.Column(db.Integer, primary_key=True)
    source_id = db.Column(db.Integer, db.ForeignKey("news_sources.id", ondelete="SET NULL"))
    source_name = db.Column(db.String(100))
    status = db.Column(db.String(10))  # ok | error | run
    message = db.Column(db.String(500))
    added = db.Column(db.Integer, default=0)
    trigger = db.Column(db.String(20))  # scheduler | manual | catch-up
    run_at = db.Column(db.DateTime, default=utcnow, index=True)


class Subject(db.Model):
    __tablename__ = "subjects"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(300))
    position = db.Column(db.Integer, default=0)
    topics = db.relationship("Topic", backref="subject", order_by="Topic.position", cascade="all, delete-orphan")


class Topic(db.Model):
    __tablename__ = "topics"
    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("topics.id"))  # subtopic support
    parent = db.relationship("Topic", remote_side=[id], backref="subtopics")
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text)      # study material (plain text / simple HTML-free paragraphs)
    key_facts = db.Column(db.Text)    # newline separated
    exam_relevance = db.Column(db.String(200))
    position = db.Column(db.Integer, default=0)


class Question(db.Model):
    __tablename__ = "questions"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    text_hash = db.Column(db.String(40), unique=True, nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"))
    subject = db.relationship("Subject")
    topic_id = db.Column(db.Integer, db.ForeignKey("topics.id"))
    topic = db.relationship("Topic")
    news_category_id = db.Column(db.Integer, db.ForeignKey("news_categories.id"))
    news_category = db.relationship("NewsCategory")
    article_id = db.Column(db.Integer, db.ForeignKey("news_articles.id", ondelete="SET NULL"))
    article = db.relationship("NewsArticle")
    difficulty = db.Column(db.String(10), default="Medium")  # Easy | Medium | Hard
    exam_tag = db.Column(db.String(60))   # e.g. "FDA 2019" for previous-year questions
    year = db.Column(db.Integer)          # set only for genuine previous-year questions
    is_approved = db.Column(db.Boolean, default=False)
    origin = db.Column(db.String(10), default="manual")  # manual | ai
    created_at = db.Column(db.DateTime, default=utcnow)
    options = db.relationship("Option", backref="question", order_by="Option.label",
                              cascade="all, delete-orphan")

    @property
    def correct(self):
        return next((o for o in self.options if o.is_correct), None)


class Option(db.Model):
    __tablename__ = "options"
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    label = db.Column(db.String(1), nullable=False)  # A-D
    text = db.Column(db.String(500), nullable=False)
    explanation = db.Column(db.Text)  # why this option is right / wrong
    is_correct = db.Column(db.Boolean, default=False)


class MockTest(db.Model):
    __tablename__ = "mock_tests"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    kind = db.Column(db.String(10), default="full")  # full | subject | topic | pyq
    exam_type = db.Column(db.String(20), default="FDA")
    duration_min = db.Column(db.Integer, default=60)
    mark_per_question = db.Column(db.Float, default=1.0)
    negative_mark = db.Column(db.Float, default=0.25)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    items = db.relationship("TestQuestion", backref="test", order_by="TestQuestion.position",
                            cascade="all, delete-orphan")


class TestQuestion(db.Model):
    __tablename__ = "test_questions"
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey("mock_tests.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    question = db.relationship("Question")
    position = db.Column(db.Integer, default=0)


class QuizAttempt(db.Model):
    __tablename__ = "user_quiz_attempts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    label = db.Column(db.String(150))
    difficulty = db.Column(db.String(10))
    total = db.Column(db.Integer, default=0)
    correct = db.Column(db.Integer, default=0)
    percentage = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=utcnow, index=True)
    answers = db.relationship("AttemptAnswer", backref="quiz_attempt", cascade="all, delete-orphan")


class TestResult(db.Model):
    __tablename__ = "user_test_results"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey("mock_tests.id"), nullable=False)
    test = db.relationship("MockTest")
    started_at = db.Column(db.DateTime, default=utcnow)
    submitted_at = db.Column(db.DateTime)
    score = db.Column(db.Float, default=0)
    max_score = db.Column(db.Float, default=0)
    correct = db.Column(db.Integer, default=0)
    wrong = db.Column(db.Integer, default=0)
    unattempted = db.Column(db.Integer, default=0)
    percentage = db.Column(db.Float, default=0)
    time_taken_sec = db.Column(db.Integer, default=0)
    answers = db.relationship("AttemptAnswer", backref="test_result", cascade="all, delete-orphan")


class AttemptAnswer(db.Model):
    """The user's answer to one question in a quiz attempt or a test attempt."""
    __tablename__ = "attempt_answers"
    id = db.Column(db.Integer, primary_key=True)
    quiz_attempt_id = db.Column(db.Integer, db.ForeignKey("user_quiz_attempts.id"))
    test_result_id = db.Column(db.Integer, db.ForeignKey("user_test_results.id"))
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    question = db.relationship("Question")
    selected_option_id = db.Column(db.Integer, db.ForeignKey("options.id"))
    selected_option = db.relationship("Option")
    is_correct = db.Column(db.Boolean)


class Bookmark(db.Model):
    __tablename__ = "bookmarks"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    article_id = db.Column(db.Integer, db.ForeignKey("news_articles.id", ondelete="CASCADE"))
    article = db.relationship("NewsArticle")
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id", ondelete="CASCADE"))
    question = db.relationship("Question")
    created_at = db.Column(db.DateTime, default=utcnow)
