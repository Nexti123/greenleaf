import os
import sqlite3
import asyncio
import logging
from threading import Thread
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from flask import Flask, render_template_string, request, redirect, url_for, session

# Логирование
logging.basicConfig(level=logging.INFO)

# Чтение конфигурации из переменных окружения Render
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "secret123")
PORT = int(os.getenv("PORT", 10000))

if not BOT_TOKEN:
    logging.error("❌ Ошибка: Не найден BOT_TOKEN в переменных окружения!")

# Инициализация базы данных SQLite
DB_NAME = "funnel_users.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            q1 TEXT,
            q2 TEXT,
            q3 TEXT,
            q4 TEXT,
            q5 TEXT,
            q6 TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def check_user_exists(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def save_user_answer(user_id, username, data):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, username, q1, q2, q3, q4, q5, q6)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, username, data.get('q1'), data.get('q2'), data.get('q3'), data.get('q4'), data.get('q5'), data.get('q6')))
    conn.commit()
    conn.close()

# Инициализация бота
bot = Bot(token=BOT_TOKEN) if BOT_TOKEN else None
dp = Dispatcher(storage=MemoryStorage())
router = Router()

# Состояния воронки
class FunnelStates(StatesGroup):
    waiting_for_q1 = State()
    waiting_for_q2 = State()
    waiting_for_q3 = State()
    waiting_for_q4 = State()
    waiting_for_q5 = State()
    waiting_for_q6 = State()

# Вопросы и варианты ответов
QUESTIONS = {
    'q1': {
        "text": "Чем вы сейчас занимаетесь?",
        "options": [
            "Работаю по найму", "Работаю на себя", "Развиваю свой бизнес", 
            "Совмещаю несколько занятий", "Сейчас в поиске"
        ]
    },
    'q2': {
        "text": "Что вы хотели бы изменить в своей текущей ситуации?",
        "options": [
            "Увеличить доход", "Создать дополнительный источник дохода", 
            "Сменить деятельность", "Создать своё дело", "Другое"
        ]
    },
    'q3': {
        "text": "Какой дополнительный доход был бы для вас действительно значимым?",
        "options": [
            "До 30 000 ₽", "30–50 000 ₽", "50–100 000 ₽", "100–200 000 ₽", "Более 200 000 ₽"
        ]
    },
    'q4': {
        "text": "Сколько времени вы готовы уделять новому направлению?",
        "options": [
            "До 30 минут в день", "30–60 минут", "1–2 часа", "2–4 часа", "Более 4 часов"
        ]
    },
    'q5': {
        "text": "Что сейчас больше всего мешает вам двигаться вперёд?",
        "options": [
            "Не хватает времени", "Нет подходящей идеи", "Не хватает денег", 
            "Не хватает знаний", "Не знаю, с чего начать", "Уже пробовал(а), но не получилось"
        ]
    },
    'q6': {
        "text": "Если вы увидите подходящую возможность, готовы ли вы её рассмотреть?",
        "options": [
            "Готов(а) начать сейчас", "Готов(а), если пойму условия", 
            "Пока хочу просто изучить", "Сейчас не готов(а)"
        ]
    }
}

def make_keyboard(q_key, options):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=opt, callback_data=f"ans_{q_key}_{i}")] for i, opt in enumerate(options)
    ])

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    # Проверяем, проходил ли пользователь тест ранее
    if check_user_exists(message.from_user.id):
        await message.answer("⚠️ Вы уже прошли этот тест ранее. Спасибо за ваши ответы!")
        return

    await state.clear()
    q_data = QUESTIONS['q1']
    await message.answer(f"1/6. {q_data['text']}", reply_markup=make_keyboard('q1', q_data['options']))
    await state.set_state(FunnelStates.waiting_for_q1)

@router.callback_query(F.data.startswith("ans_"))
async def process_answer(callback: CallbackQuery, state: FSMContext):
    # Дополнительная страховка: если пользователь попытается кликнуть по старым кнопкам повторно
    if check_user_exists(callback.from_user.id):
        await callback.message.edit_text("⚠️ Вы уже завершили прохождение теста ранее.")
        await state.clear()
        await callback.answer()
        return

    parts = callback.data.split("_")
    q_key = parts[1]
    index = int(parts[2])
    
    current_state = await state.get_state()
    data = await state.get_data()
    
    if current_state == FunnelStates.waiting_for_q1.state and q_key == 'q1':
        data['q1'] = QUESTIONS['q1']['options'][index]
        await state.set_data(data)
        q_data = QUESTIONS['q2']
        await callback.message.edit_text(f"2/6. {q_data['text']}", reply_markup=make_keyboard('q2', q_data['options']))
        await state.set_state(FunnelStates.waiting_for_q2)
        
    elif current_state == FunnelStates.waiting_for_q2.state and q_key == 'q2':
        data['q2'] = QUESTIONS['q2']['options'][index]
        await state.set_data(data)
        q_data = QUESTIONS['q3']
        await callback.message.edit_text(f"3/6. {q_data['text']}", reply_markup=make_keyboard('q3', q_data['options']))
        await state.set_state(FunnelStates.waiting_for_q3)
        
    elif current_state == FunnelStates.waiting_for_q3.state and q_key == 'q3':
        data['q3'] = QUESTIONS['q3']['options'][index]
        await state.set_data(data)
        q_data = QUESTIONS['q4']
        await callback.message.edit_text(f"4/6. {q_data['text']}", reply_markup=make_keyboard('q4', q_data['options']))
        await state.set_state(FunnelStates.waiting_for_q4)
        
    elif current_state == FunnelStates.waiting_for_q4.state and q_key == 'q4':
        data['q4'] = QUESTIONS['q4']['options'][index]
        await state.set_data(data)
        q_data = QUESTIONS['q5']
        await callback.message.edit_text(f"5/6. {q_data['text']}", reply_markup=make_keyboard('q5', q_data['options']))
        await state.set_state(FunnelStates.waiting_for_q5)
        
    elif current_state == FunnelStates.waiting_for_q5.state and q_key == 'q5':
        data['q5'] = QUESTIONS['q5']['options'][index]
        await state.set_data(data)
        q_data = QUESTIONS['q6']
        await callback.message.edit_text(f"6/6. {q_data['text']}", reply_markup=make_keyboard('q6', q_data['options']))
        await state.set_state(FunnelStates.waiting_for_q6)
        
    elif current_state == FunnelStates.waiting_for_q6.state and q_key == 'q6':
        data['q6'] = QUESTIONS['q6']['options'][index]
        
        username = callback.from_user.username or f"id_{callback.from_user.id}"
        save_user_answer(callback.from_user.id, username, data)
        
        await callback.message.edit_text(
            "✅ **Спасибо за ответы!** Мы обрабатываем информацию и свяжемся с вами в ближайшее время."
        )
        await state.clear()
        
    await callback.answer()


# ==================== FLASK ПАНЕЛЬ УПРАВЛЕНИЯ (DARK BEIGE / LATTE STYLE) ====================
flask_app = Flask(__name__)
flask_app.secret_key = os.urandom(24)

BASE_STYLE = """
    <style>
        :root {
            --bg-color: #1a1816;
            --card-bg: #24211e;
            --border-color: #38332e;
            --text-main: #f5f0eb;
            --text-muted: #b8afa6;
            --accent: #d4a373;
            --accent-hover: #faedcd;
            --danger: #e07a5f;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            margin: 0;
            padding: 40px 20px;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
        }
        .card {
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.3);
            margin-bottom: 25px;
        }
        h2, h3 {
            margin-top: 0;
            color: var(--accent);
            font-weight: 600;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }
        th, td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }
        th {
            background-color: rgba(212, 163, 115, 0.1);
            color: var(--accent);
            font-weight: 600;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        td {
            color: var(--text-main);
            font-size: 15px;
        }
        tr:hover td {
            background-color: rgba(255, 255, 255, 0.02);
        }
        a {
            color: var(--accent);
            text-decoration: none;
            transition: color 0.2s;
        }
        a:hover {
            color: var(--accent-hover);
            text-decoration: underline;
        }
        .btn {
            display: inline-block;
            background-color: var(--accent);
            color: #1a1816;
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: 600;
            text-decoration: none;
            transition: background 0.2s, transform 0.1s;
        }
        .btn:hover {
            background-color: var(--accent-hover);
            text-decoration: none;
            transform: translateY(-1px);
        }
        .logout-link {
            color: var(--text-muted);
            display: inline-block;
            margin-top: 10px;
        }
        input[type="password"] {
            background-color: #1a1816;
            border: 1px solid var(--border-color);
            padding: 12px 15px;
            border-radius: 6px;
            color: var(--text-main);
            font-size: 16px;
            width: 250px;
            outline: none;
            margin-right: 10px;
        }
        input[type="password"]:focus {
            border-color: var(--accent);
        }
        ul {
            padding-left: 20px;
            line-height: 1.8;
            color: var(--text-muted);
        }
        ul strong {
            color: var(--text-main);
        }
        .error-msg {
            color: var(--danger);
            margin-bottom: 15px;
        }
    </style>
"""

HTML_LOGIN = """
<!DOCTYPE html>
<html>
<head><title>Вход в админку</title>""" + BASE_STYLE + """</head>
<body>
    <div class="container" style="text-align:center; margin-top:120px;">
        <div class="card" style="display:inline-block; width:100%; max-width:400px; box-sizing:border-box;">
            <h2>🔐 Авторизация</h2>
            {% if error %}<p class="error-msg">{{ error }}</p>{% endif %}
            <form method="POST">
                <input type="password" name="password" placeholder="Введите пароль">
                <button type="submit" class="btn">Войти</button>
            </form>
        </div>
    </div>
</body>
</html>
"""

HTML_DASHBOARD = """
<!DOCTYPE html>
<html>
<head><title>Панель управления воронкой</title>""" + BASE_STYLE + """</head>
<body>
    <div class="container">
        <div class="card">
            <h2>📊 Статистика воронки</h2>
            <p style="color: var(--text-muted); margin-bottom: 0;">Всего прошло воронку: <strong style="color: var(--accent); font-size: 18px;">{{ total_users }}</strong> человек</p>
        </div>
        
        <div class="card">
            <h3>👥 Список пользователей</h3>
            <table>
                <tr>
                    <th>ID</th>
                    <th>Юзернейм (Telegram)</th>
                    <th>Дата прохождения</th>
                    <th>Действие</th>
                </tr>
                {% for user in users %}
                <tr>
                    <td>{{ user[0] }}</td>
                    <td><a href="https://t.me/{{ user[1].replace('@','') }}" target="_blank">@{{ user[1] }}</a></td>
                    <td style="color: var(--text-muted); font-size: 14px;">{{ user[7] }}</td>
                    <td><a class="btn" href="/user/{{ user[0] }}">Анкета</a></td>
                </tr>
                {% endfor %}
            </table>
        </div>
        <a href="/logout" class="logout-link">← Выйти из системы</a>
    </div>
</body>
</html>
"""

HTML_USER_DETAIL = """
<!DOCTYPE html>
<html>
<head><title>Анкета пользователя</title>""" + BASE_STYLE + """</head>
<body>
    <div class="container">
        <div class="card">
            <h2>📋 Анкета: @{{ user[1] }}</h2>
            <p style="color: var(--text-muted);">
                <strong>Telegram:</strong> <a href="https://t.me/{{ user[1].replace('@','') }}" target="_blank">Открыть чат (@{{ user[1] }})</a><br>
                <strong>ID в Telegram:</strong> {{ user[0] }}<br>
                <strong>Дата прохождения:</strong> {{ user[7] }}
            </p>
            <hr style="border:0; border-top:1px solid var(--border-color); margin: 20px 0;">
            <h3>Ответы на вопросы:</h3>
            <ul>
                <li><strong>1. Занятость:</strong> {{ user[2] }}</li>
                <li><strong>2. Желаемые изменения:</strong> {{ user[3] }}</li>
                <li><strong>3. Значимый доход:</strong> {{ user[4] }}</li>
                <li><strong>4. Готовность времени:</strong> {{ user[5] }}</li>
                <li><strong>5. Что мешает:</strong> {{ user[6] }}</li>
                <li><strong>6. Готовность к возможности:</strong> {{ user[7] }}</li>
            </ul>
            <br>
            <a href="/" class="btn">⬅ Назад к списку</a>
        </div>
    </div>
</body>
</html>
"""

@flask_app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            error = "Неверный пароль!"
    return render_template_string(HTML_LOGIN, error=error)

@flask_app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users ORDER BY created_at DESC")
    users = cursor.fetchall()
    total_users = len(users)
    conn.close()
    
    return render_template_string(HTML_DASHBOARD, total_users=total_users, users=users)

@flask_app.route('/user/<int:user_id>')
def user_detail(user_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        return "Пользователь не найден", 404
        
    return render_template_string(HTML_USER_DETAIL, user=user)

@flask_app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# Запуск бота и веб-сервера
async def main():
    if not bot:
        return
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запуск Flask в отдельном потоке
    flask_thread = Thread(target=lambda: flask_app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False))
    flask_thread.daemon = True
    flask_thread.start()
    
    print(f"🚀 Бот и сайт запущены! Порт: {PORT}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
