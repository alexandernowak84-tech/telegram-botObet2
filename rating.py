from datetime import datetime
from app.database import connect

def points_for_minutes(minutes: int) -> int:
    if minutes <= 0:
        return 0
    if minutes <= 5:
        return 1
    if minutes <= 10:
        return 2
    if minutes <= 15:
        return 3
    return 5

async def add_penalty(user_id, shift_id, break_id, reason, points, details=""):
    async with connect() as db:
        now = datetime.now().isoformat(timespec="seconds")
        await db.execute(
            "INSERT INTO penalties(user_id, shift_id, break_id, reason, points, details, created_at) VALUES(?,?,?,?,?,?,?)",
            (user_id, shift_id, break_id, reason, points, details, now)
        )
        await db.commit()

async def remove_last_penalty(tg_id: int):
    async with connect() as db:
        cur = await db.execute("SELECT id FROM users WHERE tg_id=?", (tg_id,))
        u = await cur.fetchone()
        if not u:
            return False
        cur = await db.execute("SELECT id FROM penalties WHERE user_id=? ORDER BY id DESC LIMIT 1", (u[0],))
        p = await cur.fetchone()
        if not p:
            return False
        await db.execute("DELETE FROM penalties WHERE id=?", (p[0],))
        await db.commit()
        return True
