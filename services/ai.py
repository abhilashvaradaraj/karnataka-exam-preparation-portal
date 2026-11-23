"""Optional AI helper. The portal works fully without it.

Questions are generated ONLY from a stored article's title + feed summary, then
rejected unless the stated correct answer is found in that source text.
Accepted questions are saved as *unapproved*; an admin must approve them."""
import json
import logging
import re

import requests
from flask import current_app

from models import NewsArticle, Option, Question, db
from services.text_utils import clean, norm_title, sha

log = logging.getLogger(__name__)
PROMPT = """You write competitive-exam MCQs. Use ONLY the article text below. Do not add outside facts.
If the text does not contain a clear, testable fact, reply exactly: {{"skip": true}}
Reply with JSON only: {{"question": str, "options": [4 strings], "correct_index": 0-3,
"explanations": [4 strings, one per option, each citing the article], "difficulty": "Easy|Medium|Hard"}}
The correct option's text must appear in the article text.

Article title: {title}
Article summary: {summary}"""


def _grounded(answer, source_text):
    a = norm_title(answer)
    s = norm_title(source_text)
    if not a:
        return False
    if a in s:
        return True
    toks = [t for t in a.split() if len(t) > 2]
    return bool(toks) and sum(t in s.split() for t in toks) / len(toks) >= 0.8


def _call(prompt):
    cfg = current_app.config
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": cfg["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": cfg["ANTHROPIC_MODEL"], "max_tokens": 900,
              "messages": [{"role": "user", "content": prompt}]}, timeout=60)
    r.raise_for_status()
    text = "".join(b.get("text", "") for b in r.json().get("content", []))
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0)) if m else {}


def generate_questions(limit=None):
    cfg = current_app.config
    if not cfg["ANTHROPIC_API_KEY"]:
        return {"created": 0, "note": "ANTHROPIC_API_KEY not set - AI generation skipped"}
    limit = limit or cfg["AI_MAX_PER_RUN"]
    used = {a for (a,) in db.session.query(Question.article_id).filter(Question.article_id.isnot(None))}
    arts = (NewsArticle.query.order_by(NewsArticle.published_at.desc()).limit(limit * 3).all())
    created = 0
    for art in arts:
        if created >= limit:
            break
        if art.id in used or len(art.summary or "") < 60:
            continue
        try:
            d = _call(PROMPT.format(title=art.title, summary=art.summary))
            if d.get("skip"):
                continue
            opts, ci, exps = d["options"], int(d["correct_index"]), d["explanations"]
            if len(opts) != 4 or len(exps) != 4 or not 0 <= ci <= 3 or len(set(opts)) != 4:
                continue
            if not _grounded(opts[ci], f"{art.title} {art.summary}"):
                continue  # unsupported answer -> rejected
            h = sha(norm_title(d["question"]))
            if Question.query.filter_by(text_hash=h).first():
                continue
            q = Question(text=clean(d["question"]), text_hash=h, article_id=art.id,
                         news_category_id=art.category_id, origin="ai", is_approved=False,
                         difficulty=d.get("difficulty") if d.get("difficulty") in ("Easy", "Medium", "Hard") else "Medium")
            for i, lab in enumerate("ABCD"):
                q.options.append(Option(label=lab, text=str(opts[i])[:500],
                                        explanation=str(exps[i]), is_correct=(i == ci)))
            db.session.add(q)
            db.session.commit()
            created += 1
        except Exception as exc:
            db.session.rollback()
            log.warning("AI question failed for article %s: %s", art.id, exc)
    return {"created": created, "note": "Saved as unapproved - review in Admin > Questions"}
