from datetime import datetime, time
from app.database import connect
from app.services.penalties import points_for_minutes, add_penalty

WORK_START = time(10, 0)
WORK_END = time(19, 0)

async def active_shift(user_id):
    async with connect() as db:
        db.row_factory = lambda cursor, row: {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
        cur = await db.execute("SELECT * FROM shifts WHERE user_id=? AND end_at IS NULL ORDER BY id DESC LIMIT 1", (user_id,))
        return await cur.fetchone()

async def start_shift(user_id, now: datetime):
    if await active_shift(user_id):
        return False, "У вас вже відкрита зміна."
    async with connect() as db:
        now_s = now.isoformat(timespec="seconds")
        cur = await db.execute(
            "INSERT INTO shifts(user_id, start_at, created_at) VALUES(?,?,?)",
            (user_id, now_s, now_s)
        )
        shift_id = cur.lastrowid
        await db.commit()

    late_minutes = max(0, int((datetime.combine(now.date(), WORK_START, now.tzinfo) - now).total_seconds() // -60))
    if now.time() > WORK_START:
        pts = points_for_minutes(late_minutes)
        if pts:
            await add_penalty(user_id, shift_id, None, "Опоздание на смену", pts, f"Опоздание {late_minutes} мин")
            return True, f"✅ Зміна почата. ⚠️ Запізнення {late_minutes} хв, штраф +{pts}."
    return True, "✅ Зміна почата."

async def end_shift(user_id, now: datetime, auto=False):
    sh = await active_shift(user_id)
    if not sh:
        return False, "У вас немає активної зміни."
    async with connect() as db:
        await db.execute(
            "UPDATE shifts SET end_at=?, auto_closed=? WHERE id=?",
            (now.isoformat(timespec='seconds'), 1 if auto else 0, sh["id"])
        )
        await db.commit()
    return True, "🔴 Зміну завершено."

async def force_set_shift_start(tg_id: int, dt: datetime):
    async with connect() as db:
        cur = await db.execute("SELECT id FROM users WHERE tg_id=?", (tg_id,))
        u = await cur.fetchone()
        if not u:
            return False
        user_id = u[0]
        cur = await db.execute("SELECT id FROM shifts WHERE user_id=? ORDER BY id DESC LIMIT 1", (user_id,))
        sh = await cur.fetchone()
        if not sh:
            now_s = datetime.now().isoformat(timespec='seconds')
            await db.execute("INSERT INTO shifts(user_id, start_at, created_at) VALUES(?,?,?)", (user_id, dt.isoformat(timespec='seconds'), now_s))
        else:
            await db.execute("UPDATE shifts SET start_at=? WHERE id=?", (dt.isoformat(timespec='seconds'), sh[0]))
        await db.commit()
        return True

async def force_set_shift_end(tg_id: int, dt: datetime):
    async with connect() as db:
        cur = await db.execute("SELECT id FROM users WHERE tg_id=?", (tg_id,))
        u = await cur.fetchone()
        if not u:
            return False
        cur = await db.execute("SELECT id FROM shifts WHERE user_id=? ORDER BY id DESC LIMIT 1", (u[0],))
        sh = await cur.fetchone()
        if not sh:
            return False
        await db.execute("UPDATE shifts SET end_at=? WHERE id=?", (dt.isoformat(timespec='seconds'), sh[0]))
        await db.commit()
        return True
