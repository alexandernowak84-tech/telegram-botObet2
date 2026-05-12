from app.database import connect

async def my_stats(user_id):
    async with connect() as db:
        cur = await db.execute("SELECT COUNT(*), COALESCE(SUM(points),0) FROM penalties WHERE user_id=?", (user_id,))
        cnt, pts = await cur.fetchone()
        cur = await db.execute("SELECT COUNT(*) FROM shifts WHERE user_id=?", (user_id,))
        shifts = (await cur.fetchone())[0]
        return f"📊 Ваша статистика\n\nЗмін: {shifts}\nПорушень: {cnt}\nШтрафні бали: {pts}"

async def today_report():
    async with connect() as db:
        cur = await db.execute("SELECT COUNT(*) FROM shifts")
        shifts = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*), COALESCE(SUM(points),0) FROM penalties")
        pc, pts = await cur.fetchone()
        return f"📊 Звіт\n\nУсього змін: {shifts}\nПорушень: {pc}\nШтрафних балів: {pts}"

async def violations():
    async with connect() as db:
        db.row_factory = lambda cursor, row: {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
        cur = await db.execute('''
            SELECT u.full_name, u.username, p.reason, p.points, p.details, p.created_at
            FROM penalties p JOIN users u ON u.id=p.user_id
            ORDER BY p.id DESC LIMIT 20
        ''')
        rows = await cur.fetchall()
        if not rows:
            return "Порушень немає."
        return "\n\n".join([f"⚠️ {r['full_name']} @{r['username']}\n{r['reason']} +{r['points']}\n{r['details']}\n{r['created_at']}" for r in rows])
