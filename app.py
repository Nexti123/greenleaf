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

# Конфигурация из переменных окружения (или дефолтные для теста)
BOT_TOKEN = os.getenv("BOT_TOKEN", "ТВОЙ_ТОКЕН_БОТА")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "secret123")  # Пароль от админки на сайте
PORT = int(os.getenv("PORT", 10000))

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
bot = Bot(token=BOT_TOKEN)
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
    'q1': ("Чем вы сейчас занимаетесь?", [
        "Работаю по найму", "Работаю на себя", "Развиваю свой бизнес", 
        "Совмещаю несколько занятий", "Сейчас в поиске"
    ]),
    'q2': ("Что вы хотели бы изменить в своей текущей ситуации?", [
        "Увеличить доход", "Создать дополнительный источник дохода", 
        "Сменить деятельность", "Создать своё дело", "Другое"
    ]),
    'q3': ("Какой дополнительный доход был бы для вас действительно значимым?", [
        "До 30 000 ₽", "30–50 000 ₽", "50–100 000 ₽", "100–200 000 ₽", "Более 200 000 ₽"
    ]),
    'q4': ("Сколько времени вы готовы уделять новому направлению?", [
        "До 30 минут в день", "30–60 минут", "1–2 часа", "2–4 часа", "Более 4 часов"
    ]),
    'q5': ("Что сейчас больше всего мешает вам двигаться вперёд?", [
        "Не хватает времени", "Нет подходящей идеи", "Не хватает денег", 
        "Не хватает знаний", "Не знаю, с чего начать", "Уже пробовал(а), но не получилось"
    ]),
    'q6': ("Если вы увидите подходящую возможность, готовы ли вы её рассмотреть?", [
        "Готов(а) начать сейчас", "Готов(а), если пойму условия", 
        "Пока хочу просто изучить", "Сейчас не готов(а)"
    ])
}

def make_keyboard(options):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=opt, callback_data=f"ans_{opt}")] for opt in options
    ])
    return keyboard

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    q_text, options = QUESTIONS['q1']
    await message.answer(f"1/6. {q_text}", reply_markup=make_keyboard(options))
    await state.set_state(FunnelStates.waiting_for_q1)

@router.callback_query(F.data.startswith("ans_"))
async def process_answer(callback: CallbackQuery, state: FSMContext):
    answer = callback.data.replace("ans_", "")
    current_state = await state.get_state()
    
    # Сохраняем ответ в FSM
    data = await state.get_data()
    
    if current_state == FunnelStates.waiting_for_q1.state:
        data['q1'] = answer
        await state.set_data(data)
        q_text, options = QUESTIONS['q2']
        await callback.message.edit_text(f"2/6. {q_text}", reply_markup=make_keyboard(options))
        await state.set_state(FunnelStates.waiting_for_q2)
        
    elif current_state == FunnelStates.waiting_for_q2.state:
        data['q2'] = answer
        await state.set_data(data)
        q_text, options = QUESTIONS['q3']
        await callback.message.edit_text(f"3/6. {q_text}", reply_markup=make_keyboard(options))
        await state.set_state(FunnelStates.waiting_for_q3)
        
    elif current_state == FunnelStates.waiting_for_q3.state:
        data['q3'] = answer
        await state.set_data(data)
        q_text, options = QUESTIONS['q4']
        await callback.message.edit_text(f"4/6. {q_text}", reply_markup=make_keyboard(options))
        await state.set_state(FunnelStates.waiting_for_q4)
        
    elif current_state == FunnelStates.waiting_for_q4.state:
        data['q4'] = answer
        await state.set_data(data)
        q_text, options = QUESTIONS['q5']
        await callback.message.edit_text(f"5/6. {q_text}", reply_markup=make_keyboard(options))
        await state.set_state(FunnelStates.waiting_for_q5)
        
    elif current_state == FunnelStates.waiting_for_q5.state:
        data['q5'] = answer
        await state.set_data(data)
        q_text, options = QUESTIONS['q6']
        await callback.message.edit_text(f"6/6. {q_text}", reply_markup=make_keyboard(options))
        await state.set_state(FunnelStates.waiting_for_q6)
        
    elif current_state == FunnelStates.waiting_for_q6.state:
        data['q6'] = answer
        
        # Финал: сохраняем в базу данных
        username = callback.from_user.username or f"id_{callback.from_user.id}"
        save_user_answer(callback.from_user.id, username, data)
        
        await callback.message.edit_text(
            "✅ **Спасибо за ответы!** Мы обрабатываем информацию и свяжемся с вами в ближайшее время."
        )
        await state.clear()
        
    await callback.answer()


# ==================== FLASK ПАНЕЛЬ УПРАВЛЕНИЯ ====================
flask_app = Flask(__name__)
flask_app.secret_key = os.urandom(24)

HTML_LOGIN = """
<!DOCTYPE html>
<html>
<head><title>Вход в админку</title></head>
<body style="font-family:sans-serif; text-align:center; margin-top:100px;">
    <h2>🔐 Вход в личный кабинет</h2>
    {% if error %}<p style="color:red;">{{ error }}</p>{% endif %}
    <form method="POST">
        <input type="password" name="password" placeholder="Пароль" style="padding:10px; font-size:16px;">
        <button type="submit" style="padding:10px 20px; font-size:16px;">Войти</button>
    </form>
</body>
</html>
"""

HTML_DASHBOARD = """
<!DOCTYPE html>
<html>
<head>
    <title>Панель управления воронкой</title>
    <style>
        body { font-family: sans-serif; margin: 30px; background: #f4f4f9; }
        .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-bottom: 20px; }
        table { width: 100%; border-collapse: collapse; margin-top: 15px; }
        th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
        th { background: #007bff; color: white; }
        a.btn { background: #007bff; color: white; padding: 5px 10px; text-decoration: none; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="card">
        <h2>📊 Статистика воронки</h2>
        <p>Всего прошло воронку: <strong>{{ total_users }}</strong> человек</p>
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
                <td>{{ user[7] }}</td>
                <td><a class="btn" href="/user/{{ user[0] }}">Открыть анкету</a></td>
            </tr>
            {% endfor %}
        </table>
    </div>
    <a href="/logout">Выйти</a>
</body>
</html>
"""

HTML_USER_DETAIL = """
<!DOCTYPE html>
<html>
<head>
    <title>Анкета пользователя</title>
    <style>
        body { font-family: sans-serif; margin: 30px; background: #f4f4f9; }
        .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        ul { line-height: 1.8; }
    </style>
</head>
<body>
    <div class="card">
        <h2>📋 Анкета пользователя: @{{ user[1] }}</h2>
        <p><strong>ID в Telegram:</strong> {{ user[0] }}</p>
        <p><strong>Дата:</strong> {{ user[7] }}</p>
        <hr>
        <h3>Ответы на вопросы:</h3>
        <ul>
            <li><strong>1. Занятость:</strong> {{ user[2] }}</li>
            <li><strong>2. Что хочет изменить:</strong> {{ user[3] }}</li>
            <li><strong>3. Желаемый доход:</strong> {{ user[4] }}</li>
            <li><strong>4. Готовность времени:</strong> {{ user[5] }}</li>
            <li><strong>5. Что мешает:</strong> {{ user[6] }}</li>
        </ul>
        <br>
        <a href="/">⬅ Назад к списку</a>
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


# Запуск бота и веб-сервера вместе
async def main():
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запускаем Flask в отдельном потоке
    flask_thread = Thread(target=lambda: flask_app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False))
    flask_thread.daemon = True
    flask_thread.start()
    
    print(f"🚀 Бот и сайт запущены! Админка доступна по порту {PORT}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
