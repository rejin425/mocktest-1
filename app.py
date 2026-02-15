from flask import Flask, render_template, request, redirect, send_from_directory, session
import os
import sqlite3
import pdfplumber

app = Flask(__name__)
app.secret_key = "supersecretkey123"

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

    # ✅ NEW RESULTS TABLE
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_id INTEGER,
            student_name TEXT,
            score INTEGER,
            total INTEGER
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------- PDF FUNCTIONS ---------------- #

def extract_text_from_pdf(filepath):
    text_data = ""
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                text_data += text + "\n"
    return text_data

def parse_questions(text):
    if "Answer Key" not in text:
        return []

    questions = []
    answer_key = {}

    parts = text.split("Answer Key")
    question_part = parts[0]
    answer_part = parts[1]

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
        if request.form.get("username") == "admin" and request.form.get("password") == "1234":
            session["admin"] = True
            return redirect("/")
        return "Invalid Login"

    return """
        <h2>Admin Login</h2>
        <form method="POST">
            <input type="text" name="username"><br><br>
            <input type="password" name="password"><br><br>
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

# ---------------- START TEST ---------------- #

@app.route("/test/<int:test_id>")
def start_test(test_id):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM questions WHERE test_id=?", (test_id,))
    questions = cursor.fetchall()
    conn.close()

    return render_template("mocktest.html",
                           questions=questions,
                           test_id=test_id)

# ---------------- SUBMIT + SAVE SCORE ---------------- #

@app.route("/submit/<int:test_id>", methods=["POST"])
def submit(test_id):
    student_name = request.form.get("student_name")

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM questions WHERE test_id=?", (test_id,))
    questions = cursor.fetchall()

    score = 0

    for q in questions:
        qid = q[0]
        correct = q[7]
        user_answer = request.form.get(str(qid))

        if user_answer == correct:
            score += 1

    total = len(questions)

    # ✅ SAVE RESULT
    cursor.execute("""
        INSERT INTO results (test_id, student_name, score, total)
        VALUES (?, ?, ?, ?)
    """, (test_id, student_name, score, total))

    conn.commit()
    conn.close()

    return render_template("result.html",
                           student_name=student_name,
                           score=score,
                           total=total)

# ---------------- ADMIN RESULTS PAGE ---------------- #

@app.route("/admin/results")
def admin_results():
    if not session.get("admin"):
        return "Unauthorized Access"

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT results.student_name, tests.name, results.score, results.total
        FROM results
        JOIN tests ON results.test_id = tests.id
        ORDER BY results.id DESC
    """)

    data = cursor.fetchall()
    conn.close()

    return render_template("admin_results.html", data=data)

# ---------------- RUN ---------------- #

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


