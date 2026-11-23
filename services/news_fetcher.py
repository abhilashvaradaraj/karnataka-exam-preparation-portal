"""RSS collection: fetch -> filter last N hours -> de-duplicate -> categorise -> save."""
import logging
from datetime import datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import feedparser
import requests
from flask import current_app

from models import FetchLog, NewsArticle, NewsCategory, NewsSource, db
from services.text_utils import clean, extract_key_facts, norm_title, sha, simple_explanation

log = logging.getLogger(__name__)
UA = {"User-Agent": "Mozilla/5.0 (compatible; KarnatakaExamPortal/1.0; educational RSS reader)"}
FALLBACK_CATEGORY = "Indian National Affairs"


def normalise_link(url):
    p = urlparse(url.strip())
    q = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith(("utm_", "fbclid", "gclid", "ocid"))]
    return urlunparse((p.scheme, p.netloc.lower(), p.path.rstrip("/"), "", urlencode(q), ""))


def entry_time(e):
    for k in ("published_parsed", "updated_parsed"):
        if e.get(k):
            return datetime(*e[k][:6])  # feedparser returns UTC
    return None


def categorise(text, source, cats):
    low = text.lower()
    best, best_score = None, 0
    for c in cats:
        score = sum(1 for kw in (c.keywords or "").split(",") if kw.strip() and kw.strip().lower() in low)
        if score > best_score:
            best, best_score = c, score
    if best:
        return best, [kw.strip() for kw in (best.keywords or "").split(",") if kw.strip() and kw.strip().lower() in low]
    if source.default_category:
        return source.default_category, []
    return next((c for c in cats if c.name == FALLBACK_CATEGORY), None), []


def fetch_feed(url):
    r = requests.get(url, headers=UA, timeout=20)
    r.raise_for_status()
    feed = feedparser.parse(r.content)
    if feed.bozo and not feed.entries:
        raise ValueError(f"Feed could not be parsed: {feed.bozo_exception}")
    return feed


def fetch_source(source, cats, cutoff, seen_links, seen_titles):
    feed = fetch_feed(source.feed_url)
    added = 0
    for e in feed.entries:
        title = clean(e.get("title"), 500)
        link = (e.get("link") or "").strip()
        published = entry_time(e)
        if not title or not link or not published:
            continue  # undated items cannot be verified as recent -> skipped
        if published < cutoff or published > datetime.utcnow() + timedelta(hours=2):
            continue
        lh, th = sha(normalise_link(link)), sha(norm_title(title))
        if lh in seen_links or th in seen_titles:
            continue
        if NewsArticle.query.filter((NewsArticle.link_hash == lh) | (NewsArticle.title_hash == th)).first():
            seen_links.add(lh); seen_titles.add(th)
            continue
        publisher = (e.get("source") or {}).get("title") if isinstance(e.get("source"), dict) else None
        publisher = publisher or source.name
        summary = clean(e.get("summary") or e.get("description"), 1000)
        cat, tags = categorise(f"{title} {summary}", source, cats)
        explanation, origin = simple_explanation(title, summary, publisher)
        db.session.add(NewsArticle(
            title=title, link=link[:1000], link_hash=lh, title_hash=th, source_id=source.id,
            publisher=publisher[:150], category_id=cat.id if cat else None, summary=summary,
            explanation=explanation, explanation_origin=origin,
            key_facts=extract_key_facts(title, summary, tags), published_at=published))
        seen_links.add(lh); seen_titles.add(th)
        added += 1
    db.session.commit()
    return added


def fetch_all(trigger="manual", source_ids=None):
    """Runs inside an app context. One failing source never stops the others."""
    cfg = current_app.config
    cutoff = datetime.utcnow() - timedelta(hours=cfg["FETCH_WINDOW_HOURS"])
    cats = NewsCategory.query.all()
    q = NewsSource.query.filter_by(is_active=True)
    if source_ids:
        q = q.filter(NewsSource.id.in_(source_ids))
    seen_links, seen_titles = set(), set()
    total, failed = 0, 0
    for s in q.all():
        try:
            n = fetch_source(s, cats, cutoff, seen_links, seen_titles)
            s.last_status, s.last_message = "ok", f"{n} new"
            db.session.add(FetchLog(source_id=s.id, source_name=s.name, status="ok",
                                    message=f"{n} new articles", added=n, trigger=trigger))
            total += n
        except Exception as exc:  # network errors, bad XML, HTTP errors
            db.session.rollback()
            failed += 1
            msg = f"{type(exc).__name__}: {exc}"[:290]
            s = db.session.get(NewsSource, s.id)
            s.last_status, s.last_message = "error", msg
            db.session.add(FetchLog(source_id=s.id, source_name=s.name, status="error",
                                    message=msg, trigger=trigger))
            log.warning("Source %s failed: %s", s.name, msg)
        s.last_fetched_at = datetime.utcnow()
        db.session.commit()
    db.session.add(FetchLog(source_name="(all sources)", status="run", added=total, trigger=trigger,
                            message=f"Run finished: {total} new articles, {failed} source(s) failed"))
    db.session.commit()
    return {"added": total, "failed": failed}
