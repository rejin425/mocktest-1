from flask import Flask, render_template, request, redirect, send_from_directory, session
import os
import sqlite3
import pdfplumber

app = Flask(__name__)
app.secret_key = "supersecretkey123"   # change later

UPLOAD_FOLDER = "uploads"
VIDEO_FOLDER = "videos"
DATABASE = "database.db"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(VIDEO_FOLDER, exist_ok=True)

# ---------------- DATABASE INIT ---------------- #

def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            video TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id INTEGER,
            question TEXT,
            option_a TEXT,
            option_b TEXT,
            option_c TEXT,
            option_d TEXT,
            correct TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------- PDF TEXT ---------------- #

def extract_text_from_pdf(filepath):
    text_data = ""
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_data += text + "\n"
    return text_data

# ---------------- PARSE QUESTIONS ---------------- #

def parse_questions(text):
    if "Answer Key" not in text:
        return []

    questions = []
    answer_key = {}

    parts = text.split("Answer Key")
    question_part = parts[0]
    answer_part = parts[1]

    # Extract answer key
    for line in answer_part.split("\n"):
        line = line.strip()
        if "." in line:
            try:
                num, ans = line.split(".", 1)
                answer_key[int(num.strip())] = ans.strip()
            except:
                continue

    lines = question_part.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        if line and line[0].isdigit() and "." in line:
            question_text = line.split(".", 1)[1].strip()
            options = []
            i += 1

            while i < len(lines) and len(options) < 4:
                opt = lines[i].strip()
                if opt.startswith(("A)", "B)", "C)", "D)")):
                    options.append(opt[3:].strip())
                i += 1

            if len(options) == 4:
                q_number = len(questions) + 1
                correct_letter = answer_key.get(q_number)
                correct_option = None

                if correct_letter:
                    index = ord(correct_letter) - ord('A')
                    if 0 <= index < 4:
                        correct_option = options[index]

                questions.append({
                    "question": question_text,
                    "options": options,
                    "answer": correct_option
                })
        else:
            i += 1

    return questions

# ---------------- ADMIN LOGIN ---------------- #

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == "admin" and password == "1234":
            session["admin"] = True
            return redirect("/")
        else:
            return "Invalid Login"

    return """
        <h2>Admin Login</h2>
        <form method="POST">
            <input type="text" name="username" placeholder="Username"><br><br>
            <input type="password" name="password" placeholder="Password"><br><br>
            <button type="submit">Login</button>
        </form>
    """

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect("/")

# ---------------- HOME ---------------- #

@app.route("/")
def home():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tests")
    tests = cursor.fetchall()
    conn.close()
    return render_template("index.html", tests=tests)

# ---------------- UPLOAD (ADMIN ONLY) ---------------- #

@app.route("/upload", methods=["POST"])
def upload():
    if not session.get("admin"):
        return "Unauthorized Access"

    pdf_file = request.files.get("pdf")
    video_file = request.files.get("video")

    if not pdf_file:
        return "No PDF uploaded"

    pdf_path = os.path.join(UPLOAD_FOLDER, pdf_file.filename)
    pdf_file.save(pdf_path)

    video_filename = None
    if video_file and video_file.filename != "":
        video_path = os.path.join(VIDEO_FOLDER, video_file.filename)
        video_file.save(video_path)
        video_filename = video_file.filename

    text = extract_text_from_pdf(pdf_path)
    questions = parse_questions(text)

    if not questions:
        return "No questions detected"

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO tests (name, video) VALUES (?, ?)",
        (pdf_file.filename, video_filename)
    )
    test_id = cursor.lastrowid

    for q in questions:
        cursor.execute("""
            INSERT INTO questions
            (test_id, question, option_a, option_b, option_c, option_d, correct)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            test_id,
            q["question"],
            q["options"][0],
            q["options"][1],
            q["options"][2],
            q["options"][3],
            q["answer"]
        ))

    conn.commit()
    conn.close()

    return redirect("/")

# ---------------- START TEST ---------------- #

@app.route("/test/<int:test_id>")
def start_test(test_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM questions WHERE test_id=?", (test_id,))
    questions = cursor.fetchall()

    cursor.execute("SELECT video FROM tests WHERE id=?", (test_id,))
    video_row = cursor.fetchone()
    video = video_row[0] if video_row else None

    conn.close()

    return render_template("mocktest.html",
                           questions=questions,
                           test_id=test_id,
                           video=video)

# ---------------- SUBMIT + SCORE SHEET ---------------- #

@app.route("/submit/<int:test_id>", methods=["POST"])
def submit(test_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM questions WHERE test_id=?", (test_id,))
    questions = cursor.fetchall()

    results = []
    score = 0

    for q in questions:
        qid = q[0]
        question = q[2]
        correct = q[7]
        user_answer = request.form.get(str(qid))

        if user_answer == correct:
            score += 1
            status = "Correct"
        else:
            status = "Wrong"

        results.append({
            "question": question,
            "your_answer": user_answer,
            "correct_answer": correct,
            "status": status
        })

    conn.close()

    return render_template("result.html",
                           score=score,
                           total=len(questions),
                           results=results)

# ---------------- SERVE VIDEO ---------------- #

@app.route("/videos/<filename>")
def serve_video(filename):
    return send_from_directory(VIDEO_FOLDER, filename)

# ---------------- RUN ---------------- #
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

