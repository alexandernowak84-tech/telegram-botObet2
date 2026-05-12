import os
from datetime import datetime
from app.database import connect
from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


async def collect_rows():
    async with connect() as db:
        db.row_factory = dict_factory
        cur = await db.execute('''
            SELECT u.full_name, u.username, u.tg_id, u.role, u.status,
                   COUNT(DISTINCT s.id) AS shifts,
                   COALESCE(SUM(p.points),0) AS points,
                   COUNT(p.id) AS violations
            FROM users u
            LEFT JOIN shifts s ON s.user_id=u.id
            LEFT JOIN penalties p ON p.user_id=u.id
            GROUP BY u.id
            ORDER BY points ASC, shifts DESC
        ''')
        return await cur.fetchall()


async def make_excel():
    os.makedirs('exports/excel', exist_ok=True)
    rows = await collect_rows()
    wb = Workbook()
    ws = wb.active
    ws.title = 'Report'
    ws.append(['Працівник','Username','Telegram ID','Роль','Статус','Змін','Штрафні бали','Порушення','Місце'])
    for i, r in enumerate(rows, 1):
        ws.append([r['full_name'], r['username'], r['tg_id'], r['role'], r['status'], r['shifts'], r['points'], r['violations'], i])
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 22
    path = f"exports/excel/report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    wb.save(path)
    return path


async def make_pdf():
    os.makedirs('exports/pdf', exist_ok=True)
    rows = await collect_rows()
    path = f"exports/pdf/report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4
    y = height - 50
    c.setFont('Helvetica-Bold', 16)
    c.drawString(40, y, 'Worker Bot Report')
    y -= 30
    c.setFont('Helvetica', 10)
    for i, r in enumerate(rows, 1):
        line = f"{i}. {r['full_name']} @{r['username']} | {r['role']} | shifts {r['shifts']} | points {r['points']} | violations {r['violations']}"
        c.drawString(40, y, line[:115])
        y -= 18
        if y < 50:
            c.showPage()
            y = height - 50
            c.setFont('Helvetica', 10)
    c.save()
    return path
