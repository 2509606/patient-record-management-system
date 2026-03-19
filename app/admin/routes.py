# Admin routes: user management, approvals, audit log, login history

from flask import Blueprint, render_template, request, redirect, url_for, flash

from app.auth.decorators import role_required
from app.db import get_db
from app.extensions import audit_collection, login_history_collection

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin/users")
@role_required("admin")
def admin_users():
    page = request.args.get("page", 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page
    search = request.args.get("search", "").strip()

    db = get_db()
    if search:
        total = db.execute(
            "SELECT COUNT(*) FROM users WHERE username LIKE ?",
            (f"%{search}%",),
        ).fetchone()[0]
        total_pages = (total + per_page - 1) // per_page
        users = db.execute(
            "SELECT id, username, email, role, status, created_at FROM users WHERE username LIKE ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (f"%{search}%", per_page, offset),
        ).fetchall()
    else:
        total = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_pages = (total + per_page - 1) // per_page
        users = db.execute(
            "SELECT id, username, email, role, status, created_at FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()

    total_users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_admins = db.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]
    total_doctors = db.execute("SELECT COUNT(*) FROM users WHERE role = 'doctor'").fetchone()[0]
    total_nurses = db.execute("SELECT COUNT(*) FROM users WHERE role = 'nurse'").fetchone()[0]
    total_patients = db.execute("SELECT COUNT(*) FROM users WHERE role = 'patient'").fetchone()[0]

    return render_template(
        "admin_users.html",
        users=users,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search,
        total_users=total_users,
        total_admins=total_admins,
        total_doctors=total_doctors,
        total_nurses=total_nurses,
        total_patients=total_patients,
    )


@admin_bp.route("/admin/approvals")
@role_required("admin")
def admin_approvals():
    page = request.args.get("page", 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM users WHERE status = 'pending'").fetchone()[0]
    total_pages = (total + per_page - 1) // per_page
    pending_users = db.execute(
        "SELECT id, username, email, role, created_at FROM users WHERE status = 'pending' ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (per_page, offset),
    ).fetchall()

    return render_template(
        "admin_approvals.html",
        users=pending_users,
        page=page,
        total_pages=total_pages,
        total=total,
    )


@admin_bp.route("/admin/approve/<int:user_id>", methods=["POST"])
@role_required("admin")
def approve_user(user_id):
    db = get_db()
    db.execute("UPDATE users SET status = 'approved' WHERE id = ? AND status = 'pending'", (user_id,))
    db.commit()
    flash("User approved successfully.", "success")
    return redirect(url_for("admin.admin_approvals"))


@admin_bp.route("/admin/reject/<int:user_id>", methods=["POST"])
@role_required("admin")
def reject_user(user_id):
    db = get_db()
    db.execute("UPDATE users SET status = 'rejected' WHERE id = ? AND status = 'pending'", (user_id,))
    db.commit()
    flash("User registration rejected.", "success")
    return redirect(url_for("admin.admin_approvals"))


@admin_bp.route("/register", methods=["GET", "POST"])
@role_required("admin")
def register():
    if request.method == "POST":
        from werkzeug.security import generate_password_hash
        from datetime import datetime

        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "doctor")

        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template("register.html")

        if role not in ("doctor", "nurse", "admin"):
            flash("Invalid role selected.", "error")
            return render_template("register.html")

        db = get_db()
        existing = db.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            flash("Username already exists.", "error")
            return render_template("register.html")

        db.execute(
            "INSERT INTO users (username, email, password, role, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                username,
                email,
                generate_password_hash(password),
                role,
                "approved",
                datetime.now().isoformat(),
            ),
        )
        db.commit()
        flash(f"User '{username}' registered successfully.", "success")
        return redirect(url_for("admin.admin_users"))

    return render_template("register.html")


@admin_bp.route("/audit")
@role_required("admin")
def audit_log():
    page = request.args.get("page", 1, type=int)
    per_page = 10
    skip = (page - 1) * per_page

    total = audit_collection.count_documents({})
    total_pages = (total + per_page - 1) // per_page
    logs = list(
        audit_collection.find()
        .sort("timestamp", -1)
        .skip(skip)
        .limit(per_page)
    )
    return render_template(
        "audit_log.html",
        logs=logs,
        page=page,
        total_pages=total_pages,
        total=total,
    )


@admin_bp.route("/admin/login-history")
@role_required("admin")
def login_history():
    page = request.args.get("page", 1, type=int)
    per_page = 10
    skip = (page - 1) * per_page

    total = login_history_collection.count_documents({})
    total_pages = (total + per_page - 1) // per_page
    records = list(
        login_history_collection.find()
        .sort("login_at", -1)
        .skip(skip)
        .limit(per_page)
    )
    return render_template(
        "login_history.html",
        records=records,
        page=page,
        total_pages=total_pages,
        total=total,
        view_all=True,
    )


@admin_bp.route("/my/login-history")
def my_login_history():
    from app.auth.decorators import login_required
    from flask import session

    if "user_id" not in session:
        flash("Please log in to access this page.", "error")
        return redirect(url_for("auth.login"))

    page = request.args.get("page", 1, type=int)
    per_page = 10
    skip = (page - 1) * per_page

    query = {"user_id": session["user_id"]}
    total = login_history_collection.count_documents(query)
    total_pages = (total + per_page - 1) // per_page
    records = list(
        login_history_collection.find(query)
        .sort("login_at", -1)
        .skip(skip)
        .limit(per_page)
    )
    return render_template(
        "login_history.html",
        records=records,
        page=page,
        total_pages=total_pages,
        total=total,
        view_all=False,
    )
