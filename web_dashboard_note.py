from app.database import connect


def dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


async def rating_text():
    async with connect() as db:
        db.row_factory = dict_factory
        cur = await db.execute('''
            SELECT u.full_name,u.username,u.tg_id,
                   COUNT(DISTINCT s.id) AS shifts,
                   COALESCE(SUM(p.points),0) AS points,
                   COUNT(p.id) AS violations
            FROM users u
            LEFT JOIN shifts s ON s.user_id=u.id
            LEFT JOIN penalties p ON p.user_id=u.id
            WHERE u.status='APPROVED'
            GROUP BY u.id
            ORDER BY points ASC, shifts DESC
        ''')
        rows = await cur.fetchall()
    if not rows:
        return 'Немає даних.'
    lines = ['🏆 Рейтинг працівників']
    for i, r in enumerate(rows, 1):
        if r['points'] == 0:
            status = '🥇 Найкращий працівник'
        elif r['points'] <= 3:
            status = '🥈 Хороший результат'
        elif r['points'] <= 8:
            status = '⚠️ Зона уваги'
        else:
            status = '🚨 Грубий порушник'
        lines.append(f"{i}. {r['full_name']} @{r['username']} — {status}\nЗмін: {r['shifts']} | Штрафи: {r['points']} | Порушень: {r['violations']}")
    return '\n\n'.join(lines)


async def bonuses_text():
    rating = await rating_text()
    return '⭐ Бонуси / Працівник місяця\n\n' + rating
