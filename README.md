# Karnataka Competitive Exam Preparation Portal

Flask + MySQL (SQLAlchemy) + Bootstrap 5 + Chart.js. Daily RSS news collection at 6:00 AM IST, daily MCQ practice,
subject-wise study material, timed mock tests, and an admin panel.

## What is built (and what to expect)
- **Current affairs**: 26 starter RSS sources (Google News queries, The Hindu, Indian Express, PIB, Deccan Herald,
  Economic Times, Business Standard, BBC). Only items with a publisher date inside the last 24 h are kept; duplicates
  are removed by normalised link and headline; each article keeps its original link, publisher, **published** time and
  separate **fetched** time. Failed feeds are logged and never stop the others.
- **Explanations / key facts** are *extractive*: the feed's own summary plus figures and names found in the headline/summary.
  Nothing is invented. If a feed gives no summary, the card says so and points to the original link.
- **Questions**: 27 starter questions across all 15 subjects (stable facts, explanation for all four options). Add more in
  Admin > Questions. Previous-year questions are **not** seeded - add real ones with a year and exam tag.
- **Optional AI**: with `ANTHROPIC_API_KEY`, news-based MCQs are generated *only from stored article text*, rejected if the
  answer is not in that text, and saved as **pending** until an admin approves. Without a key everything else works.
- **Mock tests**: countdown timer, palette, mark for review, autosave, server-side grading and time check, negative marking,
  per-option explanations, subject-wise accuracy. Negative marking defaults (0.25) are placeholders - verify against the notification.
- Starter study material is brief (one topic per subject). Extend it in Admin > Subjects.

## Windows + VS Code setup
1. Install Python 3.11+ (tick "Add to PATH") and MySQL 8 (MySQL Installer; remember the root password).
2. Open this folder in VS Code, then in the terminal:
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```
3. Edit `.env`: set `SECRET_KEY`, the MySQL password inside `DATABASE_URL`, and `ADMIN_EMAIL` / `ADMIN_PASSWORD`.
4. Create the database (either let `init_db.py` do it, or run this in MySQL Workbench):
```sql
CREATE DATABASE karnataka_exam CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```
5. Create tables and load starter data, then run:
```
python init_db.py
python app.py
```
6. Open http://127.0.0.1:5000 and log in with the admin account. Press **Fetch news now** in Admin to test feeds immediately,
   then check **Admin > Logs / Sources** to see which feeds worked. Replace any feed URL that fails (publishers change them).

## Scheduling
`app.py` starts APScheduler (IST). It runs daily at `FETCH_HOUR:FETCH_MINUTE`, and if the app was not running at 6 AM,
it runs one catch-up fetch ~15 seconds after startup. It only runs while the process is running.

## Keeping updates going when your PC is off
Host the app on an always-on machine: a small VPS (Ubuntu), Render/Railway/Azure App Service, or a PythonAnywhere paid plan
(always-on task). Use managed MySQL or MySQL on the same server, set the `.env` values as environment variables, then run
**one** process (so the job is not scheduled twice):
```
pip install waitress
waitress-serve --listen=0.0.0.0:8000 wsgi:app
```
Run it as a service (systemd on Linux, or NSSM/Task Scheduler "at startup" on a Windows server) and put Nginx/Caddy with HTTPS in
front. Alternative without an in-process scheduler: set `ENABLE_SCHEDULER=0` and trigger the fetch with a server cron
job that runs a small script calling `fetch_all()` inside an app context.

## Project layout
`app.py` app factory · `config.py` settings and exam profiles · `models.py` 17 tables · `scheduler.py` daily job ·
`services/news_fetcher.py` RSS pipeline · `services/ai.py` optional grounded MCQ generation · `routes/` blueprints ·
`templates/`, `static/` UI · `init_db.py` + `seed_data.py` setup · `wsgi.py` production entry.

## Notes
- Google News links are Google redirect links to the publisher's article; the portal stores headlines/summaries only, never full articles.
- Respect each publisher's terms; only add feeds offered for syndication.
- Never commit `.env`.
