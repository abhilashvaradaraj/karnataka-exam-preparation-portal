import hashlib
import html
import re

TAG = re.compile(r"<[^>]+>")
NUM_FACT = re.compile(
    r"(?:₹|Rs\.?\s?|US\$|\$)\s?[\d,\.]+(?:\s?(?:crore|lakh|billion|million|trillion|bn|mn)){0,2}"
    r"|\b\d[\d,\.]*\s?(?:%|per cent|crore|lakh|billion|million|trillion|km|MW|GW|tonnes|years?)\b"
)
PHRASE = re.compile(r"\b[A-Z][A-Za-z\.]+(?:\s+(?:(?:of|for|and|the)\s+)?[A-Z][A-Za-z\.]+){1,4}")


def clean(text, limit=None):
    text = html.unescape(TAG.sub(" ", text or ""))
    text = re.sub(r"\s+", " ", text).strip()
    if limit and len(text) > limit:
        cut = text[:limit].rsplit(" ", 1)[0]
        text = cut.rstrip(",;:") + "…"
    return text


def sha(s):
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def norm_title(title):
    t = (title or "").lower()
    t = re.sub(r"\s[-|–—]\s[^-|–—]{2,60}$", "", t)  # drop trailing " - Publisher"
    return re.sub(r"[^a-z0-9\u0c80-\u0cff]+", " ", t).strip()


def extract_key_facts(title, summary, tags=()):
    """Rule-based, extractive only: pulls figures and named entities that are
    literally present in the title/summary. Nothing is invented."""
    text = f"{title}. {summary or ''}"
    facts = []
    for m in NUM_FACT.finditer(text):
        v = m.group(0).strip()
        if v not in facts:
            facts.append(v)
    names = []
    for m in PHRASE.finditer(title or ""):
        v = m.group(0).strip()
        if len(v.split()) >= 2 and v not in names:
            names.append(v)
    out = []
    if names:
        out.append("Names/terms to note: " + "; ".join(names[:4]))
    if facts:
        out.append("Figures mentioned: " + "; ".join(facts[:4]))
    if tags:
        out.append("Exam topics: " + ", ".join(tags[:3]))
    return "\n".join(out)


def simple_explanation(title, summary, publisher):
    """Returns (text, origin). Uses the feed's own summary if it adds
    information; otherwise a neutral pointer to the source (never invented)."""
    s = clean(summary)
    nt = norm_title(title)
    if len(s) >= 50 and norm_title(s)[:60] != nt[:60]:
        sentences = re.split(r"(?<=[.!?])\s+", s)
        return " ".join(sentences[:2])[:380], "feed"
    return (f"Reported by {publisher or 'the source'}: {clean(title)}. "
            f"Open the original link for the full report."), "title"
