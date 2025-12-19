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
        
        # Ищем текст расписания сессии
        all_text = soup.get_text(separator='\n')
        lines = all_text.split('\n')
        
        # Ищем начало расписания сессии
        start_index = -1
        for i, line in enumerate(lines):
            if 'Расписание сессии' in line:
                start_index = i
                break
        
        if start_index == -1:
            # Альтернативный поиск
            for i, line in enumerate(lines):
                if 'сесси' in line.lower():
                    start_index = i
                    break
        
        if start_index == -1:
            logger.warning("Не найдено расписание сессии на странице")
            return []
        
        # Собираем строки с расписанием
        session_lines = []
        for i in range(start_index + 1, len(lines)):
            line = lines[i].strip()
            if line and len(line) > 5:
                # Если встречаем пустую строку после блока расписания - останавливаемся
                if i > start_index + 20:  # Ограничиваем поиск 20 строками после заголовка
                    break
                session_lines.append(line)
        
        # Объединяем строки в один текст для парсинга
        session_text = '\n'.join(session_lines)
        
        # Паттерны для парсинга
        # Ищем строки вида: "Предмет (Тип) Дата, Время Аудитория, Преподаватель"
        # Пример: "Современные информационные технологии (Консультация) 13.01.2026, с 09:00 до 10:30 2/202, Верзилина Ольга Александровна"
        
        # Разделяем по преподавателям (русские ФИО с заглавных букв)
        patterns = [
            # Паттерн 1: Разделение по ФИО преподавателя
            r'(.+?)\s*(\d{2}\.\d{2}\.\d{4}),\s*(с \d{2}:\d{2} до \d{2}:\d{2})\s*([^,]+),\s*([А-Я][а-я]+ [А-Я][а-я]+ [А-Я][а-я]+)',
            # Паттерн 2: Без запятой перед ФИО
            r'(.+?)\s*(\d{2}\.\d{2}\.\d{4}),\s*(с \d{2}:\d{2} до \d{2}:\d{2})\s*([^,]+)\s*([А-Я][а-я]+ [А-Я][а-я]+ [А-Я][а-я]+)',
        ]
        
        exams = []
        
        # Сначала пробуем найти все совпадения по паттерну
        for pattern in patterns:
            matches = re.findall(pattern, session_text)
            if matches:
                for match in matches:
                    subject_type = match[0].strip()
                    date_str = match[1].strip()
                    time_str = match[2].strip()
                    room = match[3].strip()
                    teacher = match[4].strip()
                    
                    # Разделяем предмет и тип
                    subject = subject_type
                    exam_type = ""
                    
                    # Ищем тип в скобках
                    type_match = re.search(r'\((Консультация|Экзамен)\)', subject_type)
                    if type_match:
                        exam_type = type_match.group(1)
                        subject = subject_type.replace(f'({exam_type})', '').strip()
                    
                    exams.append({
                        'subject': subject,
                        'type': exam_type,
                        'date': date_str,
                        'time': time_str,
                        'room': room,
                        'teacher': teacher
                    })
                break
        
        # Если не нашли по паттерну, пробуем другой подход
        if not exams:
            # Разбиваем текст по датам
            date_pattern = r'\d{2}\.\d{2}\.\d{4}'
            parts = re.split(f'({date_pattern})', session_text)
            
            for i in range(1, len(parts), 2):
                if i + 1 < len(parts):
                    date_str = parts[i].strip()
                    rest = parts[i + 1].strip()
                    
                    # Ищем время
                    time_match = re.search(r'с \d{2}:\d{2} до \d{2}:\d{2}', rest)
                    if time_match:
                        time_str = time_match.group(0)
                        
                        # Разделяем остальную часть
                        rest_parts = rest.split(time_str)
                        if len(rest_parts) >= 2:
                            subject_part = rest_parts[0].strip()
                            after_time = rest_parts[1].strip()
                            
                            # Ищем аудиторию и преподавателя
                            room_teacher_parts = after_time.split(',')
                            room = room_teacher_parts[0].strip() if len(room_teacher_parts) > 0 else ""
                            teacher = room_teacher_parts[1].strip() if len(room_teacher_parts) > 1 else ""
                            
                            # Разделяем предмет и тип
                            subject = subject_part
                            exam_type = ""
                            
                            type_match = re.search(r'\((Консультация|Экзамен)\)', subject_part)
                            if type_match:
                                exam_type = type_match.group(1)
                                subject = subject_part.replace(f'({exam_type})', '').strip()
                            
                            exams.append({
                                'subject': subject,
                                'type': exam_type,
                                'date': date_str,
                                'time': time_str,
                                'room': room,
                                'teacher': teacher
                            })
        
        logger.info(f"Найдено {len(exams)} записей о сессии")
        return exams
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при запросе расписания сессии: {e}")
        return []
    except Exception as e:
        logger.error(f"Ошибка при парсинге расписания сессии: {e}", exc_info=True)
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
        
        # Сортируем по дате
        exam_schedule.sort(key=lambda x: datetime.strptime(x['date'], '%d.%m.%Y'))
        
        text = "<b>📅 Расписание сессии:</b>\n\n"
        
        for exam in exam_schedule:
            # Определяем эмодзи по типу
            if exam['type'] == "Консультация":
                emoji = "💬"
                type_text = "Консультация"
            elif exam['type'] == "Экзамен":
                emoji = "📝"
                type_text = "Экзамен"
            else:
                emoji = "📚"
                type_text = exam['type'] if exam['type'] else "Занятие"
            
            text += f"{emoji} <b>{exam['subject']}</b>\n"
            text += f"   🏷️ <i>{type_text}</i>\n"
            text += f"   📅 {exam['date']}\n"
            text += f"   ⏰ {exam['time']}\n"
            text += f"   🏫 {exam['room']}\n"
            text += f"   👨‍🏫 {exam['teacher']}\n\n"
        
        text += f"\n<i>Загружено: {datetime.now().strftime('%d.%m.%Y %H:%M')}</i>"
        
        await message.reply(text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Ошибка в exam_command: {e}", exc_info=True)
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

@dp.message_handler()
async def handle_other_messages(message: types.Message):
    """Обработка только сообщения 'бот'"""
    text = message.text.strip().lower()
    
    # Реагируем только на сообщение "бот"
    if text == "бот":
        await start_command(message)

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







