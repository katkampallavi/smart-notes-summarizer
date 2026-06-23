import os
import json
import sqlite3
import traceback
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, jsonify, send_file, g
)
from werkzeug.utils import secure_filename

from config import Config
from models.auth import User, AnonymousUser
from models.summarizer import Summarizer
from models.keyword_extractor import KeywordExtractor
from utils.pdf_reader import extract_text_from_pdf
from utils.docx_reader import extract_text_from_docx
from utils.ppt_reader import extract_text_from_pptx
from utils.pdf_export import generate_summary_pdf, generate_all_summaries_pdf

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config.from_object(Config)
Config.init_app(app)

summarizer = Summarizer(max_sentences=12)
keyword_extractor = KeywordExtractor(max_keywords=10)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect(Config.DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------------------------
# Current-user context
# ---------------------------------------------------------------------------
@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id:
        g.current_user = User.get_by_id(user_id)
        if g.current_user is None:
            session.clear()
            g.current_user = AnonymousUser()
    else:
        g.current_user = AnonymousUser()


@app.context_processor
def inject_current_user():
    return dict(current_user=g.current_user)


# ---------------------------------------------------------------------------
# Auth decorator
# ---------------------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not g.current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
def allowed_file(filename):
    return (
        '.' in filename and
        filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS
    )


def get_file_extension(filename):
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''


def extract_text(filepath, extension):
    """Route file to the correct extractor based on extension."""
    if extension == 'pdf':
        return extract_text_from_pdf(filepath)
    elif extension == 'docx':
        return extract_text_from_docx(filepath)
    elif extension == 'pptx':
        return extract_text_from_pptx(filepath)
    else:
        raise ValueError(f"Unsupported file type: {extension}")


def save_summary_to_db(user_id, filename, original_text, summary, keywords):
    """Insert a new summary record and return its ID."""
    conn = get_db()
    try:
        word_count = len(original_text.split()) if original_text else 0
        cursor = conn.execute(
            '''INSERT INTO summaries (user_id, filename, original_text, summary, keywords, word_count)
               VALUES (?, ?, ?, ?, ?, ?)''',
            (user_id, filename, original_text, summary, keywords, word_count)
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_user_summaries(user_id, search_query=None):
    """Fetch all summaries for a user, optionally filtered by search query."""
    conn = get_db()
    try:
        if search_query:
            rows = conn.execute(
                '''SELECT id, filename, summary, keywords, word_count, created_at
                   FROM summaries
                   WHERE user_id = ?
                     AND (filename LIKE ? OR summary LIKE ? OR keywords LIKE ?)
                   ORDER BY created_at DESC''',
                (user_id, f'%{search_query}%', f'%{search_query}%', f'%{search_query}%')
            ).fetchall()
        else:
            rows = conn.execute(
                '''SELECT id, filename, summary, keywords, word_count, created_at
                   FROM summaries
                   WHERE user_id = ?
                   ORDER BY created_at DESC''',
                (user_id,)
            ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_summary_by_id(summary_id, user_id):
    """Fetch a specific summary record owned by the user."""
    conn = get_db()
    try:
        row = conn.execute(
            '''SELECT s.id, s.filename, s.summary, s.keywords, s.word_count,
                      s.created_at, s.original_text, u.username
               FROM summaries s
               JOIN users u ON s.user_id = u.id
               WHERE s.id = ? AND s.user_id = ?''',
            (summary_id, user_id)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_dashboard_stats(user_id):
    """Fetch analytics data for the dashboard."""
    conn = get_db()
    try:
        total_row = conn.execute(
            'SELECT COUNT(*) as count FROM summaries WHERE user_id = ?',
            (user_id,)
        ).fetchone()
        total_summaries = total_row['count'] if total_row else 0

        words_row = conn.execute(
            'SELECT SUM(word_count) as total FROM summaries WHERE user_id = ?',
            (user_id,)
        ).fetchone()
        total_words = words_row['total'] if words_row and words_row['total'] else 0

        type_rows = conn.execute(
            '''SELECT
                 LOWER(SUBSTR(filename, INSTR(filename, '.') + 1)) as ext,
                 COUNT(*) as count
               FROM summaries
               WHERE user_id = ?
               GROUP BY ext''',
            (user_id,)
        ).fetchall()
        file_types = {row['ext']: row['count'] for row in type_rows}

        recent_rows = conn.execute(
            '''SELECT filename, summary, created_at
               FROM summaries
               WHERE user_id = ?
               ORDER BY created_at DESC
               LIMIT 5''',
            (user_id,)
        ).fetchall()
        recent_summaries = [dict(r) for r in recent_rows]

        # Summaries per month (last 6 months)
        monthly_rows = conn.execute(
            '''SELECT STRFTIME('%Y-%m', created_at) as month, COUNT(*) as count
               FROM summaries
               WHERE user_id = ?
               GROUP BY month
               ORDER BY month DESC
               LIMIT 6''',
            (user_id,)
        ).fetchall()
        monthly_data = [dict(r) for r in monthly_rows]

        return {
            'total_summaries': total_summaries,
            'total_words': total_words,
            'file_types': file_types,
            'recent_summaries': recent_summaries,
            'monthly_data': monthly_data
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Routes: Public
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    if g.current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if g.current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Validation
        if not username or not email or not password:
            flash('All fields are required.', 'danger')
            return render_template('register.html')

        if len(username) < 3:
            flash('Username must be at least 3 characters.', 'danger')
            return render_template('register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('register.html')

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html')

        if '@' not in email:
            flash('Please enter a valid email address.', 'danger')
            return render_template('register.html')

        user, error = User.register(username, email, password)
        if error:
            flash(error, 'danger')
            return render_template('register.html')

        session['user_id'] = user.id
        session.permanent = True
        flash(f'Welcome, {user.username}! Your account has been created.', 'success')
        return redirect(url_for('dashboard'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if g.current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Username and password are required.', 'danger')
            return render_template('login.html')

        user, error = User.login(username, password)
        if error:
            flash(error, 'danger')
            return render_template('login.html')

        session['user_id'] = user.id
        session.permanent = True
        flash(f'Welcome back, {user.username}!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    username = g.current_user.username
    session.clear()
    flash(f'Goodbye, {username}! You have been logged out.', 'info')
    return redirect(url_for('login'))


# ---------------------------------------------------------------------------
# Routes: Protected
# ---------------------------------------------------------------------------
@app.route('/dashboard')
@login_required
def dashboard():
    stats = get_dashboard_stats(g.current_user.id)
    return render_template('dashboard.html', stats=stats)


@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'GET':
        return render_template('index.html')

    if 'file' not in request.files:
        flash('No file part in the request.', 'danger')
        return redirect(url_for('upload'))

    file = request.files['file']
    if file.filename == '':
        flash('No file selected.', 'danger')
        return redirect(url_for('upload'))

    if not allowed_file(file.filename):
        flash('Invalid file type. Please upload a PDF, DOCX, or PPTX file.', 'danger')
        return redirect(url_for('upload'))

    filename = secure_filename(file.filename)
    extension = get_file_extension(filename)

    # Save uploaded file temporarily
    filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
    try:
        file.save(filepath)
    except Exception as e:
        flash(f'Error saving file: {str(e)}', 'danger')
        return redirect(url_for('upload'))

    # Extract text
    try:
        original_text = extract_text(filepath, extension)
    except Exception as e:
        flash(f'Could not read file: {str(e)}', 'danger')
        if os.path.exists(filepath):
            os.remove(filepath)
        return redirect(url_for('upload'))
    finally:
        # Always clean up uploaded file
        if os.path.exists(filepath):
            os.remove(filepath)

    if not original_text or len(original_text.strip()) < 50:
        flash('The file contains too little text to summarize.', 'warning')
        return redirect(url_for('upload'))

    # Generate summary and keywords
    try:
        summary = summarizer.summarize(original_text)
        keywords = keyword_extractor.extract_as_string(original_text)
    except Exception as e:
        flash(f'Error generating summary: {str(e)}', 'danger')
        return redirect(url_for('upload'))

    # Save to database
    try:
        summary_id = save_summary_to_db(
            g.current_user.id, filename, original_text, summary, keywords
        )
    except Exception as e:
        flash(f'Error saving summary: {str(e)}', 'danger')
        return redirect(url_for('upload'))

    flash(f'File "{filename}" processed successfully!', 'success')
    return redirect(url_for('view_summary', id=summary_id))


@app.route('/history')
@login_required
def history():
    search_query = request.args.get('q', '').strip()
    summaries = get_user_summaries(g.current_user.id, search_query if search_query else None)
    return render_template('history.html', summaries=summaries, search_query=search_query)


@app.route('/view_summary/<int:id>')
@login_required
def view_summary(id):
    record = get_summary_by_id(id, g.current_user.id)
    if not record:
        flash('Summary not found or access denied.', 'danger')
        return redirect(url_for('history'))
    return render_template('result.html', 
                           summary=record['summary'],
                           filename=record['filename']
    )

@app.route('/delete_summary/<int:id>', methods=['POST'])
@login_required
def delete_summary(id):
    conn = get_db()
    try:
        record = conn.execute(
            'SELECT id FROM summaries WHERE id = ? AND user_id = ?',
            (id, g.current_user.id)
        ).fetchone()

        if not record:
            flash('Summary not found or access denied.', 'danger')
            return redirect(url_for('history'))

        conn.execute('DELETE FROM summaries WHERE id = ?', (id,))
        conn.commit()
        flash('Summary deleted successfully.', 'success')
    except Exception as e:
        flash(f'Error deleting summary: {str(e)}', 'danger')
    finally:
        conn.close()

    return redirect(url_for('history'))


# ---------------------------------------------------------------------------
# Routes: PDF Download
# ---------------------------------------------------------------------------
@app.route('/download_pdf')
@login_required
def download_pdf():
    """Download all summaries as a single PDF."""
    summaries = get_user_summaries(g.current_user.id)

    if not summaries:
        flash('You have no summaries to export.', 'warning')
        return redirect(url_for('history'))

    try:
        pdf_path = generate_all_summaries_pdf(summaries, g.current_user.username)
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=f"summaries_{g.current_user.username}.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        flash(f'Error generating PDF: {str(e)}', 'danger')
        return redirect(url_for('history'))


@app.route('/download_summary_pdf/<int:id>')
@login_required
def download_summary_pdf(id):
    """Download a specific summary as a PDF."""
    record = get_summary_by_id(id, g.current_user.id)
    if not record:
        flash('Summary not found or access denied.', 'danger')
        return redirect(url_for('history'))

    try:
        pdf_path = generate_summary_pdf(record)
        safe_name = secure_filename(record['filename']).rsplit('.', 1)[0]
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=f"summary_{safe_name}.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        flash(f'Error generating PDF: {str(e)}', 'danger')
        return redirect(url_for('view_summary', id=id))


# ---------------------------------------------------------------------------
# Route: AI Chatbot
# ---------------------------------------------------------------------------
@app.route('/chatbot', methods=['GET', 'POST'])
@login_required
def chatbot():
    """
    Simple rule-based chatbot that answers questions about the user's summaries.
    POST endpoint accepts JSON: { "message": "..." }
    Returns JSON: { "reply": "..." }
    """
    if request.method == 'GET':
        return render_template('chatbot.html')

    data = request.get_json(silent=True)
    if not data or 'message' not in data:
        return jsonify({'reply': 'Please send a valid message.'}), 400

    user_message = data['message'].strip().lower()

    if not user_message:
        return jsonify({'reply': 'Please type a message to continue.'}), 400

    # Fetch user context
    summaries = get_user_summaries(g.current_user.id)
    stats = get_dashboard_stats(g.current_user.id)

    reply = _generate_chatbot_reply(user_message, summaries, stats, g.current_user.username)
    return jsonify({'reply': reply})


def _generate_chatbot_reply(message, summaries, stats, username):
    """Generate a contextual reply based on message keywords."""
    msg = message.lower()

    greetings = ['hi', 'hello', 'hey', 'howdy', 'greetings', 'good morning', 'good afternoon']
    if any(g_word in msg for g_word in greetings):
        return (
            f"Hello, {username}! I'm your Smart Notes assistant. "
            f"You have {stats['total_summaries']} summaries stored. "
            "Ask me about your notes, keywords, or statistics!"
        )

    if any(w in msg for w in ['how many', 'count', 'total summaries', 'number of']):
        return (
            f"You currently have {stats['total_summaries']} summaries stored, "
            f"covering approximately {stats['total_words']:,} words of source material."
        )

    if any(w in msg for w in ['keyword', 'keywords', 'key words', 'topics']):
        if summaries:
            all_keywords = []
            for s in summaries[:10]:
                kw_str = s.get('keywords', '')
                if kw_str:
                    all_keywords.extend([k.strip() for k in kw_str.split(',')])
            from collections import Counter
            top_kw = [k for k, _ in Counter(all_keywords).most_common(8) if k]
            if top_kw:
                return f"Your most frequent keywords across recent notes are: {', '.join(top_kw)}."
        return "I couldn't find any keywords in your summaries yet. Try uploading some documents!"

    if any(w in msg for w in ['latest', 'recent', 'last', 'newest']):
        if summaries:
            latest = summaries[0]
            return (
                f"Your most recent summary is from '{latest['filename']}', "
                f"added on {latest['created_at']}. "
                f"Preview: {latest['summary'][:200]}..."
            )
        return "You don't have any summaries yet. Upload a document to get started!"

    if any(w in msg for w in ['file type', 'pdf', 'docx', 'pptx', 'word', 'powerpoint']):
        ft = stats.get('file_types', {})
        if ft:
            breakdown = ', '.join(f"{ext.upper()}: {count}" for ext, count in ft.items())
            return f"Your document breakdown: {breakdown}."
        return "No documents uploaded yet. Support PDF, DOCX, and PPTX files."

    if any(w in msg for w in ['help', 'what can you do', 'commands', 'features']):
        return (
            "I can help you with:\n"
            "• How many summaries you have\n"
            "• Your most common keywords and topics\n"
            "• Your latest or recent summaries\n"
            "• File type breakdown\n"
            "• Word count statistics\n"
            "Just ask me in natural language!"
        )

    if any(w in msg for w in ['word', 'words', 'length', 'long']):
        return (
            f"Your summaries collectively cover {stats['total_words']:,} words of source text. "
            f"That's a lot of reading time saved!"
        )

    if any(w in msg for w in ['delete', 'remove', 'clear']):
        return (
            "To delete a summary, go to your History page, find the summary, "
            "and click the Delete button. Note this action cannot be undone."
        )

    if any(w in msg for w in ['upload', 'add', 'new document', 'new file']):
        return (
            "To upload a new document, click the Upload button in the navigation. "
            "I support PDF, DOCX, and PPTX files up to 16MB."
        )

    if any(w in msg for w in ['download', 'export', 'pdf export']):
        return (
            "You can download all your summaries as a PDF from the History page, "
            "or download an individual summary from its detail view."
        )

    if any(w in msg for w in ['bye', 'goodbye', 'see you', 'thanks', 'thank you']):
        return f"Goodbye, {username}! Happy summarizing!"

    # Default fallback
    return (
        f"I'm not sure how to answer that, {username}. "
        "Try asking about your summary count, keywords, recent uploads, or file types. "
        "Type 'help' to see what I can do!"
    )


# ---------------------------------------------------------------------------
# API: Dashboard stats (JSON)
# ---------------------------------------------------------------------------
@app.route('/api/stats')
@login_required
def api_stats():
    stats = get_dashboard_stats(g.current_user.id)
    return jsonify(stats)


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(413)
def too_large(e):
    flash('File too large. Maximum allowed size is 16MB.', 'danger')
    return redirect(url_for('upload'))


@app.errorhandler(500)
def server_error(e):
    app.logger.error(f"500 error: {traceback.format_exc()}")
    return render_template('500.html'), 500


#@app.errorhandler(Exception)
#def handle_exception(e):
    #app.logger.error(f"Unhandled exception: {traceback.format_exc()}")
    #flash('An unexpected error occurred. Please try again.', 'danger')
    #if g.current_user.is_authenticated:
      #  return redirect(url_for('dashboard'))
    #return redirect(url_for('index'))


# ---------------------------------------------------------------------------
# Template filters
# ---------------------------------------------------------------------------
@app.template_filter('truncate_words')
def truncate_words_filter(text, num_words=30):
    if not text:
        return ''
    words = text.split()
    if len(words) <= num_words:
        return text
    return ' '.join(words[:num_words]) + '...'


@app.template_filter('format_date')
def format_date_filter(date_str):
    if not date_str:
        return 'Unknown'
    try:
        if isinstance(date_str, str):
            dt = datetime.strptime(date_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
        else:
            dt = date_str
        return dt.strftime('%b %d, %Y %I:%M %p')
    except Exception:
        return str(date_str)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    if not os.path.exists(Config.DATABASE):
        from create_db import create_database
        create_database()
    app.run(debug=True, host='0.0.0.0', port=5000)