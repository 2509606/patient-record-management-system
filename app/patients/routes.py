# Patient CRUD routes

import os
import re
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from app.auth.decorators import login_required, role_required
from app.extensions import patients_collection, log_action

patients_bp = Blueprint("patients_bp", __name__)

ARCHIVE_RETENTION_DAYS = int(os.environ.get("ARCHIVE_RETENTION_DAYS", "30"))


def validate_patient_form(form):
    errors = []
    age = form.get("age", "").strip()
    blood_pressure = form.get("blood_pressure", "").strip()

    if not age:
        errors.append("Age is required.")
    else:
        try:
            age_int = int(age)
            if age_int < 0 or age_int > 150:
                errors.append("Age must be between 0 and 150.")
        except ValueError:
            errors.append("Age must be a number.")

    if not form.get("sex"):
        errors.append("Sex is required.")

    if blood_pressure and not re.match(r"^\d{2,3}/\d{2,3}$", blood_pressure):
        errors.append("Blood pressure must be in the format 120/80.")

    return errors


def generate_patient_id():
    last = patients_collection.find_one(
        {"patient_id": {"$exists": True}},
        sort=[("patient_id", -1)],
    )
    if last and last.get("patient_id"):
        next_num = int(last["patient_id"]) + 1
    else:
        next_num = 1
    return str(next_num).zfill(3)


@patients_bp.route("/patients")
@login_required
@role_required("admin", "doctor", "nurse")
def patients():
    page = request.args.get("page", 1, type=int)
    per_page = 10
    skip = (page - 1) * per_page
    search = request.args.get("search", "").strip()

    query = {"status": "active"}
    if search:
        query["patient_id"] = {"$regex": re.escape(search), "$options": "i"}

    total = patients_collection.count_documents(query)
    total_pages = (total + per_page - 1) // per_page
    all_patients = list(
        patients_collection.find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(per_page)
    )
    total_active = patients_collection.count_documents({"status": "active"})
    total_archived = patients_collection.count_documents({"status": "archived"})

    return render_template(
        "patients.html",
        patients=all_patients,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search,
        total_active=total_active,
        total_archived=total_archived,
    )


@patients_bp.route("/patient/add", methods=["GET", "POST"])
@login_required
@role_required("admin", "doctor")
def add_patient():
    if request.method == "POST":
        patient = {
            "patient_id": generate_patient_id(),
            "age": request.form.get("age", "").strip(),
            "sex": request.form.get("sex", ""),
            "blood_pressure": request.form.get("blood_pressure", "").strip(),
            "cholesterol": request.form.get("cholesterol", ""),
            "fasting_blood_sugar": request.form.get("fasting_blood_sugar", ""),
            "resting_ecg": request.form.get("resting_ecg", ""),
            "exercise_angina": request.form.get("exercise_angina", ""),
            "created_by": session["user_id"],
            "created_by_name": session["username"],
            "created_at": datetime.now().isoformat(),
            "status": "active",
        }

        errors = validate_patient_form(request.form)
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("add_patient.html")

        patient["age"] = int(patient["age"])
        patients_collection.insert_one(patient)
        log_action(session["user_id"], session["username"], "create", patient["patient_id"])
        flash("Patient record added successfully.", "success")
        return redirect(url_for("patients_bp.patients"))

    return render_template("add_patient.html")


@patients_bp.route("/patient/<patient_id>")
@login_required
@role_required("admin", "doctor", "nurse")
def view_patient(patient_id):
    patient = patients_collection.find_one({"patient_id": patient_id})
    if not patient:
        flash("Patient not found.", "error")
        return redirect(url_for("patients_bp.patients"))

    log_action(session["user_id"], session["username"], "view", patient_id)

    # Get medical files for this patient
    from app.extensions import medical_files_collection
    files = list(medical_files_collection.find({"patient_id": patient_id}).sort("uploaded_at", -1))

    return render_template("view_patient.html", patient=patient, medical_files=files)


@patients_bp.route("/patient/<patient_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin", "doctor")
def edit_patient(patient_id):
    patient = patients_collection.find_one({"patient_id": patient_id})
    if not patient:
        flash("Patient not found.", "error")
        return redirect(url_for("patients_bp.patients"))

    if request.method == "POST":
        updated = {
            "age": request.form.get("age", "").strip(),
            "sex": request.form.get("sex", ""),
            "blood_pressure": request.form.get("blood_pressure", "").strip(),
            "cholesterol": request.form.get("cholesterol", ""),
            "fasting_blood_sugar": request.form.get("fasting_blood_sugar", ""),
            "resting_ecg": request.form.get("resting_ecg", ""),
            "exercise_angina": request.form.get("exercise_angina", ""),
        }

        errors = validate_patient_form(request.form)
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("edit_patient.html", patient=patient)

        updated["age"] = int(updated["age"])
        patients_collection.update_one(
            {"patient_id": patient_id},
            {"$set": updated}
        )
        log_action(session["user_id"], session["username"], "edit", patient_id)
        flash("Patient record updated successfully.", "success")
        return redirect(url_for("patients_bp.view_patient", patient_id=patient_id))

    return render_template("edit_patient.html", patient=patient)


@patients_bp.route("/patient/<patient_id>/archive", methods=["POST"])
@role_required("admin")
def archive_patient(patient_id):
    result = patients_collection.update_one(
        {"patient_id": patient_id},
        {"$set": {"status": "archived", "archived_at": datetime.now().isoformat()}}
    )
    if result.modified_count == 0:
        flash("Patient not found.", "error")
    else:
        log_action(session["user_id"], session["username"], "archive", patient_id)
        flash("Patient record archived.", "success")
    return redirect(url_for("patients_bp.patients"))


@patients_bp.route("/patients/archived")
@role_required("admin")
def archived_patients():
    # Purge expired archived records
    cutoff = (datetime.now() - timedelta(days=ARCHIVE_RETENTION_DAYS)).isoformat()
    patients_collection.delete_many({
        "status": "archived",
        "archived_at": {"$lt": cutoff, "$exists": True}
    })

    page = request.args.get("page", 1, type=int)
    per_page = 10
    skip = (page - 1) * per_page

    query = {"status": "archived"}
    total = patients_collection.count_documents(query)
    total_pages = (total + per_page - 1) // per_page
    archived = list(
        patients_collection.find(query)
        .sort("archived_at", -1)
        .skip(skip)
        .limit(per_page)
    )

    # Calculate days remaining for each
    now = datetime.now()
    for p in archived:
        if p.get("archived_at"):
            archived_dt = datetime.fromisoformat(p["archived_at"])
            expiry = archived_dt + timedelta(days=ARCHIVE_RETENTION_DAYS)
            p["days_remaining"] = max(0, (expiry - now).days)
        else:
            p["days_remaining"] = ARCHIVE_RETENTION_DAYS

    return render_template(
        "archived_patients.html",
        patients=archived,
        page=page,
        total_pages=total_pages,
        total=total,
        retention_days=ARCHIVE_RETENTION_DAYS,
    )


@patients_bp.route("/patient/<patient_id>/restore", methods=["POST"])
@role_required("admin")
def restore_patient(patient_id):
    result = patients_collection.update_one(
        {"patient_id": patient_id, "status": "archived"},
        {"$set": {"status": "active"}, "$unset": {"archived_at": ""}}
    )
    if result.modified_count == 0:
        flash("Patient not found or not archived.", "error")
    else:
        log_action(session["user_id"], session["username"], "restore", patient_id)
        flash("Patient record restored.", "success")
    return redirect(url_for("patients_bp.archived_patients"))
