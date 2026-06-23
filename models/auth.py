import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config


class User:
    def __init__(self, id, username, email, password=None):
        self.id = id
        self.username = username
        self.email = email
        self.password = password
        self.is_authenticated = True
        self.is_active = True
        self.is_anonymous = False

    def get_id(self):
        return str(self.id)

    @staticmethod
    def get_db():
        conn = sqlite3.connect(Config.DATABASE)
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def get_by_id(cls, user_id):
        conn = cls.get_db()
        try:
            user = conn.execute(
                'SELECT * FROM users WHERE id = ?', (user_id,)
            ).fetchone()
            if user:
                return cls(
                    id=user['id'],
                    username=user['username'],
                    email=user['email'],
                    password=user['password']
                )
            return None
        finally:
            conn.close()

    @classmethod
    def get_by_username(cls, username):
        conn = cls.get_db()
        try:
            user = conn.execute(
                'SELECT * FROM users WHERE username = ?', (username,)
            ).fetchone()
            if user:
                return cls(
                    id=user['id'],
                    username=user['username'],
                    email=user['email'],
                    password=user['password']
                )
            return None
        finally:
            conn.close()

    @classmethod
    def get_by_email(cls, email):
        conn = cls.get_db()
        try:
            user = conn.execute(
                'SELECT * FROM users WHERE email = ?', (email,)
            ).fetchone()
            if user:
                return cls(
                    id=user['id'],
                    username=user['username'],
                    email=user['email'],
                    password=user['password']
                )
            return None
        finally:
            conn.close()

    @classmethod
    def register(cls, username, email, password):
        conn = cls.get_db()
        try:
            existing_user = conn.execute(
                'SELECT id FROM users WHERE username = ? OR email = ?',
                (username, email)
            ).fetchone()
            if existing_user:
                return None, "Username or email already exists."

            hashed_password = generate_password_hash(password)
            conn.execute(
                'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                (username, email, hashed_password)
            )
            conn.commit()
            user = cls.get_by_username(username)
            return user, None
        except Exception as e:
            return None, str(e)
        finally:
            conn.close()

    @classmethod
    def login(cls, username, password):
        user = cls.get_by_username(username)
        if user and check_password_hash(user.password, password):
            return user, None
        return None, "Invalid username or password."

    @classmethod
    def get_total_users(cls):
        conn = cls.get_db()
        try:
            result = conn.execute('SELECT COUNT(*) as count FROM users').fetchone()
            return result['count'] if result else 0
        finally:
            conn.close()


class AnonymousUser:
    """Represents a non-authenticated user for template compatibility."""
    is_authenticated = False
    is_active = False
    is_anonymous = True
    username = None
    id = None

    def get_id(self):
        return None