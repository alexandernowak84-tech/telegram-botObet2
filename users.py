from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def admin_menu(is_main=False):
    rows = [
        [KeyboardButton(text="📋 Заявки"), KeyboardButton(text="👥 Працівники")],
        [KeyboardButton(text="☕ Хто на перерві"), KeyboardButton(text="⚠️ Порушення")],
        [KeyboardButton(text="📊 Звіт за сьогодні"), KeyboardButton(text="📌 Статуси")],
        [KeyboardButton(text="🏆 Рейтинг"), KeyboardButton(text="⭐ Бонуси")],
        [KeyboardButton(text="📁 Excel звіт"), KeyboardButton(text="📄 PDF звіт")],
    ]
    if is_main:
        rows.append([KeyboardButton(text="➕ Додати адміна"), KeyboardButton(text="👔 Додати старшого")])
        rows.append([KeyboardButton(text="🛠 Корекція"), KeyboardButton(text="➖ Зняти штраф")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)
