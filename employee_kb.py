import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.config import get_config
from app.database import init_db
from app.services.users import ensure_user, get_user_by_tg, list_pending, list_users, set_status, set_role
from app.services.shifts import start_shift, end_shift, force_set_shift_start, force_set_shift_end
from app.services.breaks import start_break, end_break, users_on_break, force_close_break
from app.services.statistics import my_stats, today_report, violations
from app.services.reports import make_excel, make_pdf
from app.services.rating import rating_text, bonuses_text
from app.services.scheduler import scheduler_loop
from app.services.penalties import remove_last_penalty
from app.keyboards.employee_kb import employee_menu
from app.keyboards.admin_kb import admin_menu

class AddRole(StatesGroup):
    waiting_id = State()

class Correction(StatesGroup):
    waiting = State()

config = get_config()
bot = Bot(config.bot_token)
dp = Dispatcher(storage=MemoryStorage())

def now():
    return datetime.now(config.tz)

def is_main(user):
    return user and user["role"] == "MAIN_ADMIN"

def is_admin(user):
    return user and user["role"] in ("MAIN_ADMIN", "ADMIN")

async def send_menu(msg: Message, user):
    if user["role"] == "MAIN_ADMIN":
        await msg.answer("👑 Меню головного адміна", reply_markup=admin_menu(True))
    elif user["role"] == "ADMIN":
        await msg.answer("🛡 Меню адміна", reply_markup=admin_menu(False))
    else:
        await msg.answer("👤 Меню працівника", reply_markup=employee_menu())

@dp.message(CommandStart())
async def cmd_start(msg: Message):
    user = await ensure_user(msg.from_user.id, msg.from_user.full_name, msg.from_user.username or "")
    if user["status"] == "PENDING":
        await msg.answer("✅ Заявка відправлена адміну.")
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Прийняти", callback_data=f"approve:{msg.from_user.id}"),
            InlineKeyboardButton(text="❌ Відхилити", callback_data=f"reject:{msg.from_user.id}")
        ]])
        await bot.send_message(config.main_admin_id, f"🆕 Заявка\n{msg.from_user.full_name}\n@{msg.from_user.username}\nID: {msg.from_user.id}", reply_markup=kb)
        return
    if user["status"] != "APPROVED":
        await msg.answer("❌ Доступ відхилено.")
        return
    await send_menu(msg, user)

@dp.callback_query(F.data.startswith("approve:"))
async def approve(call: CallbackQuery):
    admin = await get_user_by_tg(call.from_user.id)
    if not is_admin(admin):
        await call.answer("Немає доступу", show_alert=True)
        return
    tg_id = int(call.data.split(":")[1])
    await set_status(tg_id, "APPROVED")
    await call.message.answer("✅ Працівника прийнято.")
    await bot.send_message(tg_id, "✅ Доступ підтверджено. Натисніть /start")
    await call.answer()

@dp.callback_query(F.data.startswith("reject:"))
async def reject(call: CallbackQuery):
    admin = await get_user_by_tg(call.from_user.id)
    if not is_admin(admin):
        await call.answer("Немає доступу", show_alert=True)
        return
    tg_id = int(call.data.split(":")[1])
    await set_status(tg_id, "REJECTED")
    await call.message.answer("❌ Заявку відхилено.")
    await call.answer()

@dp.message(F.text == "🟢 Почав зміну")
async def h_start_shift(msg: Message):
    user = await get_user_by_tg(msg.from_user.id)
    ok, text = await start_shift(user["id"], now())
    await msg.answer(text)

@dp.message(F.text == "🔴 Завершив зміну")
async def h_end_shift(msg: Message):
    user = await get_user_by_tg(msg.from_user.id)
    ok, text = await end_shift(user["id"], now())
    await msg.answer(text)

@dp.message(F.text == "☕ Перерва 15 хв")
async def h_break15(msg: Message):
    user = await get_user_by_tg(msg.from_user.id)
    ok, text = await start_break(user["id"], now(), "15 хв", 15)
    await msg.answer(text)

@dp.message(F.text == "🍽 Обід 1 година")
async def h_lunch(msg: Message):
    user = await get_user_by_tg(msg.from_user.id)
    ok, text = await start_break(user["id"], now(), "Обід", 60)
    await msg.answer(text)

@dp.message(F.text == "✅ Повернувся")
async def h_return(msg: Message):
    user = await get_user_by_tg(msg.from_user.id)
    ok, text = await end_break(user["id"], now())
    await msg.answer(text)
    if "штраф" in text.lower():
        await bot.send_message(config.main_admin_id, f"🚨 Порушення\n{user['full_name']} @{user['username']}\n{text}")

@dp.message(F.text == "📊 Моя статистика")
async def h_stats(msg: Message):
    user = await get_user_by_tg(msg.from_user.id)
    await msg.answer(await my_stats(user["id"]))

@dp.message(F.text == "📋 Заявки")
async def h_pending(msg: Message):
    user = await get_user_by_tg(msg.from_user.id)
    if not is_admin(user): return
    rows = await list_pending()
    if not rows:
        await msg.answer("Заявок немає.")
        return
    for r in rows:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Прийняти", callback_data=f"approve:{r['tg_id']}"),
            InlineKeyboardButton(text="❌ Відхилити", callback_data=f"reject:{r['tg_id']}")
        ]])
        await msg.answer(f"{r['full_name']} @{r['username']}\nID: {r['tg_id']}", reply_markup=kb)

@dp.message(F.text == "👥 Працівники")
async def h_users(msg: Message):
    user = await get_user_by_tg(msg.from_user.id)
    if not is_admin(user): return
    rows = await list_users()
    await msg.answer("\n".join([f"{r['role']} | {r['status']} | {r['full_name']} @{r['username']} | ID {r['tg_id']}" for r in rows])[:4000])

@dp.message(F.text == "☕ Хто на перерві")
async def h_on_break(msg: Message):
    user = await get_user_by_tg(msg.from_user.id)
    if not is_admin(user): return
    rows = await users_on_break()
    if not rows:
        await msg.answer("Зараз ніхто не на перерві.")
    else:
        await msg.answer("\n".join([f"{r['full_name']} @{r['username']} — {r['type']} з {r['start_at']}" for r in rows]))

@dp.message(F.text == "⚠️ Порушення")
async def h_viol(msg: Message):
    user = await get_user_by_tg(msg.from_user.id)
    if not is_admin(user): return
    await msg.answer(await violations())

@dp.message(F.text == "📊 Звіт за сьогодні")
async def h_report(msg: Message):
    user = await get_user_by_tg(msg.from_user.id)
    if not is_admin(user): return
    await msg.answer(await today_report())

@dp.message(F.text == "📌 Статуси")
async def h_statuses(msg: Message):
    user = await get_user_by_tg(msg.from_user.id)
    if not is_admin(user): return
    rows = await list_users()
    await msg.answer("\n".join([f"{r['full_name']} — {r['status']} / {r['role']}" for r in rows])[:4000])

@dp.message(F.text.in_({"➕ Додати адміна", "👔 Додати старшого"}))
async def h_add_role(msg: Message, state: FSMContext):
    user = await get_user_by_tg(msg.from_user.id)
    if not is_main(user):
        await msg.answer("❌ Тільки головний адмін.")
        return
    role = "ADMIN" if msg.text.startswith("➕") else "SENIOR"
    await state.update_data(role=role)
    await state.set_state(AddRole.waiting_id)
    await msg.answer("Введіть Telegram ID користувача:")

@dp.message(AddRole.waiting_id)
async def h_add_role_id(msg: Message, state: FSMContext):
    data = await state.get_data()
    try:
        tg_id = int(msg.text.strip())
    except:
        await msg.answer("Введіть тільки цифри ID.")
        return
    await set_role(tg_id, data["role"])
    await state.clear()
    await msg.answer(f"✅ Роль змінено на {data['role']}")

@dp.message(F.text == "➖ Зняти штраф")
async def h_remove_penalty(msg: Message, state: FSMContext):
    user = await get_user_by_tg(msg.from_user.id)
    if not is_main(user):
        await msg.answer("❌ Тільки головний адмін.")
        return
    await state.update_data(action="remove_penalty")
    await state.set_state(Correction.waiting)
    await msg.answer("Введіть Telegram ID працівника:")

@dp.message(F.text == "🛠 Корекція")
async def h_correction(msg: Message):
    user = await get_user_by_tg(msg.from_user.id)
    if not is_main(user):
        await msg.answer("❌ Тільки головний адмін.")
        return
    text = (
        "🛠 Корекція командами:\n\n"
        "/set_start ID YYYY-MM-DD HH:MM\n"
        "/set_end ID YYYY-MM-DD HH:MM\n"
        "/close_break ID YYYY-MM-DD HH:MM\n\n"
        "Приклад:\n/set_start 123456789 2026-05-11 10:00"
    )
    await msg.answer(text)

@dp.message(F.text.startswith("/set_start"))
async def c_start(msg: Message):
    user = await get_user_by_tg(msg.from_user.id)
    if not is_main(user): return
    try:
        _, tg_id, date, hm = msg.text.split(maxsplit=3)
        dt = datetime.fromisoformat(f"{date} {hm}").replace(tzinfo=config.tz)
        ok = await force_set_shift_start(int(tg_id), dt)
        await msg.answer("✅ Початок зміни змінено." if ok else "❌ Не знайдено працівника.")
    except Exception:
        await msg.answer("Формат: /set_start ID YYYY-MM-DD HH:MM")

@dp.message(F.text.startswith("/set_end"))
async def c_end(msg: Message):
    user = await get_user_by_tg(msg.from_user.id)
    if not is_main(user): return
    try:
        _, tg_id, date, hm = msg.text.split(maxsplit=3)
        dt = datetime.fromisoformat(f"{date} {hm}").replace(tzinfo=config.tz)
        ok = await force_set_shift_end(int(tg_id), dt)
        await msg.answer("✅ Кінець зміни змінено." if ok else "❌ Не знайдено зміну.")
    except Exception:
        await msg.answer("Формат: /set_end ID YYYY-MM-DD HH:MM")

@dp.message(F.text.startswith("/close_break"))
async def c_break(msg: Message):
    user = await get_user_by_tg(msg.from_user.id)
    if not is_main(user): return
    try:
        _, tg_id, date, hm = msg.text.split(maxsplit=3)
        dt = datetime.fromisoformat(f"{date} {hm}").replace(tzinfo=config.tz)
        ok = await force_close_break(int(tg_id), dt)
        await msg.answer("✅ Перерву закрито." if ok else "❌ Активна перерва не знайдена.")
    except Exception:
        await msg.answer("Формат: /close_break ID YYYY-MM-DD HH:MM")

@dp.message(Correction.waiting)
async def h_correction_wait(msg: Message, state: FSMContext):
    data = await state.get_data()
    if data.get("action") == "remove_penalty":
        try:
            ok = await remove_last_penalty(int(msg.text.strip()))
            await msg.answer("✅ Останній штраф знято." if ok else "❌ Штраф не знайдено.")
        except:
            await msg.answer("Введіть тільки ID цифрами.")
        await state.clear()



@dp.message(F.text == "🏆 Рейтинг")
async def h_rating(msg: Message):
    user = await get_user_by_tg(msg.from_user.id)
    if not user or user["role"] not in ("MAIN_ADMIN", "ADMIN", "SENIOR"):
        return
    await msg.answer(await rating_text())

@dp.message(F.text == "⭐ Бонуси")
async def h_bonuses(msg: Message):
    user = await get_user_by_tg(msg.from_user.id)
    if not is_admin(user):
        return
    await msg.answer(await bonuses_text())

@dp.message(F.text == "📁 Excel звіт")
async def h_excel_report(msg: Message):
    user = await get_user_by_tg(msg.from_user.id)
    if not is_admin(user):
        return
    path = await make_excel()
    await msg.answer_document(FSInputFile(path), caption="📁 Excel звіт")

@dp.message(F.text == "📄 PDF звіт")
async def h_pdf_report(msg: Message):
    user = await get_user_by_tg(msg.from_user.id)
    if not is_admin(user):
        return
    path = await make_pdf()
    await msg.answer_document(FSInputFile(path), caption="📄 PDF звіт")

@dp.message(F.text.startswith("/reason"))
async def h_reason(msg: Message):
    await msg.answer("✅ Причину прийнято. У цій версії вона зберігається в ручному звіті адміністратора.")

@dp.message(F.text == "📩 Анонімне повідомлення керівнику")
async def anon_info(msg: Message):
    await msg.answer("Напишіть повідомлення так:\n/anon ваш текст")

@dp.message(F.text.startswith("/anon"))
async def anon_send(msg: Message):
    text = msg.text.replace("/anon", "", 1).strip()
    if not text:
        await msg.answer("Напишіть текст після /anon")
        return
    await bot.send_message(config.main_admin_id, f"📩 Анонімне повідомлення:\n{text}")
    await msg.answer("✅ Повідомлення відправлено анонімно.")

async def main():
    await init_db(config.main_admin_id)
    asyncio.create_task(scheduler_loop(bot, config))
    print("Bot started")
    await dp.start_polling(bot)
