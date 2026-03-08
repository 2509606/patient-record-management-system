# I need to test that the key features of my app work correctly
# I'll use Flask's built-in test client so I don't need a real server running
# Since MongoDB might not be running during tests, I'll mock the MongoDB calls

import os
import sys
import tempfile
from unittest.mock import patch, MagicMock
import pytest

# I need to add the project root to the path so I can import app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# I need to mock MongoDB before importing the app so it doesn't try to connect
mock_patients = MagicMock()
mock_audit = MagicMock()
mock_patients.count_documents.return_value = 0
mock_patients.find.return_value.sort.return_value = []

with patch("pymongo.MongoClient") as mock_mongo:
    mock_db = MagicMock()
    mock_mongo.return_value.__getitem__.return_value = mock_db
    mock_db.__getitem__.side_effect = lambda name: mock_patients if name == "patients" else mock_audit

    from app import app, get_db, init_db
    import app as app_module

from werkzeug.security import generate_password_hash

# I'll point the mock collections to the app module so routes use them
app_module.patients_collection = mock_patients
app_module.audit_collection = mock_audit


@pytest.fixture(autouse=True)
def reset_mocks():
    # I want to reset mock call counts between tests
    mock_patients.reset_mock()
    mock_audit.reset_mock()
    mock_patients.count_documents.return_value = 0
    mock_patients.find.return_value.sort.return_value = []


@pytest.fixture
def client():
    # I'll use a temporary database for testing so I don't mess up real data
    app.config["TESTING"] = True
    db_fd, db_path = tempfile.mkstemp()

    original_db = app_module.DATABASE
    app_module.DATABASE = db_path

    with app.test_client() as client:
        with app.app_context():
            init_db()
            # I'll create a test admin and clinician user
            db = get_db()
            db.execute(
                "INSERT INTO users (username, password, role, created_at) VALUES (?, ?, ?, ?)",
                ("testadmin", generate_password_hash("password123"), "admin", "2024-01-01"),
            )
            db.execute(
                "INSERT INTO users (username, password, role, created_at) VALUES (?, ?, ?, ?)",
                ("testclinician", generate_password_hash("password123"), "clinician", "2024-01-01"),
            )
            db.commit()
        yield client

    app_module.DATABASE = original_db
    os.close(db_fd)
    os.unlink(db_path)


def login(client, username, password):
    # I need a helper function to log in during tests
    # First get the login page to get a CSRF token
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


# Test 1: Home page should redirect to login when not logged in
def test_home_redirects_to_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# Test 2: Login page should load successfully
def test_login_page_loads(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Login" in response.data


# Test 3: Register page should load when logged in as admin
def test_register_page_loads_for_admin(client):
    login(client, "testadmin", "password123")
    response = client.get("/register")
    assert response.status_code == 200
    assert b"Register" in response.data


# Test 4: Login with valid credentials should work
def test_login_valid_credentials(client):
    response = login(client, "testadmin", "password123")
    assert response.status_code == 200
    assert b"Dashboard" in response.data


# Test 5: Login with invalid credentials should fail
def test_login_invalid_credentials(client):
    response = login(client, "testadmin", "wrongpassword")
    assert b"Invalid username or password" in response.data


# Test 6: Dashboard should require login
def test_dashboard_requires_login(client):
    response = client.get("/dashboard")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# Test 7: Logout should clear the session
def test_logout_clears_session(client):
    login(client, "testadmin", "password123")
    response = client.get("/logout", follow_redirects=True)
    assert b"Login" in response.data
    # I should verify that the dashboard is no longer accessible
    response = client.get("/dashboard")
    assert response.status_code == 302


# Test 8: Patient add page should require login
def test_add_patient_requires_login(client):
    response = client.get("/patient/add")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
