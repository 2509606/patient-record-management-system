# Authentication routes: login, logout, signup

from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

from app.db import get_db
from app.extensions import login_history_collection

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

        if user and check_password_hash(user["password"], password):
            # Check if account is approved
            status = user["status"] if "status" in user.keys() else "approved"
            if status == "pending":
                flash("Your account is pending approval by an administrator.", "error")
                return render_template("login.html")
            if status == "rejected":
                flash("Your account registration has been rejected.", "error")
                return render_template("login.html")

            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]

            # Record login history
            record = login_history_collection.insert_one({
                "user_id": user["id"],
                "username": user["username"],
                "role": user["role"],
                "login_at": datetime.now().isoformat(),
                "logout_at": None,
                "duration_seconds": None,
                "ip_address": request.remote_addr or "unknown",
            })
            session["login_history_id"] = str(record.inserted_id)

            flash("Logged in successfully.", "success")
            return redirect(url_for("main.dashboard"))
        else:
            flash("Invalid username or password.", "error")

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    # Update login history with logout time
    from bson import ObjectId
    history_id = session.get("login_history_id")
    if history_id:
        try:
            oid = ObjectId(history_id)
        except Exception:
            oid = None
        record = login_history_collection.find_one({"_id": oid}) if oid else None
        if record and record.get("login_at"):
            login_at = datetime.fromisoformat(record["login_at"])
            now = datetime.now()
            duration = int((now - login_at).total_seconds())
            login_history_collection.update_one(
                {"_id": ObjectId(history_id)},
                {"$set": {"logout_at": now.isoformat(), "duration_seconds": duration}}
            )

    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username or not email or not password:
            flash("All fields are required.", "error")
            return render_template("signup.html")

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("signup.html")

        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("signup.html")

        db = get_db()
        existing = db.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            flash("Username already exists.", "error")
            return render_template("signup.html")

        db.execute(
            "INSERT INTO users (username, email, password, role, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                username,
                email,
                generate_password_hash(password),
                "patient",
                "pending",
                datetime.now().isoformat(),
            ),
        )
        db.commit()
        flash("Registration submitted. Please wait for admin approval.", "success")
        return redirect(url_for("auth.login"))

    return render_template("signup.html")
