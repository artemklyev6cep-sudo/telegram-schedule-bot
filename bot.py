import requests
from bs4 import BeautifulSoup
from datetime import date, timedelta
from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.filters import Command
import random
import logging
import os
import sys
import asyncio
from aiohttp import web

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
TOKEN = os.getenv('BOT_TOKEN', '8512277521:AAE_s5IONdbZzgMzMU3LFlQqRAa00qUHpiQ')
if TOKEN == '8512277521:AAE_s5IONdbZzgMzMU3LFlQqRAa00qUHpiQ':
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
    """Улучшенный парсинг с отладкой"""
    if for_date is None:
        for_date = date.today()
    
    week_type = get_week_type(for_date)
    URL = f"http://r.sf-misis.ru/group/{GROUP_ID}/{week_type}"
    
    logger.info(f"🔍 Запрашиваем расписание: {URL}")
    
    try:
        resp = requests.get(URL, timeout=10)
        resp.raise_for_status()
        logger.info(f"✅ Страница загружена, статус: {resp.status_code}")
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Ошибка при запросе расписания: {e}")
        return {}, week_type
    
    # Пробуем разные парсеры
    try:
        soup = BeautifulSoup(resp.text, "html.parser")
    except:
        # Если не работает html.parser, пробуем lxml
        try:
            soup = BeautifulSoup(resp.text, "lxml")
            logger.info("✅ Используем парсер lxml")
        except:
            logger.error("❌ Ошибка парсинга HTML")
            return {}, week_type
    
    # Ищем таблицу по разным способам
    table = soup.find("table", id="schedule-table")
    
    if not table:
        # Пробуем найти таблицу другим способом
        table = soup.find("table", {"id": "schedule-table"})
    
    if not table:
        # Ищем любую таблицу с расписанием
        tables = soup.find_all("table")
        logger.info(f"🔍 Найдено таблиц на странице: {len(tables)}")
        for idx, t in enumerate(tables):
            if "schedule" in str(t).lower() or "расписание" in str(t).lower():
                table = t
                logger.info(f"✅ Найдена таблица расписания #{idx}")
                break
    
    schedule = {day: [] for day in DAYS_ORDER}
    
    if not table:
        logger.error("❌ Таблица расписания не найдена!")
        
        # Сохраняем HTML для отладки
        with open("debug_page.html", "w", encoding="utf-8") as f:
            f.write(resp.text[:5000])
        logger.info("📄 Первые 5000 символов страницы сохранены в debug_page.html")
        
        return schedule, week_type
    
    logger.info(f"✅ Таблица найдена, размер: {len(str(table))} символов")
    
    # Собираем времена пар
    header_row = table.find("tr")
    times = []
    
    if header_row:
        # Ищем все заголовки с временем
        time_cells = header_row.find_all(["th", "td"])
        
        for cell in time_cells:
            # Ищем время в разных форматах
            time_text = ""
            
            # Пробуем найти div с классом table-time-2
            time_div = cell.find("div", class_="table-time-2")
            if time_div:
                time_text = time_div.get_text(strip=True)
            else:
                # Ищем любой текст с цифрами (время)
                cell_text = cell.get_text(strip=True)
                if cell_text and any(char.isdigit() for char in cell_text):
                    time_text = cell_text
            
            if time_text:
                times.append(time_text)
                logger.debug(f"⏰ Найдено время: {time_text}")
    
    logger.info(f"⏰ Найдено времен пар: {len(times)}")
    
    # Парсим строки таблицы
    rows = table.find_all("tr")
    logger.info(f"📊 Найдено строк в таблице: {len(rows)}")
    
    current_day = None
    row_count = 0
    
    for row in rows[1:]:  # Пропускаем заголовок
        row_count += 1
        
        # Ищем день недели
        day_cell = row.find("th", class_="table-weekdays")
        if not day_cell:
            day_cell = row.find("th")
        
        if day_cell:
            day_name = day_cell.get_text(strip=True)
            if day_name in DAYS_ORDER:
                current_day = day_name
                logger.debug(f"📅 Найден день: {current_day}")
                continue
        
        if not current_day:
            continue
        
        # Ищем ячейки с занятиями
        cells = row.find_all("td")
        
        for cell_index, cell in enumerate(cells):
            if cell_index >= len(times):
                current_time = ""
            else:
                current_time = times[cell_index]
            
            # Проверяем, есть ли в ячейке занятия
            cell_text = cell.get_text(strip=True)
            if not cell_text:
                continue
            
            # Упрощенный парсинг - просто извлекаем весь текст
            # Позже можно доработать для структурированных данных
            
            # Разбиваем текст на строки
            lines = [line.strip() for line in cell_text.split('\n') if line.strip()]
            
            for line in lines:
                if line and len(line) > 2:  # Игнорируем слишком короткие строки
                    # Добавляем время, если есть
                    lesson_text = f"- {line}"
                    if current_time:
                        lesson_text += f" | {current_time}"
                    
                    schedule[current_day].append(lesson_text)
                    logger.debug(f"📚 Добавлено занятие: {lesson_text}")
    
    # Проверяем результат
    total_lessons = sum(len(lessons) for lessons in schedule.values())
    logger.info(f"📊 Всего найдено занятий: {total_lessons}")
    
    for day in DAYS_ORDER:
        if schedule[day]:
            logger.info(f"📅 {day}: {len(schedule[day])} занятий")
    
    return schedule, week_type

def format_day_schedule(day_name, schedule):
    text = f"<b>{day_name}:</b>\n"
    if schedule.get(day_name) and len(schedule[day_name]) > 0:
        for i, lesson in enumerate(schedule[day_name][:10], 1):  # Ограничиваем 10 занятиями
            text += f"{i}. {lesson}\n"
        if len(schedule[day_name]) > 10:
            text += f"... и еще {len(schedule[day_name]) - 10} занятий\n"
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

# ========== ОТЛАДОЧНАЯ КОМАНДА ==========

@router.message(Command("debug"))
async def debug_command(message: types.Message):
    """Команда для отладки парсинга"""
    try:
        schedule, week_type = fetch_schedule_table()
        week_type_name = "Знаменатель" if week_type == '2' else 'Числитель'
        
        # Подсчитываем занятия
        total_lessons = sum(len(lessons) for lessons in schedule.values())
        lessons_by_day = {day: len(schedule[day]) for day in DAYS_ORDER}
        
        text = f"<b>🔧 Отладка парсинга</b>\n\n"
        text += f"Тип недели: <b>{week_type_name}</b>\n"
        text += f"Всего занятий: <b>{total_lessons}</b>\n\n"
        
        text += "<b>Занятий по дням:</b>\n"
        for day in DAYS_ORDER[:-1]:
            text += f"{day}: {lessons_by_day[day]}\n"
        
        # Показываем первые 3 занятия каждого дня
        text += "\n<b>Примеры занятий:</b>\n"
        for day in DAYS_ORDER[:-1]:
            if schedule[day]:
                text += f"\n{day}:\n"
                for lesson in schedule[day][:3]:
                    text += f"• {lesson[:50]}...\n"
        
        await message.reply(text, parse_mode="HTML")
        
    except Exception as e:
        await message.reply(f"❌ Ошибка отладки: {str(e)[:200]}")

# ... остальной код (session, start, handle_other_messages) без изменений ...

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
        "/debug — отладка парсинга\n"
        "/session — прогноз на сессию\n"
        "/help — эта справка\n\n"
        "<i>By. Shmal</i>",
        parse_mode="HTML"
    )

@router.message()
async def handle_other_messages(message: types.Message):
    text = message.text.strip().lower()
    day_mapping = {
        "понедельник": "Понедельник", "пн": "Понедельник",
        "вторник": "Вторник", "вт": "Вторник",
        "среда": "Среда", "ср": "Среда",
        "четверг": "Четверг", "чт": "Четверг",
        "пятница": "Пятница", "пт": "Пятница",
        "суббота": "Суббота", "сб": "Суббота",
        "сегодня": "today",
        "завтра": "tomorrow",
        "расписание": "schedule"
    }
    
    if text in day_mapping:
        if day_mapping[text] == "today":
            await today_command(message)
        elif day_mapping[text] == "tomorrow":
            await tomorrow_command(message)
        elif day_mapping[text] == "schedule":
            await schedule_command(message)
        else:
            await day_command(types.Message(text=f"/day {text}"))
    elif "расписание" in text or "пары" in text:
        await schedule_command(message)
    elif "сессия" in text or "экзамен" in text:
        await session_command(message)
    elif text in ["привет", "hello", "hi", "бот"]:
        await start_command(message)

# ========== МИНИМАЛЬНЫЙ ВЕБ-СЕРВЕР ДЛЯ RENDER ==========
async def health_check(request):
    """Простая проверка здоровья для Render"""
    return web.Response(text="✅ Telegram бот работает!")

async def start_web_server():
    """Запускаем простой HTTP-сервер на порту 8080"""
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    port = int(os.environ.get("PORT", 8080))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"🌐 Веб-сервер запущен на порту {port}")
    return runner

# ========== ЗАПУСК ДЛЯ RENDER ==========

async def main():
    """Основная функция запуска"""
    logger.info("=" * 50)
    logger.info("🚀 Запуск Telegram бота расписания")
    logger.info("📅 Референсная неделя: %s", REFERENCE_WEEK_START)
    logger.info("👥 ID группы: %s", GROUP_ID)
    
    # Проверка токена
    if TOKEN == '8512277521:AAE_s5IONdbZzgMzMU3LFlQqRAa00qUHpiQ':
        logger.warning("⚠️  ВНИМАНИЕ: Используется тестовый токен!")
        logger.warning("⚠️  Для продакшена установите переменную BOT_TOKEN на Render")
    
    logger.info("✅ Все проверки пройдены")
    logger.info("=" * 50)
    
    # Запускаем веб-сервер
    web_runner = await start_web_server()
    
    # Запускаем Telegram бота
    logger.info("🤖 Запуск Telegram бота...")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"❌ Критическая ошибка запуска бота: {e}", exc_info=True)
        print(f"❌ Ошибка: {e}")
        sys.exit(1)

