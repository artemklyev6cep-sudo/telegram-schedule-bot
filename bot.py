import requests
from datetime import date, timedelta, datetime
from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import Command
import random
import logging
import os
import sys
import asyncio
import re

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
    """Упрощенный парсинг без lxml"""
    if for_date is None:
        for_date = date.today()
    week_type = get_week_type(for_date)
    URL = f"http://r.sf-misis.ru/group/{GROUP_ID}/{week_type}"
    
    try:
        resp = requests.get(URL, timeout=10)
        resp.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе расписания: {e}")
        return {}, week_type
    
    html_content = resp.text
    schedule = {day: [] for day in DAYS_ORDER}
    
    # Упрощенный парсинг с помощью регулярных выражений
    # Ищем таблицу расписания
    table_match = re.search(r'<table[^>]*id="schedule-table"[^>]*>(.*?)</table>', html_content, re.DOTALL)
    
    if not table_match:
        return schedule, week_type
    
    table_html = table_match.group(1)
    
    # Простой парсинг строк таблицы
    # Это упрощенная версия - в реальном боте нужно доработать
    # под вашу конкретную структуру таблицы
    
    # Пример простого извлечения данных:
    current_day = None
    
    # Разбиваем на строки
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL)
    
    for row in rows[1:]:  # Пропускаем заголовок
        # Проверяем день недели
        day_match = re.search(r'<th[^>]*class="table-weekdays"[^>]*>(.*?)</th>', row)
        if day_match:
            day_name = day_match.group(1).strip()
            if day_name in DAYS_ORDER:
                current_day = day_name
                continue
        
        if not current_day:
            continue
        
        # Ищем занятия в строке
        # Это нужно адаптировать под вашу конкретную структуру таблицы
        lessons = re.findall(r'<td[^>]*class="[^"]*table-single[^"]*"[^>]*>(.*?)</td>', row, re.DOTALL)
        lessons += re.findall(r'<td[^>]*class="[^"]*table-subgroups[^"]*"[^>]*>(.*?)</td>', row, re.DOTALL)
        
        for lesson_html in lessons:
            # Извлекаем предмет
            subject_match = re.search(r'<div[^>]*class="table-subject"[^>]*>(.*?)</div>', lesson_html, re.DOTALL)
            if subject_match:
                subject = re.sub(r'<[^>]+>', '', subject_match.group(1)).strip()
                if subject:
                    # Упрощенная запись
                    schedule[current_day].append(f"- {subject}")
    
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

# ========== ЗАПУСК ==========

if __name__ == "__main__":
    try:
        logger.info("🚀 Запуск бота...")
        dp.run_polling(bot, skip_updates=True)
    except Exception as e:
        logger.error(f"❌ Ошибка запуска: {e}")




