from datetime import datetime
from app.database import connect

async def get_user_by_tg(tg_id: int):
    async with connect() as db:
        db.row_factory = lambda cursor, row: {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
        cur = await db.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,))
        return await cur.fetchone()

async def ensure_user(tg_id: int, full_name: str, username: str):
    user = await get_user_by_tg(tg_id)
    if user:
        return user
    async with connect() as db:
        now = datetime.now().isoformat(timespec="seconds")
        await db.execute(
            "INSERT INTO users(tg_id, full_name, username, role, status, created_at) VALUES(?,?,?,?,?,?)",
            (tg_id, full_name, username or "", "EMPLOYEE", "PENDING", now)
        )
        await db.commit()
    return await get_user_by_tg(tg_id)

async def set_status(tg_id: int, status: str):
    async with connect() as db:
        await db.execute("UPDATE users SET status=? WHERE tg_id=?", (status, tg_id))
        await db.commit()

async def set_role(tg_id: int, role: str):
    async with connect() as db:
        await db.execute("UPDATE users SET role=?, status='APPROVED' WHERE tg_id=?", (role, tg_id))
        await db.commit()

async def list_pending():
    async with connect() as db:
        db.row_factory = lambda cursor, row: {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
        cur = await db.execute("SELECT * FROM users WHERE status='PENDING' ORDER BY id DESC")
        return await cur.fetchall()

async def list_users():
    async with connect() as db:
        db.row_factory = lambda cursor, row: {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
        cur = await db.execute("SELECT * FROM users ORDER BY role DESC, full_name")
        return await cur.fetchall()
