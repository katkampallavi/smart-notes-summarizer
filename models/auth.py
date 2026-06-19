import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

DB = "database/smartnotes.db"

def register_user(username, email, password):

    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    hashed_password = generate_password_hash(password)

    cursor.execute(
        """
        INSERT INTO users(username, email, password)
        VALUES (?, ?, ?)
        """,
        (username, email, hashed_password)
    )

    conn.commit()
    conn.close()


def login_user(email, password):

    conn = sqlite3.connect(DB)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT password FROM users WHERE email=?",
        (email,)
    )

    user = cursor.fetchone()

    conn.close()

    if user:
        return check_password_hash(user[0], password)

    return False
