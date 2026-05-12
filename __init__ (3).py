from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def employee_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🟢 Почав зміну"), KeyboardButton(text="🔴 Завершив зміну")],
            [KeyboardButton(text="☕ Перерва 15 хв"), KeyboardButton(text="🍽 Обід 1 година")],
            [KeyboardButton(text="✅ Повернувся")],
            [KeyboardButton(text="📊 Моя статистика"), KeyboardButton(text="📩 Анонімне повідомлення керівнику")],
        ],
        resize_keyboard=True
    )
