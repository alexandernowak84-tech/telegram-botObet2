import os
import aiosqlite
from datetime import datetime

DB_PATH = os.path.join("data", "bot.db")

def connect():
    os.makedirs("data", exist_ok=True)
    return aiosqlite.connect(DB_PATH)

async def init_db(main_admin_id: int):
    async with connect() as db:
        await db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tg_id INTEGER UNIQUE NOT NULL,
            full_name TEXT,
            username TEXT,
            role TEXT NOT NULL DEFAULT 'EMPLOYEE',
            status TEXT NOT NULL DEFAULT 'PENDING',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS shifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            start_at TEXT,
            end_at TEXT,
            auto_closed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS breaks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shift_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            allowed_minutes INTEGER NOT NULL,
            start_at TEXT NOT NULL,
            end_at TEXT,
            penalty_points INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS penalties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            shift_id INTEGER,
            break_id INTEGER,
            reason TEXT NOT NULL,
            points INTEGER NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS anonymous_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        ''')
        now = datetime.now().isoformat(timespec="seconds")
        cur = await db.execute("SELECT id FROM users WHERE tg_id=?", (main_admin_id,))
        row = await cur.fetchone()
        if not row:
            await db.execute(
                "INSERT INTO users(tg_id, full_name, username, role, status, created_at) VALUES(?,?,?,?,?,?)",
                (main_admin_id, "Main Admin", "", "MAIN_ADMIN", "APPROVED", now)
            )
        else:
            await db.execute(
                "UPDATE users SET role='MAIN_ADMIN', status='APPROVED' WHERE tg_id=?",
                (main_admin_id,)
            )

        # Enterprise migrations
        for sql in [
            "ALTER TABLE shifts ADD COLUMN remind_2230 INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE shifts ADD COLUMN remind_2250 INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE breaks ADD COLUMN remind_sent INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE breaks ADD COLUMN overdue_sent INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE penalties ADD COLUMN explanation TEXT",
        ]:
            try:
                await db.execute(sql)
            except Exception:
                pass
        await db.commit()
