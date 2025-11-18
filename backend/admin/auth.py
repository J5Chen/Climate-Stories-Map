import re
from functools import wraps

from flask import redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from repos.repos import get_users_collection


def validate_password_complexity(password):
    if len(password) < 8:
        return False, 'Password must be at least 8 characters long'
    if not re.search(r'[A-Z]', password):
        return False, 'Password must contain at least one uppercase letter'
    if not re.search(r'[a-z]', password):
        return False, 'Password must contain at least one lowercase letter'
    if not re.search(r'[0-9]', password):
        return False, 'Password must contain at least one number'
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False, 'Password must contain at least one special character'
    return True, 'Password meets complexity requirements'


class Auth:
    def __init__(self, app=None):
        self.USERS = get_users_collection()
        self.app = app
        if app:
            self.register_routes(app)

    def create_user(self, username, password, role):
        is_valid, message = validate_password_complexity(password)
        if not is_valid:
            raise ValueError(message)
        hashed = generate_password_hash(password)
        self.USERS.insert_one({'username': username, 'password': hashed, 'role': role})

    def verify_user(self, username, password):
        user = self.USERS.find_one({'username': username})
        if user and check_password_hash(user['password'], password):
            return user
        return None

    def register_routes(self, app):
        @app.route('/login', methods=['GET', 'POST'])
        def login():
            if request.method == 'POST':
                username = request.form.get('username')
                password = request.form.get('password')
                user = self.verify_user(username, password)
                if user:
                    session['user'] = {'username': user['username'], 'role': user['role']}
                    return redirect(url_for('admin.index'))
                return 'Invalid credentials'
            return render_template('login.html')

        @app.route('/logout')
        def logout():
            session.pop('user', None)
            return redirect(url_for('login'))

# ----------------- DECORATORS -----------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            if "user" not in session or session["user"].get("role") != "admin":
                return redirect(url_for("login"))
        except Exception:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return wrapper

def moderator_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            if "user" not in session or session["user"].get("role") not in [
                "admin",
                "moderator",
            ]:
                return redirect(url_for("login"))
        except Exception:
            return redirect(url_for("login"))
        return f(*args, **kwargs)

    return wrapper
