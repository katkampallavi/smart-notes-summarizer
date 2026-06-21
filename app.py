from flask import Flask, render_template, request, send_file
import os
from flask import redirect
from flask import session
from utils.pdf_reader import extract_text
from utils.docx_reader import extract_docx_text
from utils.ppt_reader import extract_ppt_text
from models.auth import register_user, login_user
from utils.pdf_export import create_pdf
from models.summarizer import generate_summary
#from models.summarizer import generate_summary
from models.keyword_extractor import extract_keywords
import sqlite3

app = Flask(__name__)
app.secret_key = "smartnotes123"

UPLOAD_FOLDER = "static/uploads"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

@app.route("/")
def home():
    if "user" not in session:
        return redirect("/login")
    
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():

    if "user" not in session:
        return redirect("/login")

    if "pdf" not in request.files:
        return "No file uploaded"

    file = request.files["pdf"]

    if file.filename == "":
        return "Please select a file"

    filepath = os.path.join(
        app.config["UPLOAD_FOLDER"],
        file.filename
    )

    file.save(filepath)

    filename = file.filename.lower()

    if filename.endswith(".pdf"):
        text = extract_text(filepath)

    elif filename.endswith(".docx"):
        text = extract_docx_text(filepath)

    elif filename.endswith(".pptx"):
        text = extract_ppt_text(filepath)

    else:
        return "Unsupported File Type"

    summary = generate_summary(text)

    keywords = extract_keywords(text)

    # Save summary history
    conn = sqlite3.connect("database/smartnotes.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM users WHERE email=?",
        (session["user"],)
    )

    user = cursor.fetchone()

    if user:

        user_id = user[0]

        cursor.execute(
            """
            INSERT INTO summaries
            (user_id, filename, summary)
            VALUES (?, ?, ?)
            """,
            (
                user_id,
                file.filename,
                summary
            )
        )

        conn.commit()

    conn.close()

    create_pdf(summary)

    return render_template(
        "result.html",
        summary=summary,
        keywords=keywords
    )


@app.route("/login", methods=["GET", "POST"])
def login():


 if request.method == "POST":

    email = request.form["email"]
    password = request.form["password"]

    if login_user(email, password):

        session["user"] = email

        return redirect("/")

    return "Invalid Email or Password"

 return render_template("login.html")


@app.route("/logout")
def logout():

    session.pop("user", None)

    return redirect("/login")



@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        register_user(username, email, password)

        return redirect("/login")

    return render_template("register.html")

@app.route("/chatbot")
def chatbot():
    return render_template("chatbot.html")

@app.route("/download")
def download():
    return send_file(
        "static/downloads/summary.pdf",
        as_attachment=True
    )

if __name__ == "__main__":
    app.run(debug=True)