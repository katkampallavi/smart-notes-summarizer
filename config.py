import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'smart-notes-secret-key-2024-change-in-production'
    DATABASE = os.path.join(BASE_DIR, 'database.db')
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    EXPORT_FOLDER = os.path.join(BASE_DIR, 'exports')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload
    ALLOWED_EXTENSIONS = {'pdf', 'docx', 'pptx'}
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    SESSION_PERMANENT = True

    # NLP settings
    SUMMARY_MAX_LENGTH = 500
    SUMMARY_MIN_LENGTH = 100
    MAX_KEYWORDS = 10

    @staticmethod
    def init_app(app):
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.EXPORT_FOLDER, exist_ok=True)