# Fake payment routes (demo only — no real charges)

from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from app.auth.decorators import login_required, role_required
from app.extensions import payments_collection, appointments_collection

payments_bp = Blueprint("payments_bp", __name__)


def generate_payment_id():
    last = payments_collection.find_one(
        {"payment_id": {"$exists": True}},
        sort=[("payment_id", -1)],
    )
    if last and last.get("payment_id"):
        next_num = int(last["payment_id"].replace("PAY", "")) + 1
    else:
        next_num = 1
    return f"PAY{str(next_num).zfill(4)}"


@payments_bp.route("/payments")
@login_required
@role_required("patient")
def payment_history():
    page = request.args.get("page", 1, type=int)
    per_page = 10
    skip = (page - 1) * per_page

    query = {"patient_user_id": session["user_id"]}
    total = payments_collection.count_documents(query)
    total_pages = (total + per_page - 1) // per_page
    pays = list(
        payments_collection.find(query)
        .sort("paid_at", -1)
        .skip(skip)
        .limit(per_page)
    )

    return render_template(
        "payment_history.html",
        payments=pays,
        page=page,
        total_pages=total_pages,
        total=total,
    )


@payments_bp.route("/payment/checkout/<appointment_id>", methods=["GET", "POST"])
@login_required
@role_required("patient")
def checkout(appointment_id):
    appt = appointments_collection.find_one({
        "appointment_id": appointment_id,
        "patient_user_id": session["user_id"],
    })
    if not appt:
        flash("Appointment not found.", "error")
        return redirect(url_for("payments_bp.payment_history"))

    # Check if already paid
    existing = payments_collection.find_one({"appointment_id": appointment_id})
    if existing:
        flash("This appointment has already been paid for.", "error")
        return redirect(url_for("payments_bp.receipt", payment_id=existing["payment_id"]))

    if request.method == "POST":
        card_number = request.form.get("card_number", "").replace(" ", "")
        amount = request.form.get("amount", "50.00")

        if len(card_number) < 4:
            flash("Please enter a valid card number.", "error")
            return render_template("checkout.html", appointment=appt)

        payment = {
            "payment_id": generate_payment_id(),
            "patient_user_id": session["user_id"],
            "appointment_id": appointment_id,
            "amount": float(amount),
            "status": "completed",
            "card_last_four": card_number[-4:],
            "paid_at": datetime.now().isoformat(),
        }
        payments_collection.insert_one(payment)
        flash("Payment processed successfully (demo).", "success")
        return redirect(url_for("payments_bp.receipt", payment_id=payment["payment_id"]))

    return render_template("checkout.html", appointment=appt)


@payments_bp.route("/payment/receipt/<payment_id>")
@login_required
@role_required("patient")
def receipt(payment_id):
    payment = payments_collection.find_one({
        "payment_id": payment_id,
        "patient_user_id": session["user_id"],
    })
    if not payment:
        flash("Payment not found.", "error")
        return redirect(url_for("payments_bp.payment_history"))

    return render_template("receipt.html", payment=payment)
