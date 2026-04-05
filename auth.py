"""
Authentication Module
Handles user registration, login, and session management
using SQLite database and password hashing.
"""

import sqlite3
import os
from pathlib import Path
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from flask import session, redirect, url_for, request

DB_PATH = Path(__file__).parent / 'users.db'


def init_db():
    """Initialize the users database."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fullname TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def register_user(fullname, email, password):
    """
    Register a new user.
    Returns (success: bool, message: str)
    """
    if not fullname or not email or not password:
        return False, 'All fields are required'

    if len(password) < 6:
        return False, 'Password must be at least 6 characters'

    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    try:
        hashed = generate_password_hash(password)
        c.execute(
            'INSERT INTO users (fullname, email, password) VALUES (?, ?, ?)',
            (fullname.strip(), email.strip().lower(), hashed)
        )
        conn.commit()
        return True, 'Account created successfully'
    except sqlite3.IntegrityError:
        return False, 'Email already registered'
    finally:
        conn.close()


def authenticate_user(email, password):
    """
    Authenticate a user by email and password.
    Returns (success: bool, user_dict or error_message)
    """
    if not email or not password:
        return False, 'Email and password are required'

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE email = ?', (email.strip().lower(),))
    user = c.fetchone()
    conn.close()

    if user is None:
        return False, 'Invalid email or password'

    if not check_password_hash(user['password'], password):
        return False, 'Invalid email or password'

    return True, {
        'id': user['id'],
        'fullname': user['fullname'],
        'email': user['email'],
    }


def login_required(f):
    """Decorator to protect routes that require authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated


def get_current_user():
    """Get current logged-in user info from session."""
    if 'user_id' in session:
        return {
            'id': session['user_id'],
            'fullname': session.get('user_name', ''),
            'email': session.get('user_email', ''),
        }
    return None
