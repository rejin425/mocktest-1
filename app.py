from flask import Flask, render_template, request, redirect, session
import os
import psycopg2
import pdfplumber

app = Flask(__name__)
app.secret_key = "super_secure_key_2026"

# ---------------- DATABASE CONNECTION ---------------- #

DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

# ---------------- CREATE TABLES ---------------- #

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS tests (
            id SERIAL PRIMARY KEY,
            name TEXT
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id SERIAL PRIMARY KEY,
            test_id INTEGER,
            question TEXT,
            option_a TEXT,
            option_b TEXT,
            option_c TEXT,
            option_d TEXT,
            correct TEXT
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id SERIAL PRIMARY KEY,
            test_id INTEGER,
            student_name TEXT,
            score INTEGER,
            total INTEGER,
            percentage REAL
        );
    """)

    conn.commit()
    cur.close()
    conn.close()

init_db()

# ---------------- HOME ---------------- #

@app.route("/")
def home():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tests ORDER BY id DESC;")
    tests = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("index.html", tests=tests)

# ---------------- ADMIN LOGIN ---------------- #

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form["username"] == "admin" and request.form["password"] == "1234":
            session["admin"] = True
            return redirect("/")
        return "Invalid Login"
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ---------------- PDF PARSE ---------------- #

def extract_text(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    return text

def simple_parse(text):
    if "Answer Key" not in text:
        return []

    parts = text.split("Answer Key")
    q_part = parts[0]
    a_part = parts[1]

    answers = {}
    for line in a_part.split("\n"):
        if "." in line:
            try:
                num, ans = line.split(".", 1)
                answers[int(num.strip())] = ans.strip()
            except:
                pass

    questions = []
    lines = q_part.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        if line and line[0].isdigit() and "." in line:
            question_text = line.split(".",1)[1].strip()
            opts = []
            i += 1

            while i < len(lines) and len(opts) < 4:
                if lines[i].strip().startswith(("A)", "B)", "C)", "D)")):
                    opts.append(lines[i].strip()[3:])
                i += 1

            if len(opts) == 4:
                qnum = len(questions)+1
                correct_letter = answers.get(qnum)
                correct_answer = None

                if correct_letter:
                    index = ord(correct_letter)-ord("A")
                    if 0 <= index < 4:
                        correct_answer = opts[index]

                questions.append({
                    "question": question_text,
                    "options": opts,
                    "answer": correct_answer
                })
        else:
            i += 1

    return questions

# ---------------- UPLOAD ---------------- #

@app.route("/upload", methods=["POST"])
def upload():
    if not session.get("admin"):
        return "Unauthorized"

    file = request.files.get("pdf")
    if not file:
        return "No file selected"

    text = extract_text(file)
    questions = simple_parse(text)

    if not questions:
        return "PDF format not supported"

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("INSERT INTO tests (name) VALUES (%s) RETURNING id;", (file.filename,))
    test_id = cur.fetchone()[0]

    for q in questions:
        cur.execute("""
            INSERT INTO questions
            (test_id, question, option_a, option_b, option_c, option_d, correct)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
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
    cur.close()
    conn.close()

    return redirect("/")

# ---------------- START TEST ---------------- #

@app.route("/test/<int:test_id>")
def start_test(test_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM questions WHERE test_id=%s;", (test_id,))
    questions = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("mocktest.html",
                           questions=questions,
                           test_id=test_id)

# ---------------- SUBMIT ---------------- #

@app.route("/submit/<int:test_id>", methods=["POST"])
def submit(test_id):
    student_name = request.form.get("student_name")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM questions WHERE test_id=%s;", (test_id,))
    questions = cur.fetchall()

    score = 0

    for q in questions:
        qid = q[0]
        correct = q[7]
        ans = request.form.get(str(qid))
        if ans == correct:
            score += 1

    total = len(questions)
    percentage = round((score/total)*100,2) if total > 0 else 0

    cur.execute("""
        INSERT INTO results (test_id, student_name, score, total, percentage)
        VALUES (%s, %s, %s, %s, %s);
    """, (test_id, student_name, score, total, percentage))

    conn.commit()
    cur.close()
    conn.close()

    return render_template("result.html",
                           name=student_name,
                           score=score,
                           total=total,
                           percentage=percentage)

# ---------------- ADMIN RESULTS ---------------- #

@app.route("/admin/results")
def admin_results():
    if not session.get("admin"):
        return "Unauthorized"

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT results.student_name, tests.name,
               results.score, results.total, results.percentage
        FROM results
        JOIN tests ON results.test_id = tests.id
        ORDER BY results.id DESC;
    """)

    data = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("admin_results.html", data=data)

# ---------------- RUN ---------------- #

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)






