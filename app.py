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
    results = []

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

    # ✅ SAVE RESULT
    cursor.execute("""
        INSERT INTO results (test_id, student_name, score, total)
        VALUES (?, ?, ?, ?)
    """, (test_id, student_name, score, len(questions)))

    conn.commit()
    conn.close()

    return render_template("result.html",
                           score=score,
                           total=len(questions),
                           results=results)

# ---------------- ADMIN RESULTS PAGE ---------------- #

@app.route("/admin_results")
def admin_results():
    if not session.get("admin"):
        return "Unauthorized Access"

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT tests.name, results.student_name, results.score, results.total
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

