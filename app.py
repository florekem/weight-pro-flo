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
login_manager.login_view = "login"  # type: ignore


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


@app.route("/settings", methods=["GET", "POST"])
def settings():
    con, cur = open_db()
    if request.method == "POST":
        weight_goal = request.form["weight_goal"]
        waist_reminder_days = request.form["waist_reminder_days"]
        settings = cur.execute(
            """
        UPDATE users SET weight_goal = ?, waist_reminder_days = ? WHERE id = ?
        """,
            (weight_goal, waist_reminder_days, current_user.id),
        )
        con.commit()

    settings = cur.execute(
        "SELECT id, weight_goal, waist_reminder_days FROM users WHERE id = ?",
        (current_user.id,),
    ).fetchone()

    con.close()
    return render_template("settings.html", settings=settings)


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


@app.route("/")
def home():
    return render_template("home.html")


# displaying all entries from the database for logged-in user
# the default redirect page after logg in
@app.route("/entries")
@login_required
def entries():
    today = date.today()
    back_in_time = today - timedelta(days=21)  # how many days to show on page
    con, cur = open_db()
    rows = cur.execute(
        """
        SELECT id, date, weight, waist, notes, photo_path FROM entries 
        WHERE user_id = ? AND date >= ? AND date <= ? ORDER BY date DESC
        """,
        (current_user.id, back_in_time, today),
    ).fetchall()
    waist_last_date = cur.execute(
        "SELECT MAX(date) FROM entries WHERE user_id = ? AND NULLIF(waist, '') IS NOT NULL",
        (current_user.id,),
    ).fetchall()
    con.close()
    # check when was the last date waist was measured
    waist_last_date = waist_last_date[0][0]
    waist_reminder = False
    if waist_last_date:
        if datetime.now() - datetime.fromisoformat(waist_last_date) >= timedelta(
            days=get_user_setting("waist_reminder_days", current_user.id)  # type: ignore
        ):
            waist_reminder = True
    return render_template("entries.html", entries=rows, waist_reminder=waist_reminder)


# add new entries for logged-in user
@app.route("/entries/add", methods=["POST", "GET"])
@login_required
def add_entry():
    if request.method == "POST":
        con, cur = open_db()
        the_date = request.form["the_date"]
        weight = request.form["weight"]
        waist = request.form["waist"]
        notes = request.form["notes"]
        cur.execute(
            """
            INSERT INTO entries (user_id, date, weight, waist, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (current_user.id, the_date, weight, waist, notes),
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
                    round((sum(temp_avg) / len(temp_avg)), 2),
                ]
            )
            i += 7
        except:
            print("requested entries listed")
            break

    #  display a weight change between consecutive weeks
    for i in range(0, len(avgs) - 1):
        diff = avgs[i][2] - avgs[i + 1][2]
        if diff > 0:  # add + or - sing for change
            avgs[i].append("+" + str(round(diff, 2)))
        else:
            avgs[i].append(str(round(diff, 2)))
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
    weight_goal = cur.execute(
        "SELECT id, weight_goal FROM users WHERE id = ?", (current_user.id,)
    ).fetchone()
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

    weight_goal = weight_goal[1]
    weight_goal = [weight_goal] * len(labels)
    # reverse to get the oldest first
    return render_template(
        "trend.html", labels=labels[::-1], values=values[::-1], weight_goal=weight_goal
    )


# helper for opening database
def open_db():
    db_path = os.environ.get("DATABASE_PATH", "weight.db")
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("PRAGMA foreign_keys = ON")
    return con, cur


# helper for retrieving user requested setting (request col name)
def get_user_setting(requested_setting, user_id):
    con, cur = open_db()
    settings = cur.execute(
        "SELECT weight_goal, waist_reminder_days FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    con.close()
    if requested_setting == "weight_goal":
        return settings[0]
    if requested_setting == "waist_reminder_days":
        return settings[1]
