import sqlite3

DB_NAME = "game.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    c = conn.cursor()

    # Users table
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        money INTEGER DEFAULT 0,
        trust INTEGER DEFAULT 100,
        job TEXT DEFAULT NULL,
        job_fired_count INTEGER DEFAULT 0,
        apartment_status TEXT DEFAULT 'owned',
        last_work_timestamp INTEGER DEFAULT 0,
        work_streak INTEGER DEFAULT 0
    )
    """)

    # Inventory table
    c.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        id TEXT,
        item_name TEXT,
        value INTEGER
    )
    """)

    # State table (inspection lock)
    c.execute("""
    CREATE TABLE IF NOT EXISTS state (
        id TEXT PRIMARY KEY,
        is_in_inspection INTEGER DEFAULT 0,
        inspection_end_time INTEGER DEFAULT 0
    )
    """)

    # Tax table
    c.execute("""
    CREATE TABLE IF NOT EXISTS taxes (
        id TEXT PRIMARY KEY,
        last_paid INTEGER DEFAULT 0,
        missed_payments INTEGER DEFAULT 0
    )
    """)

    conn.commit()
    conn.close()
