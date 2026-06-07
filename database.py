import sqlite3

DB_NAME = "automod.db"


def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    c = conn.cursor()

    # ---------- USERS ----------
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        warns INTEGER DEFAULT 0,
        last_message_time INTEGER DEFAULT 0
    )
    """)

    # ---------- WARN LOG ----------
    c.execute("""
    CREATE TABLE IF NOT EXISTS warn_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        reason TEXT,
        timestamp INTEGER
    )
    """)

    conn.commit()
    conn.close()
