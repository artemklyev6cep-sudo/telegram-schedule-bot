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
    
    # ВАЖНО: используем html.parser вместо lxml
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", id="schedule-table")
    schedule = {day: [] for day in DAYS_ORDER}

    if not table:
        logger.warning("Таблица расписания не найдена")
        return schedule, week_type

    # Собираем времена пар из заголовка таблицы
    header_row = table.find("tr")
    times = []
    time_cells = header_row.find_all("th")[1:]  # Пропускаем первый th с днями недели
    
    for th in time_cells:
        time_div = th.find("div", class_="table-time-2")
        if time_div:
            times.append(time_div.get_text(strip=True))
        else:
            time_text = th.get_text(strip=True)
            if time_text and any(char.isdigit() for char in time_text):
                times.append(time_text)
            else:
                times.append("")

    # Проходим по всем строкам таблицы
    current_day = None
    
    for row in table.find_all("tr")[1:]:
        day_th = row.find("th", class_="table-weekdays")
        if day_th:
            day_name = day_th.get_text(strip=True)
            if day_name in DAYS_ORDER:
                current_day = day_name
                continue
        
        if not current_day:
            continue

        cells = row.find_all("td")
        
        for cell_index, cell in enumerate(cells):
            if cell_index >= len(times):
                continue
                
            current_time = times[cell_index] if cell_index < len(times) else ""
            cell_classes = cell.get("class", [])
            
            if not cell.get_text(strip=True):
                continue
            
            # Обычные занятия (без подгрупп)
            if "table-single" in cell_classes:
                subject = cell.find("div", class_="table-subject")
                teacher = cell.find("div", class_="table-teacher")
                room = cell.find("div", class_="table-room")
                
                if subject and subject.get_text(strip=True):
                    lesson_text = f"- {subject.get_text(strip=True)}"
                    if current_time:
                        lesson_text += f" | {current_time}"
                    if room and room.get_text(strip=True):
                        lesson_text += f" | {room.get_text(strip=True)}"
                    if teacher and teacher.get_text(strip=True):
                        lesson_text += f" | {teacher.get_text(strip=True)}"
                    
                    schedule[current_day].append(lesson_text)
            
            # Занятия с подгруппами
            elif "table-subgroups" in cell_classes:
                subgroups = cell.find_all("div", class_="table-subgroup-item")
                
                for subgroup in subgroups:
                    sg_name = subgroup.find("div", class_="table-sg-name")
                    subject = subgroup.find("div", class_="table-subject")
                    teacher = subgroup.find("div", class_="table-teacher")
                    room = subgroup.find("div", class_="table-room")
                    
                    if subject and subject.get_text(strip=True):
                        subgroup_num = ""
                        if sg_name and sg_name.get_text(strip=True):
                            sg_text = sg_name.get_text(strip=True)
                            if "подгруппа" in sg_text.lower():
                                subgroup_num = sg_text
                            elif any(str(i) in sg_text for i in range(1, 10)):
                                subgroup_num = f"Подгруппа {sg_text}"
                            else:
                                subgroup_num = sg_text
                        
                        lesson_text = f"- {subject.get_text(strip=True)}"
                        if subgroup_num:
                            lesson_text += f" ({subgroup_num})"
                        if current_time:
                            lesson_text += f" | {current_time}"
                        if room and room.get_text(strip=True):
                            lesson_text += f" | {room.get_text(strip=True)}"
                        if teacher and teacher.get_text(strip=True):
                            lesson_text += f" | {teacher.get_text(strip=True)}"
                        
                        schedule[current_day].append(lesson_text)
            
            # Если ячейка содержит занятия, но не имеет специального класса
            elif cell.get_text(strip=True):
                subject = cell.find("div", class_="table-subject") or cell.find("span", class_="table-subject")
                teacher = cell.find("div", class_="table-teacher") or cell.find("span", class_="table-teacher")
                room = cell.find("div", class_="table-room") or cell.find("span", class_="table-room")
                
                if subject and subject.get_text(strip=True):
                    lesson_text = f"- {subject.get_text(strip=True)}"
                    if current_time:
                        lesson_text += f" | {current_time}"
                    if room and room.get_text(strip=True):
                        lesson_text += f" | {room.get_text(strip=True)}"
                    if teacher and teacher.get_text(strip=True):
                        lesson_text += f" | {teacher.get_text(strip=True)}"
                    
                    schedule[current_day].append(lesson_text)
    
    # Удаляем дубликаты
    for day in DAYS_ORDER:
        unique_lessons = []
        seen = set()
        for lesson in schedule[day]:
            if lesson not in seen:
                seen.add(lesson)
                unique_lessons.append(lesson)
        schedule[day] = unique_lessons
    
    return schedule, week_type

def format_day_schedule(day_name, schedule):
    text = f"<b>{day_name}:</b>\n"
    if schedule.get(day_name) and len(schedule[day_name]) > 0:
        for lesson in schedule[day_name]:
            text += f"📚 {lesson}\n"
    else:
        text += "🎉 Нет занятий\n"
    return text

# ========== КОМАНДЫ БОТА (aiogram 3.x стиль) ==========

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

@router.message(Command("day"))
async def day_command(message: types.Message):
    try:
        # Получаем аргументы команды
        args = message.text.split()
        if len(args) < 2:
            await message.reply("Укажите день недели после команды /day\nНапример: /day понедельник")
            return
        
        day_input = args[1].strip().lower()
        
        day_mapping = {
            "понедельник": "Понедельник", "пн": "Понедельник",
            "вторник": "Вторник", "вт": "Вторник",
            "среда": "Среда", "ср": "Среда",
            "четверг": "Четверг", "чт": "Четверг",
            "пятница": "Пятница", "пт": "Пятница",
            "суббота": "Суббота", "сб": "Суббота"
        }
        
        if day_input not in day_mapping:
            await message.reply("Неверный день недели. Используйте: понедельник, вторник, среда, четверг, пятница, суббота")
            return
        
        day_name = day_mapping[day_input]
        schedule, week_type = fetch_schedule_table()
        week_type_name = "Знаменатель" if week_type == '2' else 'Числитель'
        
        text = f"<b>Расписание на {day_name.lower()} ({week_type_name}):</b>\n\n"
        text += format_day_schedule(day_name, schedule)
        await message.reply(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка в day_command: {e}")
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
        "/day [день] — на конкретный день\n"
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

# ========== ЗАПУСК ДЛЯ RENDER ==========

async def on_startup(_):
    """Функция запуска для Render"""
    logger.info("🚀 Бот запускается на Render...")
    logger.info(f"👥 ID группы: {GROUP_ID}")
    logger.info(f"📅 Референсная неделя: {REFERENCE_WEEK_START}")
    logger.info("✅ Бот успешно запущен и готов к работе!")
    print("=" * 50)
    print("🤖 Telegram Schedule Bot")
    print("🚀 Успешно запущен на Render.com")
    print("📞 Напишите /start вашему боту")
    print("=" * 50)

if __name__ == "__main__":
    try:
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
        
        # Запуск бота для aiogram 3.x
        dp.run_polling(
            bot,
            skip_updates=True,
            on_startup=on_startup
        )
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка запуска бота: {e}", exc_info=True)
        print(f"❌ Ошибка: {e}")
        sys.exit(1)



