from datetime import datetime, timedelta

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from models import (Bookmark, FetchLog, MockTest, NewsArticle, NewsCategory, Question, QuizAttempt,
                    TestResult, db)
from scheduler import next_run_text
from services.runner import is_running, start_refresh
from utils import ist_day_range, to_int

bp = Blueprint("main", __name__)


@bp.route("/")
def dashboard():
    since = datetime.utcnow() - timedelta(hours=24)
    todays = NewsArticle.query.filter(NewsArticle.published_at >= since).order_by(NewsArticle.published_at.desc()).limit(6).all()
    fresh = bool(todays)
    if not todays:
        todays = NewsArticle.query.order_by(NewsArticle.published_at.desc()).limit(6).all()
    last_run = FetchLog.query.filter_by(status="run").order_by(FetchLog.run_at.desc()).first()
    stats = {
        "articles": NewsArticle.query.count(),
        "today": NewsArticle.query.filter(NewsArticle.published_at >= since).count(),
        "questions": Question.query.filter_by(is_approved=True).count(),
        "tests": MockTest.query.filter_by(is_active=True).count(),
    }
    chart = None
    if current_user.is_authenticated:
        qa = QuizAttempt.query.filter_by(user_id=current_user.id).all()
        tr = TestResult.query.filter(TestResult.user_id == current_user.id, TestResult.submitted_at.isnot(None)).all()
        pts = sorted([(a.created_at, a.percentage, "Quiz") for a in qa] + [(r.submitted_at, r.percentage, "Test") for r in tr])[-10:]
        if pts:
            chart = {"labels": [f"{p[2]} {p[0].strftime('%d %b')}" for p in pts], "values": [round(p[1], 1) for p in pts]}
        stats["my_attempts"] = len(qa) + len(tr)
        stats["my_avg"] = round(sum(p[1] for p in pts) / len(pts), 1) if pts else 0
    return render_template("dashboard.html", todays=todays, fresh=fresh, stats=stats, last_run=last_run,
                           chart=chart, next_run=next_run_text())


@bp.route("/news")
def news():
    q = NewsArticle.query
    term = request.args.get("q", "").strip()
    cat = to_int(request.args.get("category"))
    date = request.args.get("date", "").strip()
    page = to_int(request.args.get("page"), 1, 1)
    if term:
        like = f"%{term[:100]}%"
        q = q.filter(NewsArticle.title.like(like) | NewsArticle.summary.like(like) | NewsArticle.publisher.like(like))
    if cat:
        q = q.filter(NewsArticle.category_id == cat)
    if date:
        try:
            s, e = ist_day_range(date)
            q = q.filter(NewsArticle.published_at >= s, NewsArticle.published_at < e)
        except ValueError:
            flash("Choose a valid date.", "warning")
            date = ""
    pag = q.order_by(NewsArticle.published_at.desc()).paginate(page=page, per_page=current_app.config["PER_PAGE"], error_out=False)
    marked = set()
    if current_user.is_authenticated:
        marked = {b.article_id for b in Bookmark.query.filter(Bookmark.user_id == current_user.id, Bookmark.article_id.isnot(None))}
    return render_template("news.html", pag=pag, cats=NewsCategory.query.order_by(NewsCategory.id).all(),
                           term=term, cat=cat, date=date, marked=marked, running=is_running())


@bp.route("/news/refresh", methods=["POST"])
@login_required
def refresh():
    last = FetchLog.query.filter_by(trigger="manual").order_by(FetchLog.run_at.desc()).first()
    if not current_user.is_admin and last and datetime.utcnow() - last.run_at < timedelta(minutes=5):
        flash("News was refreshed a moment ago. Try again in a few minutes.", "warning")
    elif start_refresh(current_app._get_current_object(), "manual"):
        flash("Refresh started. New articles will appear in a minute - reload the page.", "success")
    else:
        flash("A refresh is already running.", "info")
    return redirect(request.referrer or url_for("main.news"))


@bp.route("/bookmark/article/<int:aid>", methods=["POST"])
@login_required
def bookmark_article(aid):
    db.get_or_404(NewsArticle, aid)
    b = Bookmark.query.filter_by(user_id=current_user.id, article_id=aid).first()
    if b:
        db.session.delete(b)
        state = False
    else:
        db.session.add(Bookmark(user_id=current_user.id, article_id=aid))
        state = True
    db.session.commit()
    return jsonify(saved=state)


@bp.route("/bookmarks")
@login_required
def bookmarks():
    items = (Bookmark.query.filter(Bookmark.user_id == current_user.id, Bookmark.article_id.isnot(None))
             .order_by(Bookmark.created_at.desc()).all())
    return render_template("bookmarks.html", items=items)
