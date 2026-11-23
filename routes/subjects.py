from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import login_required

from models import MockTest, Question, Subject, TestQuestion, Topic, db
from routes.tests import start_attempt

bp = Blueprint("subjects", __name__, url_prefix="/subjects")


def counts():
    rows = db.session.query(Question.subject_id, db.func.count(Question.id)).filter_by(is_approved=True).group_by(Question.subject_id).all()
    return dict(rows)


@bp.route("/")
def index():
    return render_template("subjects.html", subjects=Subject.query.order_by(Subject.position).all(), qcount=counts())


@bp.route("/<int:sid>")
def subject(sid):
    s = db.get_or_404(Subject, sid)
    tests = (MockTest.query.filter_by(is_active=True).join(TestQuestion).join(Question)
             .filter(Question.subject_id == sid).distinct().all())
    pyq = Question.query.filter(Question.subject_id == sid, Question.is_approved == True, Question.year.isnot(None)).count()  # noqa: E712
    top = [t for t in s.topics if t.parent_id is None]
    return render_template("subject.html", s=s, top=top, tests=tests, pyq=pyq, qn=counts().get(sid, 0))


@bp.route("/topic/<int:tid>")
def topic(tid):
    t = db.get_or_404(Topic, tid)
    qs = Question.query.filter_by(topic_id=tid, is_approved=True).order_by(Question.id).all()
    return render_template("topic.html", t=t, qs=qs)


def make_test(kind, title, qs, exam="Custom"):
    test = MockTest.query.filter_by(title=title, kind=kind).first()
    if not test:
        test = MockTest(title=title, kind=kind, exam_type=exam, duration_min=max(5, round(len(qs) * 1.0)),
                        mark_per_question=1.0, negative_mark=0.25)
        db.session.add(test)
        db.session.flush()
        for i, q in enumerate(qs, 1):
            db.session.add(TestQuestion(test_id=test.id, question_id=q.id, position=i))
        db.session.commit()
    return test


@bp.route("/topic/<int:tid>/test", methods=["POST"])
@login_required
def topic_test(tid):
    t = db.get_or_404(Topic, tid)
    qs = Question.query.filter_by(topic_id=tid, is_approved=True).order_by(Question.id).all()
    if not qs:
        flash("This topic has no approved questions yet.", "warning")
        return redirect(url_for("subjects.topic", tid=tid))
    return start_attempt(make_test("topic", f"Topic test: {t.title}", qs))


@bp.route("/<int:sid>/test", methods=["POST"])
@login_required
def subject_test(sid):
    s = db.get_or_404(Subject, sid)
    qs = Question.query.filter_by(subject_id=sid, is_approved=True).order_by(Question.id).all()
    if not qs:
        flash("This subject has no approved questions yet.", "warning")
        return redirect(url_for("subjects.subject", sid=sid))
    return start_attempt(make_test("subject", f"Subject test: {s.name}", qs))
