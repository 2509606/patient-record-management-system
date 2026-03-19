# Main routes: index redirect and dashboard

from flask import Blueprint, render_template, redirect, url_for, session

from app.auth.decorators import login_required
from app.extensions import patients_collection, appointments_collection, prescriptions_collection

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("auth.login"))


@main_bp.route("/dashboard")
@login_required
def dashboard():
    patient_count = patients_collection.count_documents({"status": "active"})
    role = session.get("role")

    # Role-specific stats
    stats = {"patient_count": patient_count}

    if role == "patient":
        user_id = session["user_id"]
        stats["my_appointments"] = appointments_collection.count_documents({
            "patient_user_id": user_id, "status": {"$ne": "cancelled"}
        })
        stats["my_prescriptions"] = prescriptions_collection.count_documents({
            "patient_user_id": user_id
        })
    elif role in ("doctor", "nurse"):
        stats["pending_appointments"] = appointments_collection.count_documents({
            "status": "pending"
        })

    return render_template("dashboard.html", **stats)
