from flask import Flask, render_template, request, redirect
import sqlite3
import os

app = Flask(__name__)

# ---------------- DATABASE INIT ---------------- #

def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        score INTEGER
    )
    """)
    conn.commit()
    conn.close()

init_db()

# ---------------- SAMPLE QUESTIONS ---------------- #

questions = [
    {
        "question": "What is 2 + 2?",
        "options": ["3", "4", "5", "6"],
        "answer": "4"
    },
    {
        "question": "Capital of India?",
        "options": ["Chennai", "Delhi", "Mumbai", "Kolkata"],
        "answer": "Delhi"
    },
    {
        "question": "5 x 3 = ?",
        "options": ["15", "10", "20", "25"],
        "answer": "15"
    }
]

# ---------------- HOME ---------------- #

@app.route("/")
def home():
    return render_template("index.html")

# ---------------- MOCK TEST PAGE ---------------- #

@app.route("/mocktest")
def mocktest():
    return render_template("mocktest.html", questions=questions)

# ---------------- SUBMIT ---------------- #

@app.route("/submit", methods=["POST"])
def submit():
    name = request.form.get("student_name")
    score = 0

    for i in range(len(questions)):
        selected = request.form.get(f"q{i}")
        if selected == questions[i]["answer"]:
            score += 1

    # Save to database
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("INSERT INTO results (name, score) VALUES (?, ?)", (name, score))
    conn.commit()
    conn.close()

    return render_template("result.html", score=score)

# ---------------- ADMIN RESULTS ---------------- #

@app.route("/admin_results")
def admin_results():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT * FROM results")
    data = c.fetchall()
    conn.close()
    return render_template("admin_results.html", data=data)

# ---------------- RUN ---------------- #

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)


