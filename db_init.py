import sqlite3

con = sqlite3.connect("weight.db")
cur = con.cursor()
cur.execute("PRAGMA foreign_keys = ON")

cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    weight_goal REAL NULL,
    waist_reminder_days INTEGER NULL
    )
""")
cur.execute("""
    CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    weight REAL NOT NULL,
    waist REAL NULL,
    notes TEXT NULL,
    photo_path TEXT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
    )
""")
# cur.execute("""
#    INSERT INTO users (username, password_hash)
#    VALUES ('florekem', 'pass')
#    """)
# id is autoincrement


con.commit()
con.close()
