import random

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import login_required

from config import EXAM_PROFILES
from models import (FetchLog, MockTest, NewsArticle, NewsCategory, NewsSource, Option, Question, Subject,
                    TestQuestion, Topic, User, db)
from scheduler import next_run_text
from services.ai import generate_questions
from services.runner import is_running, start_refresh
from services.text_utils import norm_title, sha
from utils import admin_required, to_int

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.before_request
@login_required
@admin_required
def guard():
    pass


def back(default="admin.index"):
    return redirect(request.referrer or url_for(default))


@bp.route("/")
def index():
    stats = {"Articles": NewsArticle.query.count(), "Sources": NewsSource.query.count(),
             "Questions": Question.query.count(),
             "Pending review": Question.query.filter_by(is_approved=False).count(),
             "Tests": MockTest.query.count(), "Users": User.query.count()}
    logs = FetchLog.query.order_by(FetchLog.run_at.desc()).limit(10).all()
    return render_template("admin/index.html", stats=stats, logs=logs, next_run=next_run_text(),
                           running=is_running(), ai=bool(current_app.config["ANTHROPIC_API_KEY"]))


@bp.route("/refresh", methods=["POST"])
def refresh():
    flash("Refresh started." if start_refresh(current_app._get_current_object(), "manual") else "A refresh is already running.", "info")
    return back()


@bp.route("/generate-questions", methods=["POST"])
def gen_questions():
    res = generate_questions()
    flash(f"{res['created']} question(s) created. {res['note']}", "info")
    return back()


# ---- sources -------------------------------------------------------------
@bp.route("/sources", methods=["GET", "POST"])
def sources():
    if request.method == "POST":
        name, url = request.form.get("name", "").strip(), request.form.get("feed_url", "").strip()
        if not name or not url.startswith(("http://", "https://")):
            flash("Enter a name and a feed URL starting with http:// or https://.", "danger")
        elif NewsSource.query.filter_by(feed_url=url).first():
            flash("That feed is already listed.", "warning")
        else:
            db.session.add(NewsSource(name=name[:100], feed_url=url[:700], default_category_id=to_int(request.form.get("category"))))
            db.session.commit()
            flash("Source added.", "success")
        return redirect(url_for("admin.sources"))
    return render_template("admin/sources.html", sources=NewsSource.query.order_by(NewsSource.id).all(),
                           cats=NewsCategory.query.all())


@bp.route("/sources/<int:sid>/<action>", methods=["POST"])
def source_action(sid, action):
    s = db.get_or_404(NewsSource, sid)
    if action == "toggle":
        s.is_active = not s.is_active
    elif action == "delete":
        db.session.delete(s)
    elif action == "edit":
        name, url = request.form.get("name", "").strip(), request.form.get("feed_url", "").strip()
        if name and url.startswith(("http://", "https://")):
            s.name, s.feed_url, s.default_category_id = name[:100], url[:700], to_int(request.form.get("category"))
        else:
            flash("Name and a valid URL are required.", "danger")
    db.session.commit()
    return back("admin.sources")


# ---- articles & categories -----------------------------------------------
@bp.route("/articles")
def articles():
    q = NewsArticle.query
    term = request.args.get("q", "").strip()
    if term:
        q = q.filter(NewsArticle.title.like(f"%{term[:100]}%"))
    pag = q.order_by(NewsArticle.fetched_at.desc()).paginate(page=to_int(request.args.get("page"), 1, 1), per_page=25, error_out=False)
    return render_template("admin/articles.html", pag=pag, term=term, cats=NewsCategory.query.all())


@bp.route("/articles/<int:aid>/<action>", methods=["POST"])
def article_action(aid, action):
    a = db.get_or_404(NewsArticle, aid)
    if action == "delete":
        db.session.delete(a)
    elif action == "category":
        a.category_id = to_int(request.form.get("category"))
    db.session.commit()
    return back("admin.articles")


@bp.route("/categories", methods=["GET", "POST"])
def categories():
    if request.method == "POST":
        c = db.session.get(NewsCategory, to_int(request.form.get("id"), 0)) if request.form.get("id") else NewsCategory()
        name = request.form.get("name", "").strip()
        if not c or not name:
            flash("Category name is required.", "danger")
        else:
            c.name, c.keywords = name[:80], request.form.get("keywords", "").strip().lower()
            db.session.add(c)
            try:
                db.session.commit()
                flash("Category saved. New keywords apply to future articles.", "success")
            except Exception:
                db.session.rollback()
                flash("A category with that name already exists.", "danger")
        return redirect(url_for("admin.categories"))
    return render_template("admin/categories.html", cats=NewsCategory.query.order_by(NewsCategory.id).all())


# ---- questions -------------------------------------------------------------
@bp.route("/questions", methods=["GET", "POST"])
def questions():
    if request.method == "POST":
        f = request.form
        text = f.get("text", "").strip()
        opts = [f.get(f"opt{i}", "").strip() for i in range(4)]
        exps = [f.get(f"exp{i}", "").strip() for i in range(4)]
        ci = to_int(f.get("correct"), -1)
        err = None
        if len(text) < 10:
            err = "Write the question (at least 10 characters)."
        elif not all(opts) or len(set(o.lower() for o in opts)) != 4:
            err = "Provide four different options."
        elif not all(exps):
            err = "Provide an explanation for every option."
        elif ci not in range(4):
            err = "Select the correct option."
        elif f.get("difficulty") not in ("Easy", "Medium", "Hard"):
            err = "Select a difficulty."
        elif not to_int(f.get("subject")) and not to_int(f.get("category")):
            err = "Select a subject or a current-affairs category."
        elif Question.query.filter_by(text_hash=sha(norm_title(text))).first():
            err = "A very similar question already exists."
        if err:
            flash(err, "danger")
        else:
            q = Question(text=text, text_hash=sha(norm_title(text)), subject_id=to_int(f.get("subject")),
                         topic_id=to_int(f.get("topic")), news_category_id=to_int(f.get("category")),
                         difficulty=f["difficulty"], year=to_int(f.get("year")), exam_tag=f.get("exam_tag", "").strip()[:60] or None,
                         is_approved=True, origin="manual")
            for i in range(4):
                q.options.append(Option(label="ABCD"[i], text=opts[i][:500], explanation=exps[i], is_correct=(i == ci)))
            db.session.add(q)
            db.session.commit()
            flash("Question added and approved.", "success")
        return redirect(url_for("admin.questions"))
    status = request.args.get("status", "")
    q = Question.query
    if status == "pending":
        q = q.filter_by(is_approved=False)
    pag = q.order_by(Question.id.desc()).paginate(page=to_int(request.args.get("page"), 1, 1), per_page=20, error_out=False)
    return render_template("admin/questions.html", pag=pag, status=status, subjects=Subject.query.order_by(Subject.position).all(),
                           topics=Topic.query.order_by(Topic.subject_id).all(), cats=NewsCategory.query.all())


@bp.route("/questions/<int:qid>/<action>", methods=["POST"])
def question_action(qid, action):
    q = db.get_or_404(Question, qid)
    if action == "approve":
        q.is_approved = True
    elif action == "unapprove":
        q.is_approved = False
    elif action == "delete":
        if TestQuestion.query.filter_by(question_id=qid).first():
            flash("This question is used in a mock test. Remove it from the test first, or unapprove it instead.", "warning")
            return back("admin.questions")
        db.session.delete(q)
    db.session.commit()
    return back("admin.questions")


# ---- subjects & study material ----------------------------------------------
@bp.route("/content", methods=["GET", "POST"])
def content():
    if request.method == "POST":
        f = request.form
        if f.get("kind") == "subject":
            name = f.get("name", "").strip()
            if not name or Subject.query.filter_by(name=name).first():
                flash("Enter a new, unique subject name.", "danger")
            else:
                db.session.add(Subject(name=name[:100], description=f.get("description", "")[:300], position=Subject.query.count()))
                db.session.commit()
                flash("Subject added.", "success")
        else:
            sid, title = to_int(f.get("subject")), f.get("title", "").strip()
            if not db.session.get(Subject, sid or 0) or not title or not f.get("content", "").strip():
                flash("Choose a subject and provide a title and study material.", "danger")
            else:
                db.session.add(Topic(subject_id=sid, parent_id=to_int(f.get("parent")), title=title[:200], content=f["content"].strip(),
                                     key_facts=f.get("key_facts", "").strip(), exam_relevance=f.get("exam_relevance", "")[:200],
                                     position=Topic.query.filter_by(subject_id=sid).count() + 1))
                db.session.commit()
                flash("Topic added.", "success")
        return redirect(url_for("admin.content"))
    return render_template("admin/content.html", subjects=Subject.query.order_by(Subject.position).all(), topics=Topic.query.all())


@bp.route("/topics/<int:tid>/delete", methods=["POST"])
def topic_delete(tid):
    t = db.get_or_404(Topic, tid)
    if Question.query.filter_by(topic_id=tid).first() or t.subtopics:
        flash("This topic has questions or subtopics. Move or delete them first.", "warning")
    else:
        db.session.delete(t)
        db.session.commit()
    return back("admin.content")


# ---- mock tests -----------------------------------------------------------------
@bp.route("/tests", methods=["GET", "POST"])
def tests():
    if request.method == "POST":
        f = request.form
        title = f.get("title", "").strip()
        kind = f.get("kind", "full")
        exam = f.get("exam_type", "Custom")
        prof = EXAM_PROFILES.get(exam, EXAM_PROFILES["Custom"])
        dur = to_int(f.get("duration"), prof["duration"], 1, 300)
        try:
            mark = float(f.get("mark") or prof["mark"])
            neg = float(f.get("negative") or 0)
        except ValueError:
            mark, neg = prof["mark"], 0
        qs = Question.query.filter_by(is_approved=True)
        if to_int(f.get("subject")):
            qs = qs.filter_by(subject_id=to_int(f.get("subject")))
        if to_int(f.get("topic")):
            qs = qs.filter_by(topic_id=to_int(f.get("topic")))
        if kind == "pyq":
            qs = qs.filter(Question.year.isnot(None))
        pool = qs.all()
        n = to_int(f.get("count"), 20, 1, 200)
        if not title or not pool or mark <= 0 or neg < 0:
            flash("Provide a title and valid marks; the chosen filters must match at least one approved question.", "danger")
        else:
            random.shuffle(pool)
            t = MockTest(title=title[:200], kind=kind if kind in ("full", "subject", "topic", "pyq") else "full",
                         exam_type=exam, duration_min=dur, mark_per_question=mark, negative_mark=neg)
            db.session.add(t)
            db.session.flush()
            for i, q in enumerate(pool[:n], 1):
                db.session.add(TestQuestion(test_id=t.id, question_id=q.id, position=i))
            db.session.commit()
            flash(f"Test created with {min(n, len(pool))} question(s).", "success")
        return redirect(url_for("admin.tests"))
    return render_template("admin/tests.html", tests=MockTest.query.order_by(MockTest.id.desc()).all(), profiles=EXAM_PROFILES,
                           subjects=Subject.query.order_by(Subject.position).all(), topics=Topic.query.all())


@bp.route("/tests/<int:tid>/<action>", methods=["POST"])
def test_action(tid, action):
    t = db.get_or_404(MockTest, tid)
    if action == "toggle":
        t.is_active = not t.is_active
    elif action == "delete":
        from models import TestResult
        if TestResult.query.filter_by(test_id=tid).first():
            t.is_active = False
            flash("Users have attempted this test, so it was hidden instead of deleted.", "info")
        else:
            db.session.delete(t)
    db.session.commit()
    return back("admin.tests")


@bp.route("/logs")
def logs():
    status = request.args.get("status", "")
    q = FetchLog.query
    if status in ("ok", "error", "run"):
        q = q.filter_by(status=status)
    pag = q.order_by(FetchLog.run_at.desc()).paginate(page=to_int(request.args.get("page"), 1, 1), per_page=30, error_out=False)
    return render_template("admin/logs.html", pag=pag, status=status)
