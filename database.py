import sqlite3

DB_NAME = "game.db"


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
        money INTEGER DEFAULT 0,
        trust INTEGER DEFAULT 100,
        job TEXT DEFAULT NULL,
        job_fired_count INTEGER DEFAULT 0,
        apartment_status TEXT DEFAULT 'owned',
        last_work_timestamp INTEGER DEFAULT 0,
        created_at INTEGER DEFAULT (strftime('%s','now'))
    )
    """)

    # ---------- INVENTORY ----------
    c.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        item_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        item_name TEXT,
        value INTEGER,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # ---------- STATE (INSPECTION) ----------
    c.execute("""
    CREATE TABLE IF NOT EXISTS state (
        user_id TEXT PRIMARY KEY,
        is_in_inspection INTEGER DEFAULT 0,
        inspection_end_time INTEGER DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # ---------- TAXES ----------
    c.execute("""
    CREATE TABLE IF NOT EXISTS taxes (
        user_id TEXT PRIMARY KEY,
        last_paid INTEGER DEFAULT 0,
        missed_payments INTEGER DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # ---------- JOB HISTORY ----------
    c.execute("""
    CREATE TABLE IF NOT EXISTS job_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        job_name TEXT,
        payout INTEGER,
        timestamp INTEGER
    )
    """)

    conn.commit()
    conn.close()
