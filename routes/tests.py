from datetime import datetime, timedelta

from flask import Blueprint, abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models import AttemptAnswer, MockTest, Option, TestResult, db
from utils import to_int

bp = Blueprint("tests", __name__, url_prefix="/tests")
GRACE_SECONDS = 30


def start_attempt(test):
    """Resume an unfinished attempt (if time remains) or start a new one."""
    if not test.items:
        flash("This test has no questions yet.", "warning")
        return redirect(url_for("tests.index"))
    open_ = TestResult.query.filter_by(user_id=current_user.id, test_id=test.id, submitted_at=None).order_by(TestResult.id.desc()).first()
    if open_ and remaining(open_) > 0:
        return redirect(url_for("tests.attempt", rid=open_.id))
    r = TestResult(user_id=current_user.id, test_id=test.id)
    db.session.add(r)
    db.session.commit()
    return redirect(url_for("tests.attempt", rid=r.id))


def remaining(r):
    end = r.started_at + timedelta(minutes=r.test.duration_min)
    return int((end - datetime.utcnow()).total_seconds())


def own_result(rid):
    r = db.get_or_404(TestResult, rid)
    if r.user_id != current_user.id:
        abort(403)
    return r


def finalize(r, answers):
    """answers: {question_id: option_id}. Grades on the server; the client is never trusted."""
    t = r.test
    AttemptAnswer.query.filter_by(test_result_id=r.id).delete()
    correct = wrong = 0
    for item in t.items:
        q = item.question
        opt = next((o for o in q.options if o.id == answers.get(q.id)), None)
        ok = None
        if opt:
            ok = opt.is_correct
            correct += ok
            wrong += (not ok)
        db.session.add(AttemptAnswer(test_result_id=r.id, question_id=q.id,
                                     selected_option_id=opt.id if opt else None, is_correct=ok))
    n = len(t.items)
    r.correct, r.wrong, r.unattempted = correct, wrong, n - correct - wrong
    r.max_score = round(n * t.mark_per_question, 2)
    r.score = round(correct * t.mark_per_question - wrong * t.negative_mark, 2)
    r.percentage = round(max(r.score, 0) * 100 / r.max_score, 1) if r.max_score else 0
    r.submitted_at = datetime.utcnow()
    cap = timedelta(minutes=t.duration_min)
    r.time_taken_sec = int(min(r.submitted_at - r.started_at, cap).total_seconds())
    db.session.commit()


def saved_answers(r):
    return {a.question_id: a.selected_option_id for a in AttemptAnswer.query.filter_by(test_result_id=r.id) if a.selected_option_id}


@bp.route("/")
@login_required
def index():
    kind = request.args.get("kind", "")
    q = MockTest.query.filter_by(is_active=True)
    if kind in ("full", "subject", "topic", "pyq"):
        q = q.filter_by(kind=kind)
    best = {}
    for r in TestResult.query.filter(TestResult.user_id == current_user.id, TestResult.submitted_at.isnot(None)):
        best[r.test_id] = max(best.get(r.test_id, 0), r.percentage)
    recent = (TestResult.query.filter(TestResult.user_id == current_user.id, TestResult.submitted_at.isnot(None))
              .order_by(TestResult.submitted_at.desc()).limit(8).all())
    return render_template("tests.html", tests=q.order_by(MockTest.created_at.desc()).all(), kind=kind, best=best, recent=recent)


@bp.route("/<int:tid>/start", methods=["POST"])
@login_required
def start(tid):
    t = db.get_or_404(MockTest, tid)
    if not t.is_active:
        abort(404)
    return start_attempt(t)


@bp.route("/attempt/<int:rid>")
@login_required
def attempt(rid):
    r = own_result(rid)
    if r.submitted_at:
        return redirect(url_for("tests.result", rid=rid))
    left = remaining(r)
    if left <= 0:
        finalize(r, saved_answers(r))
        flash("Time was up - your saved answers were submitted automatically.", "info")
        return redirect(url_for("tests.result", rid=rid))
    data = [{"id": it.question.id, "text": it.question.text,
             "options": [{"id": o.id, "label": o.label, "text": o.text} for o in it.question.options]}
            for it in r.test.items]
    return render_template("exam.html", r=r, t=r.test, data=data, left=left, saved=saved_answers(r))


@bp.route("/attempt/<int:rid>/save", methods=["POST"])
@login_required
def save(rid):
    r = own_result(rid)
    if r.submitted_at or remaining(r) < -GRACE_SECONDS:
        return jsonify(ok=False), 409
    body = request.get_json(silent=True) or {}
    qid, oid = to_int(body.get("q")), to_int(body.get("o"))
    item = next((i for i in r.test.items if i.question_id == qid), None)
    if not item:
        return jsonify(ok=False), 400
    row = AttemptAnswer.query.filter_by(test_result_id=rid, question_id=qid).first()
    valid = next((o for o in item.question.options if o.id == oid), None)
    if not row:
        row = AttemptAnswer(test_result_id=rid, question_id=qid)
        db.session.add(row)
    row.selected_option_id = valid.id if valid else None
    db.session.commit()
    return jsonify(ok=True)


@bp.route("/attempt/<int:rid>/submit", methods=["POST"])
@login_required
def submit(rid):
    r = own_result(rid)
    if r.submitted_at:
        return jsonify(redirect=url_for("tests.result", rid=rid))
    body = request.get_json(silent=True) or {}
    answers = {}
    if remaining(r) >= -GRACE_SECONDS:  # late submissions fall back to the autosaved answers
        for k, v in (body.get("answers") or {}).items():
            qk, ov = to_int(k), to_int(v)
            if qk and ov:
                answers[qk] = ov
    else:
        answers = saved_answers(r)
    finalize(r, answers)
    return jsonify(redirect=url_for("tests.result", rid=rid))


@bp.route("/result/<int:rid>")
@login_required
def result(rid):
    r = own_result(rid)
    if not r.submitted_at:
        return redirect(url_for("tests.attempt", rid=rid))
    by_subject = {}
    for a in r.answers:
        name = a.question.subject.name if a.question.subject else (a.question.news_category.name if a.question.news_category else "General")
        d = by_subject.setdefault(name, {"total": 0, "correct": 0})
        d["total"] += 1
        d["correct"] += bool(a.is_correct)
    order = {it.question_id: it.position for it in r.test.items}
    answers = sorted(r.answers, key=lambda a: order.get(a.question_id, 0))
    return render_template("test_result.html", r=r, t=r.test, answers=answers, by_subject=by_subject)
