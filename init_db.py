"""Create the database/tables and load starter data. Safe to re-run."""
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app import create_app
from config import Config
from models import (MockTest, NewsCategory, NewsSource, Option, Question, Subject, TestQuestion, Topic, User, db)
from seed_data import CATEGORIES, QUESTIONS, SOURCES, SUBJECTS, TESTS
from services.text_utils import norm_title, sha


def ensure_mysql_database():
    url = make_url(Config.SQLALCHEMY_DATABASE_URI)
    if url.get_backend_name() != "mysql":
        return
    server = url.set(database=None)
    eng = create_engine(server)
    with eng.connect() as c:
        c.execute(text(f"CREATE DATABASE IF NOT EXISTS `{url.database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
        c.commit()
    print(f"Database `{url.database}` ready.")


def seed():
    cats = {}
    for name, kw in CATEGORIES:
        c = NewsCategory.query.filter_by(name=name).first() or NewsCategory(name=name)
        c.keywords = c.keywords or kw
        db.session.add(c)
        cats[name] = c
    db.session.flush()
    for name, url, cat in SOURCES:
        if not NewsSource.query.filter_by(feed_url=url).first():
            db.session.add(NewsSource(name=name, feed_url=url, default_category_id=cats[cat].id))
    topics, subjects = {}, {}
    for i, (name, desc, ttitle, content, facts) in enumerate(SUBJECTS):
        s = Subject.query.filter_by(name=name).first() or Subject(name=name, description=desc, position=i)
        db.session.add(s)
        db.session.flush()
        subjects[name] = s
        t = Topic.query.filter_by(subject_id=s.id, title=ttitle).first()
        if not t:
            t = Topic(subject_id=s.id, title=ttitle, content=content, key_facts=facts,
                      exam_relevance="Karnataka FDA / SDA general studies", position=1)
            db.session.add(t)
            db.session.flush()
        topics[(name, ttitle)] = t
    for sname, ttitle, diff, text_, opts, ci in QUESTIONS:
        h = sha(norm_title(text_))
        if Question.query.filter_by(text_hash=h).first():
            continue
        q = Question(text=text_, text_hash=h, subject_id=subjects[sname].id,
                     topic_id=topics[(sname, ttitle)].id, difficulty=diff, is_approved=True, origin="manual")
        for k, (otext, why) in enumerate(opts):
            q.options.append(Option(label="ABCD"[k], text=otext, explanation=why, is_correct=(k == ci)))
        db.session.add(q)
    db.session.flush()
    for title, kind, subj_names, dur, exam in TESTS:
        if MockTest.query.filter_by(title=title).first():
            continue
        qs = Question.query.filter_by(is_approved=True)
        if subj_names:
            ids = [subjects[n].id for n in subj_names]
            qs = qs.filter(Question.subject_id.in_(ids))
        qs = qs.order_by(Question.id).all()
        t = MockTest(title=title, kind=kind, exam_type=exam, duration_min=dur, mark_per_question=1.0, negative_mark=0.25)
        db.session.add(t)
        db.session.flush()
        for pos, q in enumerate(qs, 1):
            db.session.add(TestQuestion(test_id=t.id, question_id=q.id, position=pos))
    if not User.query.filter_by(email=Config.ADMIN_EMAIL).first():
        u = User(name="Administrator", email=Config.ADMIN_EMAIL, is_admin=True)
        u.set_password(Config.ADMIN_PASSWORD)
        db.session.add(u)
        print(f"Admin created: {Config.ADMIN_EMAIL}")
    db.session.commit()


if __name__ == "__main__":
    ensure_mysql_database()
    app = create_app()
    with app.app_context():
        db.create_all()
        seed()
        print("Tables created and starter data loaded.")
        print(f"Sources: {NewsSource.query.count()} | Subjects: {Subject.query.count()} | "
              f"Questions: {Question.query.count()} | Tests: {MockTest.query.count()}")
