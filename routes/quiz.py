import random
from datetime import date, datetime, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models import AttemptAnswer, NewsCategory, Option, Question, QuizAttempt, Subject, db
from utils import to_int

bp = Blueprint("quiz", __name__, url_prefix="/quiz")
DIFFS = ("Easy", "Medium", "Hard")


def category_label(cat):
    if cat.startswith("s:"):
        s = db.session.get(Subject, to_int(cat[2:], 0))
        return s.name if s else "All categories"
    if cat.startswith("c:"):
        c = db.session.get(NewsCategory, to_int(cat[2:], 0))
        return f"Current affairs: {c.name}" if c else "All categories"
    return "All categories"


@bp.route("/")
@login_required
def home():
    attempts = QuizAttempt.query.filter_by(user_id=current_user.id).order_by(QuizAttempt.created_at.desc()).limit(5).all()
    return render_template("quiz_home.html", subjects=Subject.query.order_by(Subject.position).all(),
                           cats=NewsCategory.query.all(), diffs=DIFFS, attempts=attempts,
                           available=Question.query.filter_by(is_approved=True).count())


@bp.route("/take")
@login_required
def take():
    cat = request.args.get("cat", "all")
    diff = request.args.get("diff", "")
    n = to_int(request.args.get("n"), 20, 5, 50)
    q = Question.query.filter_by(is_approved=True)
    if cat.startswith("s:"):
        q = q.filter(Question.subject_id == to_int(cat[2:], 0))
    elif cat.startswith("c:"):
        q = q.filter(Question.news_category_id == to_int(cat[2:], 0))
    if diff in DIFFS:
        q = q.filter(Question.difficulty == diff)
    pool = q.all()
    if not pool:
        flash("No approved questions match those choices yet. Try another category or difficulty.", "warning")
        return redirect(url_for("quiz.home"))
    # Skip questions this user answered in the last 7 days when enough others remain.
    since = datetime.utcnow() - timedelta(days=7)
    recent = {qid for (qid,) in db.session.query(AttemptAnswer.question_id).join(QuizAttempt)
              .filter(QuizAttempt.user_id == current_user.id, QuizAttempt.created_at >= since)}
    fresh = [x for x in pool if x.id not in recent]
    if len(fresh) >= min(n, len(pool)):
        pool = fresh
    # Same set for the same user/day/filters, so a page reload does not reshuffle the quiz.
    rnd = random.Random(f"{date.today()}-{current_user.id}-{cat}-{diff}")
    rnd.shuffle(pool)
    questions = pool[:n]
    return render_template("quiz_take.html", questions=questions, label=category_label(cat), diff=diff)


@bp.route("/submit", methods=["POST"])
@login_required
def submit():
    ids = []
    for raw in request.form.getlist("qid"):
        i = to_int(raw)
        if i and i not in ids:
            ids.append(i)
    questions = Question.query.filter(Question.id.in_(ids), Question.is_approved == True).all() if ids else []  # noqa: E712
    if not questions:
        flash("Your quiz could not be submitted. Please start a new quiz.", "danger")
        return redirect(url_for("quiz.home"))
    attempt = QuizAttempt(user_id=current_user.id, label=request.form.get("label", "")[:150],
                          difficulty=request.form.get("diff", "")[:10], total=len(questions))
    db.session.add(attempt)
    correct = 0
    for q in questions:
        oid = to_int(request.form.get(f"q_{q.id}"))
        opt = next((o for o in q.options if o.id == oid), None)  # ignore ids not belonging to the question
        ok = bool(opt and opt.is_correct)
        correct += ok
        attempt.answers.append(AttemptAnswer(question_id=q.id, selected_option_id=opt.id if opt else None, is_correct=ok if opt else None))
    attempt.correct = correct
    attempt.percentage = round(correct * 100 / len(questions), 1)
    db.session.commit()
    return redirect(url_for("quiz.result", aid=attempt.id))


@bp.route("/result/<int:aid>")
@login_required
def result(aid):
    a = db.get_or_404(QuizAttempt, aid)
    if a.user_id != current_user.id:
        abort(403)
    return render_template("quiz_result.html", a=a, answered=sum(1 for x in a.answers if x.selected_option_id))


@bp.route("/history")
@login_required
def history():
    items = QuizAttempt.query.filter_by(user_id=current_user.id).order_by(QuizAttempt.created_at.desc()).all()
    return render_template("quiz_history.html", items=items)
