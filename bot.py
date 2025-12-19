import requests
from bs4 import BeautifulSoup
from datetime import date, timedelta, datetime
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import random
import logging
import os
import sys
import asyncio
import re

# ========== НАСТРОЙКИ ДЛЯ BOTHOST ==========
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)
# ===========================================

TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    logger.error("❌ Не найден BOT_TOKEN в переменных окружения!")
    raise ValueError("Установите BOT_TOKEN в настройках Bothost")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

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
    
    soup = BeautifulSoup(resp.text, "lxml")
    table = soup.find("table", id="schedule-table")
    schedule = {day: [] for day in DAYS_ORDER}

    if not table:
        return schedule, week_type

    header_row = table.find("tr")
    times = []
    time_cells = header_row.find_all("th")[1:]
    
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

    for row in table.find_all("tr")[1:]:
        day_th = row.find("th", class_="table-weekdays")
        current_day = None
        if day_th:
            day_name = day_th.get_text(strip=True)
            if day_name in DAYS_ORDER:
                current_day = day_name
        
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
    
    for day in DAYS_ORDER:
        unique_lessons = []
        seen = set()
        for lesson in schedule[day]:
            if lesson not in seen:
                seen.add(lesson)
                unique_lessons.append(lesson)
        schedule[day] = unique_lessons
    
    return schedule, week_type

def fetch_exam_schedule():
    """Получает расписание экзаменов с сайта"""
    try:
        URL = f"http://r.sf-misis.ru/group/{GROUP_ID}/1"
        resp = requests.get(URL, timeout=10)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, "lxml")
        
        exam_data = []
        
        session_header = soup.find(string=re.compile(r"Расписание сессии", re.IGNORECASE))
        
        if not session_header:
            session_header = soup.find(['h1', 'h2', 'h3', 'h4', 'div', 'p'], 
                                      string=re.compile(r"сесси", re.IGNORECASE))
        
        if session_header:
            parent = session_header.parent
            
            next_elements = []
            
            current = parent.find_next_sibling()
            for _ in range(10):
                if current and current.get_text(strip=True):
                    next_elements.append(current.get_text(strip=True))
                elif current and hasattr(current, 'find_all'):
                    text_elements = current.find_all(string=True, recursive=True)
                    for text in text_elements:
                        if text.strip() and len(text.strip()) > 10:
                            next_elements.append(text.strip())
                current = current.find_next_sibling() if current else None
            
            if not next_elements:
                all_text = parent.get_text(separator='\n', strip=True)
                lines = all_text.split('\n')
                found_header = False
                for line in lines:
                    if re.search(r"Расписание сессии", line, re.IGNORECASE):
                        found_header = True
                        continue
                    if found_header and line.strip():
                        next_elements.append(line.strip())
            
            for element in next_elements:
                if element and len(element) > 20:
                    lines = element.split('\n')
                    for line in lines:
                        line = line.strip()
                        if line and len(line) > 10:
                            exam_data.append(line)
        
        if not exam_data:
            all_text = soup.get_text(separator='\n')
            lines = all_text.split('\n')
            
            for line in lines:
                line = line.strip()
                if re.search(r'\d{2}\.\d{2}\.\d{4}.*\d{2}:\d{2}', line):
                    exam_data.append(line)
        
        cleaned_exams = []
        current_exam = []
        
        for line in exam_data:
            line = ' '.join(line.split())
            
            if '(' in line and ')' in line and any(word in line.lower() for word in ['экзамен', 'консультац']):
                if current_exam:
                    cleaned_exams.append(' '.join(current_exam))
                    current_exam = []
                current_exam.append(line)
            elif current_exam and (re.search(r'\d{2}\.\d{2}\.\d{4}', line) or '/' in line):
                current_exam.append(line)
                if any(char.isdigit() for char in line) and any(char.isalpha() for char in line):
                    cleaned_exams.append(' '.join(current_exam))
                    current_exam = []
            elif line:
                if not current_exam and any(word in line.lower() for word in ['экзамен', 'консультац']):
                    current_exam.append(line)
        
        if current_exam:
            cleaned_exams.append(' '.join(current_exam))
        
        unique_exams = []
        seen = set()
        for exam in cleaned_exams:
            if exam and exam not in seen:
                seen.add(exam)
                unique_exams.append(exam)
        
        logger.info(f"Найдено {len(unique_exams)} записей о сессии")
        return unique_exams
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе расписания сессии: {e}")
        return []
    except Exception as e:
        logger.error(f"Ошибка при парсинге расписания сессии: {e}")
        return []

def format_day_schedule(day_name, schedule):
    text = f"<b>{day_name}:</b>\n"
    if schedule.get(day_name) and len(schedule[day_name]) > 0:
        for lesson in schedule[day_name]:
            text += f"📚 {lesson}\n"
    else:
        text += "🎉 Нет занятий\n"
    return text

@dp.message_handler(commands=["exam"])
async def exam_command(message: types.Message):
    """Выводит расписание сессии"""
    try:
        exam_schedule = fetch_exam_schedule()
        
        if not exam_schedule:
            await message.reply(
                "❌ Не удалось загрузить расписание сессии.\n"
                "Попробуйте позже или проверьте сайт."
            )
            return
        
        text = "<b>📅 Расписание сессии:</b>\n\n"
        
        for i, exam in enumerate(exam_schedule, 1):
            exam_lines = exam.split(', ')
            if len(exam_lines) >= 3:
                subject_line = exam_lines[0]
                datetime_line = exam_lines[1] if len(exam_lines) > 1 else ""
                location_line = exam_lines[2] if len(exam_lines) > 2 else ""
                
                if "консультац" in subject_line.lower():
                    emoji = "💬"
                elif "экзамен" in subject_line.lower():
                    emoji = "📝"
                else:
                    emoji = "📚"
                
                text += f"{emoji} <b>{subject_line}</b>\n"
                text += f"   📅 {datetime_line}\n"
                text += f"   🏫 {location_line}\n\n"
            else:
                text += f"📌 {exam}\n\n"
        
        text += f"\n<i>Загружено: {datetime.now().strftime('%d.%m.%Y %H:%M')}</i>"
        
        await message.reply(text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка в exam_command: {e}")
        await message.reply(
            "❌ Ошибка при получении расписания сессии.\n"
            "Попробуйте позже."
        )

@dp.message_handler(commands=["schedule"])
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

@dp.message_handler(commands=["today"])
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

@dp.message_handler(commands=["tomorrow"])
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

@dp.message_handler(commands=["day"])
async def day_command(message: types.Message):
    try:
        args = message.get_args().strip().lower()
        
        if not args:
            await message.reply("Укажите день недели после команды /day\nНапример: /day понедельник")
            return
        
        day_mapping = {
            "понедельник": "Понедельник", "пн": "Понедельник",
            "вторник": "Вторник", "вт": "Вторник",
            "среда": "Среда", "ср": "Среда",
            "четверг": "Четверг", "чт": "Четверг",
            "пятница": "Пятница", "пт": "Пятница",
            "суббота": "Суббота", "сб": "Суббота"
        }
        
        if args not in day_mapping:
            await message.reply("Неверный день недели. Используйте: понедельник, вторник, среда, четверг, пятница, суббота")
            return
        
        day_name = day_mapping[args]
        schedule, week_type = fetch_schedule_table()
        week_type_name = "Знаменатель" if week_type == '2' else 'Числитель'
        
        text = f"<b>Расписание на {day_name.lower()} ({week_type_name}):</b>\n\n"
        text += format_day_schedule(day_name, schedule)
        await message.reply(text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка в day_command: {e}")
        await message.reply("❌ Ошибка при получении расписания.")

@dp.message_handler(commands=["session"])
async def session_command(message: types.Message):
    answers = [
        "✅ Сдашь!",
        "🎯 Пора бы вспомнить какой сегодня праздник...",
        "🤔 Отчислен!",
        "📚 Учись!",
        "🍀 Готовь подарки Некрасовой!",
    ]
    answer = random.choice(answers)
    await message.reply(f"🎓 Прогноз на сессию:\n\n{answer}")

@dp.message_handler(commands=["start", "help"])
async def start_command(message: types.Message):
    await message.reply(
        "📚 <b>Бот-расписание МИСИС</b>\n\n"
        "Доступные команды:\n"
        "/schedule — расписание на неделю\n"
        "/today — на сегодня\n"
        "/tomorrow — на завтра\n"
        "/day [день] — на конкретный день\n"
        "/exam — расписание сессии\n"
        "/session — прогноз на сессию\n"
        "/help — эта справка\n\n"
        "<i>By. Shmal</i>",
        parse_mode="HTML"
    )

# ИЗМЕНЕНО: Упрощена обработка текстовых сообщений
@dp.message_handler()
async def handle_other_messages(message: types.Message):
    """Обработка только сообщения 'бот'"""
    text = message.text.strip().lower()
    
    # Реагируем только на сообщение "бот"
    if text == "бот":
        await start_command(message)
    # Все остальные сообщения без '/' игнорируем
    else:
        # Можно добавить логирование, если нужно
        logger.debug(f"Игнорируем сообщение без команды: '{text}'")
        # Не отправляем ответ - бот просто игнорирует

async def on_startup(_):
    """Функция запуска для Bothost"""
    logger.info("🚀 Бот запускается на Bothost.ru...")
    logger.info(f"👥 ID группы: {GROUP_ID}")
    logger.info(f"📅 Референсная неделя: {REFERENCE_WEEK_START}")
    logger.info("✅ Бот успешно запущен и готов к работе!")
    print("=" * 50)
    print("🤖 Telegram Schedule Bot")
    print("🚀 Успешно запущен на Bothost.ru")
    print("📞 Напишите /start вашему боту")
    print("=" * 50)

# ========== ЗАПУСК ДЛЯ BOTHOST ==========
if __name__ == "__main__":
    try:
        logger.info("=" * 50)
        logger.info("🚀 Запуск Telegram бота расписания")
        logger.info("📅 Референсная неделя: %s", REFERENCE_WEEK_START)
        logger.info("👥 ID группы: %s", GROUP_ID)
        
        if not TOKEN:
            logger.error("❌ BOT_TOKEN не установлен!")
            raise ValueError("Установите BOT_TOKEN в переменных окружения Bothost")
        
        logger.info("✅ Все проверки пройдены")
        logger.info("=" * 50)
        
        import asyncio
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            logger.info("🤖 Запуск бота на Bothost.ru...")
            loop.run_until_complete(
                executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
            )
        except KeyboardInterrupt:
            logger.info("⏹️ Остановка бота...")
        finally:
            loop.close()
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка запуска бота: {e}", exc_info=True)
        print(f"❌ Ошибка: {e}")
        sys.exit(1)






