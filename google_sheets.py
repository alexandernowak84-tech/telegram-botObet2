from datetime import datetime, time
from app.database import connect
from app.services.shifts import active_shift
from app.services.penalties import points_for_minutes, add_penalty

async def active_break(user_id):
    async with connect() as db:
        db.row_factory = lambda cursor, row: {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
        cur = await db.execute("SELECT * FROM breaks WHERE user_id=? AND end_at IS NULL ORDER BY id DESC LIMIT 1", (user_id,))
        return await cur.fetchone()

async def start_break(user_id, now: datetime, break_type: str, allowed: int):
    if now.time() < time(11,0):
        return False, "❌ У першу годину роботи перерву брати не можна."
    if now.time() >= time(18,0):
        return False, "❌ В останню годину роботи перерву брати не можна."
    sh = await active_shift(user_id)
    if not sh:
        return False, "❌ Спочатку почніть зміну."
    if await active_break(user_id):
        return False, "❌ Ви вже на перерві."

    async with connect() as db:
        # limit counts per day/simple shift
        if break_type == "Обід":
            cur = await db.execute("SELECT COUNT(*) FROM breaks WHERE shift_id=? AND type='Обід'", (sh["id"],))
            if (await cur.fetchone())[0] >= 1:
                return False, "❌ Обід вже використано."
        else:
            cur = await db.execute("SELECT COUNT(*) FROM breaks WHERE shift_id=? AND type='15 хв'", (sh["id"],))
            if (await cur.fetchone())[0] >= 3:
                return False, "❌ Усі 15-хв перерви вже використані."

        now_s = now.isoformat(timespec="seconds")
        await db.execute(
            "INSERT INTO breaks(shift_id, user_id, type, allowed_minutes, start_at, created_at) VALUES(?,?,?,?,?,?)",
            (sh["id"], user_id, break_type, allowed, now_s, now_s)
        )
        await db.commit()
    return True, f"✅ {break_type} почато. Повернутись через {allowed} хв."

async def end_break(user_id, now: datetime):
    br = await active_break(user_id)
    if not br:
        return False, "У вас немає активної перерви."
    start = datetime.fromisoformat(br["start_at"])
    used = int((now.replace(tzinfo=None) - start.replace(tzinfo=None)).total_seconds() // 60)
    over = max(0, used - int(br["allowed_minutes"]))
    pts = points_for_minutes(over)

    async with connect() as db:
        await db.execute("UPDATE breaks SET end_at=?, penalty_points=? WHERE id=?", (now.isoformat(timespec='seconds'), pts, br["id"]))
        await db.commit()

    if pts:
        await add_penalty(user_id, br["shift_id"], br["id"], f"Перевищення перерви: {br['type']}", pts, f"Дозволено {br['allowed_minutes']} хв, фактично {used} хв, перевищення {over} хв")
        return True, f"✅ Ви повернулись. ⚠️ Перевищення {over} хв, штраф +{pts}."
    return True, "✅ Ви повернулись з перерви."

async def force_close_break(tg_id: int, dt: datetime):
    async with connect() as db:
        cur = await db.execute("SELECT id FROM users WHERE tg_id=?", (tg_id,))
        u = await cur.fetchone()
        if not u:
            return False
        cur = await db.execute("SELECT id FROM breaks WHERE user_id=? AND end_at IS NULL ORDER BY id DESC LIMIT 1", (u[0],))
        br = await cur.fetchone()
        if not br:
            return False
        await db.execute("UPDATE breaks SET end_at=? WHERE id=?", (dt.isoformat(timespec='seconds'), br[0]))
        await db.commit()
        return True

async def users_on_break():
    async with connect() as db:
        db.row_factory = lambda cursor, row: {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
        cur = await db.execute('''
            SELECT u.full_name, u.username, b.type, b.start_at, b.allowed_minutes
            FROM breaks b JOIN users u ON u.id=b.user_id
            WHERE b.end_at IS NULL
            ORDER BY b.start_at DESC
        ''')
        return await cur.fetchall()
