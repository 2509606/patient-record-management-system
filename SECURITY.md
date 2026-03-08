# Security Documentation

## STRIDE Threat Model

I used the STRIDE framework to identify potential threats to the system and think about how to mitigate them.

| STRIDE Category | Threat Description | Mitigation |
|---|---|---|
| **Spoofing** | An attacker could pretend to be a legitimate user by guessing or stealing credentials. | I implemented session-based authentication with `login_required` and `admin_required` decorators. Users must log in with a valid username and password before accessing any protected page. |
| **Tampering** | An attacker could submit forged requests to modify patient data without the user's knowledge (CSRF attacks). | I implemented CSRF tokens using `secrets.token_hex()`. Every form includes a hidden token that is validated on the server before processing any POST request. |
| **Repudiation** | A user could deny performing an action on a patient record, and there would be no way to prove otherwise. | I implemented an audit log that records every patient action (create, view, edit, archive) along with the user who performed it and a timestamp. Admins can review this log. |
| **Information Disclosure** | If the database is compromised, an attacker could read plaintext passwords and use them to access accounts. | I hash all passwords using `werkzeug.security.generate_password_hash()` before storing them. Even if the database is accessed, the original passwords cannot be recovered. |
| **Denial of Service** | An attacker could flood the login page with requests to overwhelm the server. | This is acknowledged as a risk. In a production system, I would add rate limiting to the login route. For this prototype, the risk is accepted. |
| **Elevation of Privilege** | A clinician user could try to access admin-only pages like user management or the audit log. | I implemented role-based access control using the `admin_required` decorator, which checks the user's role stored in the session. Admin routes reject non-admin users with an error message. |

## Security Techniques Implemented

### 1. Password Hashing

**What it is:** Instead of storing passwords as plain text, I convert them into an irreversible hash before saving them to the database.

**How I implemented it:** I used `werkzeug.security.generate_password_hash()` when creating user accounts and `check_password_hash()` when verifying login attempts. Werkzeug is included with Flask so I didn't need any extra libraries.

```python
# When registering a new user
hashed = generate_password_hash(password)
db.execute("INSERT INTO users ... VALUES (?, ?, ...)", (username, hashed, ...))

# When logging in
user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
if user and check_password_hash(user["password"], password):
    # login successful
```

**STRIDE threat mitigated:** Information Disclosure - even if an attacker gains access to the database, they cannot read the original passwords.

### 2. CSRF Protection

**What it is:** Cross-Site Request Forgery (CSRF) is an attack where a malicious website tricks a user's browser into submitting a form to my application without their knowledge.

**How I implemented it:** I generate a random token using `secrets.token_hex(16)` and store it in the user's session. Every form includes this token as a hidden field. When a POST request comes in, the `before_request` handler checks that the submitted token matches the one in the session.

```python
# Generate token and store in session
def generate_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    return session["csrf_token"]

# Validate on every POST request
@app.before_request
def check_csrf():
    if request.method == "POST":
        token = session.get("csrf_token")
        form_token = request.form.get("csrf_token")
        if not token or token != form_token:
            flash("Invalid form submission.", "error")
            return redirect(request.url)
```

**STRIDE threat mitigated:** Tampering - attackers cannot forge valid form submissions because they don't have access to the CSRF token stored in the user's session.

### 3. Session-Based Authentication and Authorisation

**What it is:** I use Flask's built-in session management to track who is logged in and what role they have. This controls access to different parts of the application.

**How I implemented it:** When a user logs in successfully, I store their user ID, username, and role in the session. I created two decorators - `login_required` checks if a user is logged in, and `admin_required` additionally checks if they have the admin role.

```python
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("role") != "admin":
            flash("You do not have permission.", "error")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated_function
```

**STRIDE threats mitigated:**
- Spoofing - users cannot access protected pages without authenticating first
- Elevation of Privilege - clinician users cannot access admin-only features because the `admin_required` decorator checks their role
