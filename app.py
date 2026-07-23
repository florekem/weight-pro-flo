import os
import sqlite3
from flask import Flask
from flask import render_template
from flask import request, redirect, url_for
from datetime import date
from datetime import datetime
from datetime import timedelta
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    current_user,
    login_required,
)
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("SECRET_KEY environment variable is required")
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


class User(UserMixin):
    def __init__(self, id, username, password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash


@login_manager.user_loader
def load_user(user_id):
    con, cur = open_db()
    row = cur.execute(
        "SELECT id, username, password_hash FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    con.close()

    if row is None:
        return None

    return User(id=row[0], username=row[1], password_hash=row[2])


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        con, cur = open_db()
        row = cur.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        con.close()

        if row and check_password_hash(row[2], password):
            user = User(id=row[0], username=row[1], password_hash=row[2])
            login_user(user)
            return redirect(url_for("entries"))

        return "Invalid username or password", 401

    return render_template("login.html")


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("home"))


# this one will be for login screen
@app.route("/")
def home():
    return render_template("home.html")


# this one will be for displaying all entries from the database for logged-in user
# if user is allready logged-in redirect here from home
# todo: make entries template. how to?
@app.route("/entries")
@login_required
def entries():
    today = date.today()
    back_in_time = today - timedelta(days=21)
    con, cur = open_db()
    rows = cur.execute(
        """
        SELECT id, date, weight, waist FROM entries 
        WHERE user_id = ? AND date >= ? AND date <= ? ORDER BY date DESC
        """,
        (current_user.id, back_in_time, today),
    ).fetchall()
    waist_last_date = cur.execute(
        "SELECT MAX(date) FROM entries WHERE user_id = ? AND waist IS NOT NULL",
        (current_user.id,),
    ).fetchall()
    con.close()
    # check when was the last date waist was measured
    last_waist_date = waist_last_date[0][0]
    waist_reminder = False
    if last_waist_date:
        if datetime.now() - datetime.fromisoformat(last_waist_date) >= timedelta(
            days=14
        ):
            waist_reminder = True
    return render_template("entries.html", entries=rows, waist_reminder=waist_reminder)


# this one will be for adding new entries for logged-in user
@app.route("/entries/add", methods=["POST", "GET"])
@login_required
def add_entry():
    if request.method == "POST":
        con, cur = open_db()
        the_date = request.form["the_date"]
        weight = request.form["weight"]
        waist = request.form["waist"]
        cur.execute(
            """
            INSERT INTO entries (user_id, date, weight, waist)
            VALUES (?, ?, ?, ?)
            """,
            (current_user.id, the_date, weight, waist),
        )
        con.commit()
        con.close()
        return redirect(url_for("entries"))
    else:
        today = date.today().isoformat()
        return render_template("add_entry.html", tday=today)


@app.route("/entries/remove/<int:entry_id>", methods=["POST"])
@login_required
def remove_entry(entry_id):
    con, cur = open_db()
    cur.execute(
        """
        DELETE FROM entries WHERE id = ? AND user_id = ?
        """,
        (entry_id, current_user.id),
    )
    con.commit()
    con.close()
    return redirect(url_for("entries"))


@app.route("/averages")
@login_required
def averages():
    con, cur = open_db()
    rows = cur.execute(
        "SELECT id, date, weight FROM entries WHERE user_id = ?", (current_user.id,)
    ).fetchall()
    con.close()

    diki = {}
    for row in rows:
        diki[datetime.fromisoformat(row[1])] = row[2]

    i = 0
    avgs = []
    while True:
        try:
            chunk_stop = max(diki) - timedelta(days=i)
            chunk_start = max(diki) - timedelta(days=i + 6)
            temp_avg = []
            for key, value in diki.items():
                if key <= chunk_stop and key >= chunk_start:
                    temp_avg.append(value)
            avgs.append(
                [
                    chunk_stop.strftime("%Y-%m-%d"),
                    chunk_start.strftime("%Y-%m-%d"),
                    (sum(temp_avg) / len(temp_avg)),
                ]
            )
            i += 7
        except:
            print("error, no more  entries")
            break

    # this one is for adding change between weeks
    for i in range(0, len(avgs) - 1):
        diff = avgs[i][2] - avgs[i + 1][2]
        if diff > 0:  # add + or - sing for change
            avgs[i].append("+" + str("{:.2f}".format(diff)))
        else:
            avgs[i].append(str("{:.2f}".format(diff)))
    # add 0 change to first week of tracking which does not compare
    avgs[len(avgs) - 1].append(0)

    return render_template("averages.html", averages=avgs)


@app.route("/trend")
@login_required
def trend():

    con, cur = open_db()
    rows = cur.execute(
        "SELECT id, date, weight FROM entries WHERE user_id = ?", (current_user.id,)
    ).fetchall()
    con.close()

    diki = {}
    for row in rows:
        diki[datetime.fromisoformat(row[1])] = row[2]

    labels = []
    values = []
    # calculates a moving avarage
    while True:
        try:
            chunk_stop = max(diki)
            chunk_start = max(diki) - timedelta(days=6)
            temp_avg = []
            for key, value in diki.items():
                if key <= chunk_stop and key >= chunk_start:
                    temp_avg.append(value)
            labels.append(chunk_stop.strftime("%Y-%m-%d"))
            values.append(sum(temp_avg) / len(temp_avg))
            diki.pop(max(diki))
        except:
            print("error, no more  entries")
            break
    # reverse to get the oldest first
    return render_template("trend.html", labels=labels[::-1], values=values[::-1])


def open_db():
    db_path = os.environ.get("DATABASE_PATH", "weight.db")
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("PRAGMA foreign_keys = ON")
    return con, cur
