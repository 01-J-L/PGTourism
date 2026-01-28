from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from .models import User
from . import db

auth = Blueprint("auth", __name__)

@auth.route("/login", methods=["GET", "POST"])
def login():
    # If already logged in, redirect based on role
    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for("views.dashboard"))
        return redirect(url_for("views.home"))

    if request.method == "POST":
        email = request.form.get("email", "").strip() # Removed .lower() to allow 'admin'
        pw    = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        
        # Check password
        if user and check_password_hash(user.password, pw):
            login_user(user, remember=True)
            if user.is_admin:
                return redirect(url_for("views.dashboard"))
            return redirect(url_for("views.home"))
        else:
            flash("Invalid username or password.", "error")

    return render_template("login.html")

@auth.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("views.home"))