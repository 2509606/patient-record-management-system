# Tests for the Patient Record Management System
# Uses Flask's test client with mocked MongoDB

import os
import sys
import tempfile
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Mock MongoDB before importing the app
mock_patients = MagicMock()
mock_audit = MagicMock()
mock_login_history = MagicMock()
mock_appointments = MagicMock()
mock_prescriptions = MagicMock()
mock_emergency_contacts = MagicMock()
mock_medical_files = MagicMock()
mock_payments = MagicMock()

mock_patients.count_documents.return_value = 0
mock_appointments.count_documents.return_value = 0
mock_prescriptions.count_documents.return_value = 0


def _make_find_chain(data=None):
    if data is None:
        data = []
    chain = MagicMock()
    chain.sort.return_value = chain
    chain.skip.return_value = chain
    chain.limit.return_value = data
    chain.__iter__ = lambda self: iter(data)
    return chain


mock_patients.find.return_value = _make_find_chain()
mock_medical_files.find.return_value = _make_find_chain()

COLLECTION_MAP = {
    "patients": mock_patients,
    "audit_log": mock_audit,
    "login_history": mock_login_history,
    "appointments": mock_appointments,
    "prescriptions": mock_prescriptions,
    "emergency_contacts": mock_emergency_contacts,
    "medical_files": mock_medical_files,
    "payments": mock_payments,
}

with patch("pymongo.MongoClient") as mock_mongo:
    mock_db = MagicMock()
    mock_mongo.return_value.__getitem__.return_value = mock_db
    mock_db.__getitem__.side_effect = lambda name: COLLECTION_MAP.get(name, MagicMock())

    import app.extensions as ext_module
    ext_module.patients_collection = mock_patients
    ext_module.audit_collection = mock_audit
    ext_module.login_history_collection = mock_login_history
    ext_module.appointments_collection = mock_appointments
    ext_module.prescriptions_collection = mock_prescriptions
    ext_module.emergency_contacts_collection = mock_emergency_contacts
    ext_module.medical_files_collection = mock_medical_files
    ext_module.payments_collection = mock_payments

    from app import create_app
    from app.db import get_db, init_db
    import app.db as db_module

from werkzeug.security import generate_password_hash


@pytest.fixture(autouse=True)
def reset_mocks():
    mock_patients.reset_mock()
    mock_audit.reset_mock()
    mock_login_history.reset_mock()
    mock_appointments.reset_mock()
    mock_prescriptions.reset_mock()
    mock_emergency_contacts.reset_mock()
    mock_medical_files.reset_mock()
    mock_payments.reset_mock()
    mock_patients.count_documents.return_value = 0
    mock_patients.find.return_value = _make_find_chain()
    mock_patients.find_one.return_value = None
    mock_patients.insert_one.return_value = MagicMock(inserted_id="fake_id")
    mock_patients.update_one.return_value = MagicMock(modified_count=1)
    mock_login_history.insert_one.return_value = MagicMock(inserted_id="fake_history_id")
    mock_medical_files.find.return_value = _make_find_chain()
    mock_appointments.count_documents.return_value = 0
    mock_prescriptions.count_documents.return_value = 0


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp()
    original_db = db_module.DATABASE
    db_module.DATABASE = db_path

    test_app = create_app()
    test_app.config["TESTING"] = True

    with test_app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO users (username, email, password, role, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("testadmin", "admin@test.com", generate_password_hash("password123"), "admin", "approved", "2024-01-01"),
        )
        db.execute(
            "INSERT INTO users (username, email, password, role, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("testdoctor", "doc@test.com", generate_password_hash("password123"), "doctor", "approved", "2024-01-01"),
        )
        db.execute(
            "INSERT INTO users (username, email, password, role, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("testnurse", "nurse@test.com", generate_password_hash("password123"), "nurse", "approved", "2024-01-01"),
        )
        db.execute(
            "INSERT INTO users (username, email, password, role, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("testpatient", "patient@test.com", generate_password_hash("password123"), "patient", "approved", "2024-01-01"),
        )
        db.execute(
            "INSERT INTO users (username, email, password, role, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("pendinguser", "pending@test.com", generate_password_hash("password123"), "patient", "pending", "2024-01-01"),
        )
        db.commit()

    yield test_app

    db_module.DATABASE = original_db
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


def login(client, username, password):
    response = client.get("/login")
    html = response.data.decode()
    token_start = html.find('name="csrf_token" value="') + len('name="csrf_token" value="')
    token_end = html.find('"', token_start)
    csrf_token = html[token_start:token_end]
    return client.post("/login", data={
        "username": username,
        "password": password,
        "csrf_token": csrf_token,
    }, follow_redirects=True)


def get_csrf(client, url="/patient/add"):
    response = client.get(url)
    html = response.data.decode()
    token_start = html.find('name="csrf_token" value="') + len('name="csrf_token" value="')
    token_end = html.find('"', token_start)
    return html[token_start:token_end]


# ========== Auth tests ==========

def test_home_redirects_to_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_login_page_loads(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Login" in response.data or b"Sign in" in response.data


def test_signup_page_loads(client):
    response = client.get("/signup")
    assert response.status_code == 200
    assert b"Sign up" in response.data or b"Create Account" in response.data


def test_login_valid_credentials(client):
    response = login(client, "testadmin", "password123")
    assert response.status_code == 200
    assert b"Dashboard" in response.data


def test_login_invalid_credentials(client):
    response = login(client, "testadmin", "wrongpassword")
    assert b"Invalid username or password" in response.data


def test_login_pending_user_blocked(client):
    response = login(client, "pendinguser", "password123")
    assert b"pending approval" in response.data


def test_dashboard_requires_login(client):
    response = client.get("/dashboard")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_logout_clears_session(client):
    login(client, "testadmin", "password123")
    response = client.get("/logout", follow_redirects=True)
    assert b"Sign in" in response.data or b"Login" in response.data
    response = client.get("/dashboard")
    assert response.status_code == 302


# ========== Role-based access tests ==========

def test_admin_can_access_users(client):
    login(client, "testadmin", "password123")
    response = client.get("/admin/users")
    assert response.status_code == 200
    assert b"testadmin" in response.data


def test_doctor_cannot_access_admin_users(client):
    login(client, "testdoctor", "password123")
    response = client.get("/admin/users")
    assert response.status_code == 302
    assert "/dashboard" in response.headers["Location"]


def test_nurse_cannot_add_patient(client):
    login(client, "testnurse", "password123")
    response = client.get("/patient/add")
    assert response.status_code == 302
    assert "/dashboard" in response.headers["Location"]


def test_patient_cannot_access_patients_list(client):
    login(client, "testpatient", "password123")
    response = client.get("/patients")
    assert response.status_code == 302
    assert "/dashboard" in response.headers["Location"]


def test_nurse_can_view_patients_list(client):
    login(client, "testnurse", "password123")
    response = client.get("/patients")
    assert response.status_code == 200


def test_doctor_can_add_patient(client):
    login(client, "testdoctor", "password123")
    response = client.get("/patient/add")
    assert response.status_code == 200
    assert b"Add" in response.data


# ========== Admin approval tests ==========

def test_admin_approvals_page_loads(client):
    login(client, "testadmin", "password123")
    response = client.get("/admin/approvals")
    assert response.status_code == 200
    assert b"pendinguser" in response.data


def test_admin_can_approve_user(client, app):
    login(client, "testadmin", "password123")
    csrf = get_csrf(client, "/admin/approvals")

    with app.app_context():
        db = get_db()
        pending = db.execute("SELECT id FROM users WHERE username = 'pendinguser'").fetchone()
        user_id = pending["id"]

    response = client.post(f"/admin/approve/{user_id}", data={
        "csrf_token": csrf,
    }, follow_redirects=True)
    assert b"approved" in response.data or b"Approved" in response.data


def test_admin_can_reject_user(client, app):
    login(client, "testadmin", "password123")
    csrf = get_csrf(client, "/admin/approvals")

    with app.app_context():
        db = get_db()
        pending = db.execute("SELECT id FROM users WHERE username = 'pendinguser'").fetchone()
        user_id = pending["id"]

    response = client.post(f"/admin/reject/{user_id}", data={
        "csrf_token": csrf,
    }, follow_redirects=True)
    assert response.status_code == 200


# ========== Patient CRUD tests ==========

def test_add_patient_stores_short_id(client):
    login(client, "testadmin", "password123")
    mock_patients.find_one.return_value = None
    csrf = get_csrf(client)
    client.post("/patient/add", data={
        "csrf_token": csrf,
        "age": "45",
        "sex": "Male",
        "blood_pressure": "120/80",
        "cholesterol": "Normal",
        "fasting_blood_sugar": "No",
        "resting_ecg": "Normal",
        "exercise_angina": "No",
    }, follow_redirects=True)
    mock_patients.insert_one.assert_called_once()
    saved = mock_patients.insert_one.call_args[0][0]
    assert saved["patient_id"] == "001"
    assert saved["age"] == 45
    assert saved["status"] == "active"


def test_view_patient_by_short_id(client):
    login(client, "testadmin", "password123")
    mock_patients.find_one.return_value = {
        "_id": "mongo_obj_id",
        "patient_id": "001",
        "age": 45,
        "sex": "Male",
        "blood_pressure": "120/80",
        "cholesterol": "Normal",
        "fasting_blood_sugar": "No",
        "resting_ecg": "Normal",
        "exercise_angina": "No",
        "created_by": 1,
        "created_by_name": "testadmin",
        "created_at": "2024-01-01T00:00:00",
        "status": "active",
    }
    response = client.get("/patient/001")
    assert response.status_code == 200
    assert b"001" in response.data


def test_view_patient_not_found(client):
    login(client, "testadmin", "password123")
    mock_patients.find_one.return_value = None
    response = client.get("/patient/999")
    assert response.status_code == 302
    assert "/patients" in response.headers["Location"]


def test_archive_patient(client):
    login(client, "testadmin", "password123")
    csrf = get_csrf(client)
    response = client.post("/patient/003/archive", data={
        "csrf_token": csrf,
    }, follow_redirects=False)
    assert response.status_code == 302
    mock_patients.update_one.assert_called_once()
    call_args = mock_patients.update_one.call_args[0]
    assert call_args[0] == {"patient_id": "003"}
    assert "archived_at" in call_args[1]["$set"]


def test_nurse_cannot_archive(client):
    login(client, "testnurse", "password123")
    # Get CSRF by accessing any page that has a form
    with client.session_transaction() as sess:
        csrf = sess.get("csrf_token", "")
    response = client.post("/patient/001/archive", data={
        "csrf_token": csrf,
    }, follow_redirects=False)
    assert response.status_code == 302
    assert "/dashboard" in response.headers["Location"]
    mock_patients.update_one.assert_not_called()


def test_archive_logs_audit(client):
    login(client, "testadmin", "password123")
    csrf = get_csrf(client)
    client.post("/patient/007/archive", data={
        "csrf_token": csrf,
    }, follow_redirects=True)
    mock_audit.insert_one.assert_called_once()
    logged = mock_audit.insert_one.call_args[0][0]
    assert logged["patient_id"] == "007"
    assert logged["action"] == "archive"


# ========== Archived patients & restore tests ==========

def test_archived_patients_page(client):
    login(client, "testadmin", "password123")
    mock_patients.count_documents.return_value = 0
    mock_patients.find.return_value = _make_find_chain()
    response = client.get("/patients/archived")
    assert response.status_code == 200


def test_restore_patient(client):
    login(client, "testadmin", "password123")
    # Visit archived page to ensure CSRF token is set
    mock_patients.count_documents.return_value = 0
    mock_patients.find.return_value = _make_find_chain()
    client.get("/patients/archived")
    with client.session_transaction() as sess:
        csrf = sess.get("csrf_token", "")
    mock_patients.update_one.return_value = MagicMock(modified_count=1)
    response = client.post("/patient/001/restore", data={
        "csrf_token": csrf,
    }, follow_redirects=True)
    assert response.status_code == 200
    mock_patients.update_one.assert_called_once()


# ========== Pagination tests ==========

def test_patients_pagination(client):
    login(client, "testadmin", "password123")
    mock_patients.count_documents.return_value = 25
    response = client.get("/patients?page=2")
    assert response.status_code == 200
    find_chain = mock_patients.find.return_value
    find_chain.sort.return_value.skip.assert_called_with(10)


def test_patients_defaults_page_one(client):
    login(client, "testadmin", "password123")
    mock_patients.count_documents.return_value = 5
    response = client.get("/patients")
    assert response.status_code == 200
    find_chain = mock_patients.find.return_value
    find_chain.sort.return_value.skip.assert_called_with(0)


def test_audit_log_pagination(client):
    login(client, "testadmin", "password123")
    mock_audit.count_documents.return_value = 15
    mock_audit.find.return_value = _make_find_chain([])
    response = client.get("/audit?page=1")
    assert response.status_code == 200


# ========== Login history tests ==========

def test_login_creates_history_record(client):
    login(client, "testadmin", "password123")
    mock_login_history.insert_one.assert_called_once()
    record = mock_login_history.insert_one.call_args[0][0]
    assert record["username"] == "testadmin"
    assert record["role"] == "admin"
    assert "ip_address" in record


def test_admin_login_history_page(client):
    login(client, "testadmin", "password123")
    mock_login_history.count_documents.return_value = 0
    mock_login_history.find.return_value = _make_find_chain()
    response = client.get("/admin/login-history")
    assert response.status_code == 200


def test_my_login_history_page(client):
    login(client, "testdoctor", "password123")
    mock_login_history.count_documents.return_value = 0
    mock_login_history.find.return_value = _make_find_chain()
    response = client.get("/my/login-history")
    assert response.status_code == 200


# ========== Signup tests ==========

def test_signup_creates_pending_user(client, app):
    csrf_response = client.get("/signup")
    html = csrf_response.data.decode()
    token_start = html.find('name="csrf_token" value="') + len('name="csrf_token" value="')
    token_end = html.find('"', token_start)
    csrf = html[token_start:token_end]

    response = client.post("/signup", data={
        "csrf_token": csrf,
        "username": "newpatient",
        "email": "newpatient@test.com",
        "password": "password123",
        "confirm_password": "password123",
    }, follow_redirects=True)
    assert b"pending" in response.data or b"approval" in response.data

    with app.app_context():
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = 'newpatient'").fetchone()
        assert user is not None
        assert user["role"] == "patient"
        assert user["status"] == "pending"


# ========== Appointment tests ==========

def test_patient_can_book_appointment(client):
    login(client, "testpatient", "password123")
    response = client.get("/appointment/book")
    assert response.status_code == 200
    assert b"Book" in response.data


def test_appointments_page_loads(client):
    login(client, "testpatient", "password123")
    mock_appointments.count_documents.return_value = 0
    mock_appointments.find.return_value = _make_find_chain()
    response = client.get("/appointments")
    assert response.status_code == 200


def test_doctor_sees_appointments(client):
    login(client, "testdoctor", "password123")
    mock_appointments.count_documents.return_value = 0
    mock_appointments.find.return_value = _make_find_chain()
    response = client.get("/appointments")
    assert response.status_code == 200


# ========== Prescription tests ==========

def test_doctor_can_create_prescription_page(client):
    login(client, "testdoctor", "password123")
    response = client.get("/prescription/create")
    assert response.status_code == 200
    assert b"Prescription" in response.data


def test_nurse_cannot_create_prescription(client):
    login(client, "testnurse", "password123")
    response = client.get("/prescription/create")
    assert response.status_code == 302
    assert "/dashboard" in response.headers["Location"]


def test_prescriptions_page_loads(client):
    login(client, "testpatient", "password123")
    mock_prescriptions.count_documents.return_value = 0
    mock_prescriptions.find.return_value = _make_find_chain()
    response = client.get("/prescriptions")
    assert response.status_code == 200


# ========== Emergency contacts tests ==========

def test_patient_can_view_emergency_contacts(client):
    login(client, "testpatient", "password123")
    mock_emergency_contacts.find.return_value = _make_find_chain()
    response = client.get("/emergency-contacts")
    assert response.status_code == 200


def test_non_patient_cannot_access_emergency_contacts(client):
    login(client, "testdoctor", "password123")
    response = client.get("/emergency-contacts")
    assert response.status_code == 302


# ========== Payment tests ==========

def test_patient_can_view_payments(client):
    login(client, "testpatient", "password123")
    mock_payments.count_documents.return_value = 0
    mock_payments.find.return_value = _make_find_chain()
    response = client.get("/payments")
    assert response.status_code == 200


def test_non_patient_cannot_access_payments(client):
    login(client, "testdoctor", "password123")
    response = client.get("/payments")
    assert response.status_code == 302


# ========== Register user tests ==========

def test_admin_register_page_loads(client):
    login(client, "testadmin", "password123")
    response = client.get("/register")
    assert response.status_code == 200
    assert b"Register" in response.data


def test_admin_register_with_new_roles(client):
    login(client, "testadmin", "password123")
    response = client.get("/register")
    html = response.data.decode()
    assert "doctor" in html.lower()
    assert "nurse" in html.lower()
