import logging
import os

from flask import Flask, render_template
from flask_login import LoginManager

from config import Config
from models import User, db
from utils import to_ist

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
login_manager = LoginManager()


def create_app(config=Config):
    app = Flask(__name__)
    app.config.from_object(config)
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to continue."

    @login_manager.user_loader
    def load_user(uid):
        return db.session.get(User, int(uid))

    from routes.admin import bp as admin_bp
    from routes.auth import bp as auth_bp
    from routes.main import bp as main_bp
    from routes.quiz import bp as quiz_bp
    from routes.subjects import bp as subjects_bp
    from routes.tests import bp as tests_bp
    for b in (main_bp, auth_bp, quiz_bp, subjects_bp, tests_bp, admin_bp):
        app.register_blueprint(b)

    @app.template_filter("ist")
    def ist_filter(dt, fmt="%d %b %Y, %I:%M %p"):
        d = to_ist(dt)
        return d.strftime(fmt) if d else "—"

    @app.template_filter("lines")
    def lines_filter(text):
        return [l.strip() for l in (text or "").splitlines() if l.strip()]

    @app.errorhandler(403)
    def forbidden(_):
        return render_template("error.html", code=403, msg="You do not have access to this page."), 403

    @app.errorhandler(404)
    def not_found(_):
        return render_template("error.html", code=404, msg="That page does not exist."), 404

    @app.errorhandler(500)
    def server_error(_):
        db.session.rollback()
        return render_template("error.html", code=500, msg="Something went wrong on our side. Please try again."), 500

    return app


app = create_app()

if __name__ == "__main__":
    from scheduler import init_scheduler
    # Reloader off: otherwise the scheduler would start twice.
    init_scheduler(app)
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False, use_reloader=False)
