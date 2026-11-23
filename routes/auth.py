import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user

from models import User, db

bp = Blueprint("auth", __name__)
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def safe_next(target):
    return target if target and target.startswith("/") and not target.startswith("//") else url_for("main.dashboard")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        pw = request.form.get("password", "")
        errors = []
        if not 2 <= len(name) <= 80:
            errors.append("Enter your name (2-80 characters).")
        if not EMAIL.match(email) or len(email) > 120:
            errors.append("Enter a valid email address.")
        if len(pw) < 8:
            errors.append("Password must be at least 8 characters.")
        if not errors and User.query.filter_by(email=email).first():
            errors.append("An account with this email already exists. Log in instead.")
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("auth.html", mode="register", name=name, email=email), 400
        u = User(name=name, email=email)
        u.set_password(pw)
        db.session.add(u)
        db.session.commit()
        login_user(u)
        flash("Welcome! Your account is ready.", "success")
        return redirect(url_for("main.dashboard"))
    return render_template("auth.html", mode="register")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        u = User.query.filter_by(email=email).first()
        if u and u.check_password(request.form.get("password", "")):
            login_user(u, remember=bool(request.form.get("remember")))
            return redirect(safe_next(request.args.get("next")))
        flash("Email or password is incorrect.", "danger")
        return render_template("auth.html", mode="login", email=email), 401
    return render_template("auth.html", mode="login")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.dashboard"))
