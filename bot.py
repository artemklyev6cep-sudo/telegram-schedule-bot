import requests
from datetime import date, timedelta
from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
import random
import logging
import os
import sys
import asyncio

# ========== НАСТРОЙКИ ДЛЯ RENDER ==========
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)
# ==========================================

# Безопасное получение токена из переменных окружения
TOKEN = os.getenv('BOT_TOKEN', '8512277521:AAHYP10fWioTGeMQ30OUYOLlB1i-AMMmJT4')
if TOKEN == '8512277521:AAHYP10fWioTGeMQ30OUYOLlB1i-AMMmJT4':
    logger.warning("⚠️ Используется тестовый токен! Для продакшена установите BOT_TOKEN в переменные окружения")

# Инициализация aiogram 3.x
bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Убедитесь, что это правильный ID группы
GROUP_ID = 3808
REFERENCE_WEEK_START = date(2025, 12, 15)  
DAYS_ORDER = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

def get_week_type(check_date=None):
    if check_date is None:
        check_date = date.today()
    monday = check_date - timedelta(days=check_date.weekday())
    delta_weeks = (monday - REFERENCE_WEEK_START).days // 7
    return "2" if delta_weeks % 2 == 0 else "1"  

def fetch_schedule_table(for_date=None):
    """Упрощенная функция для теста - возвращает тестовое расписание"""
    if for_date is None:
        for_date = date.today()
    
    week_type = get_week_type(for_date)
    
    # ТЕСТОВОЕ РАСПИСАНИЕ - замените на реальный парсинг позже
    schedule = {
        "Понедельник": ["- Математика | 9:00 | ауд. 101 | Иванов"],
        "Вторник": ["- Физика | 10:30 | ауд. 202 | Петров"],
        "Среда": ["- Программирование | 13:00 | ауд. 303 | Сидоров"],
        "Четверг": ["- Английский | 11:00 | ауд. 404 | Смирнова"],
        "Пятница": ["- Физкультура | 15:00 | спортзал | Кузнецов"],
        "Суббота": [],
        "Воскресенье": []
    }
    
    return schedule, week_type

def format_day_schedule(day_name, schedule):
    text = f"<b>{day_name}:</b>\n"
    if schedule.get(day_name) and len(schedule[day_name]) > 0:
        for lesson in schedule[day_name]:
            text += f"📚 {lesson}\n"
    else:
        text += "🎉 Нет занятий\n"
    return text

# ========== КОМАНДЫ БОТА ==========

@router.message(Command("schedule"))
async def schedule_command(message: types.Message):
    try:
        schedule, week_type = fetch_schedule_table()
        week_type_name = "Знаменатель" if week_type == '2' else 'Числитель'
        text = f"<b>Расписание на эту неделю ({week_type_name}):</b>\n\n"
        for day in DAYS_ORDER[:-1]:
            text += format_day_schedule(day, schedule) + "\n"
        await message.reply(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка в schedule_command: {e}")
        await message.reply("❌ Ошибка при получении расписания.")

@router.message(Command("today"))
async def today_command(message: types.Message):
    try:
        schedule, week_type = fetch_schedule_table()
        today_name = DAYS_ORDER[date.today().weekday()]
        week_type_name = "Знаменатель" if week_type == '2' else 'Числитель'
        text = f"<b>Расписание на сегодня ({today_name}, {week_type_name}):</b>\n\n"
        text += format_day_schedule(today_name, schedule)
        await message.reply(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка в today_command: {e}")
        await message.reply("❌ Ошибка при получении расписания.")

@router.message(Command("tomorrow"))
async def tomorrow_command(message: types.Message):
    try:
        tomorrow = date.today() + timedelta(days=1)
        if tomorrow.weekday() >= 6:
            text = "🎉 Завтра занятий нет (воскресенье)."
        else:
            schedule, week_type = fetch_schedule_table(for_date=tomorrow)
            tomorrow_name = DAYS_ORDER[tomorrow.weekday()]
            week_type_name = "Знаменатель" if week_type == '2' else 'Числитель'
            text = f"<b>Расписание на завтра ({tomorrow_name}, {week_type_name}):</b>\n\n"
            text += format_day_schedule(tomorrow_name, schedule)
        await message.reply(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка в tomorrow_command: {e}")
        await message.reply("❌ Ошибка при получении расписания.")

@router.message(Command("session"))
async def session_command(message: types.Message):
    answers = [
        "✅ Сдашь!",
        "🎯 Нужно немного подготовиться",
        "🤔 Отчислен!",
        "📚 Учись!",
        "🍀 Готовь подарки Некрасовой!",
    ]
    answer = random.choice(answers)
    await message.reply(f"🎓 Прогноз на сессию:\n\n{answer}")

@router.message(Command("start", "help"))
async def start_command(message: types.Message):
    await message.reply(
        "📚 <b>Бот-расписание МИСИС</b>\n\n"
        "Доступные команды:\n"
        "/schedule — расписание на неделю\n"
        "/today — на сегодня\n"
        "/tomorrow — на завтра\n"
        "/session — прогноз на сессию\n"
        "/help — эта справка\n\n"
        "<i>By. Shmal</i>",
        parse_mode="HTML"
    )

@router.message()
async def handle_other_messages(message: types.Message):
    text = message.text.strip().lower()
    if text in ["привет", "hello", "hi", "бот"]:
        await start_command(message)
    elif "сессия" in text or "экзамен" in text:
        await session_command(message)
    else:
        await message.reply("Напишите /help для списка команд")

# ========== ЗАПУСК ==========

if __name__ == "__main__":
    try:
        logger.info("🚀 Бот запускается...")
        logger.info(f"👥 ID группы: {GROUP_ID}")
        logger.info(f"📅 Референсная неделя: {REFERENCE_WEEK_START}")
        
        dp.run_polling(bot, skip_updates=True)
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}")



