from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime, timedelta
from config import TIMEZONE
import pytz
import calendar
import logging
logger = logging.getLogger(__name__)

def get_week_keyboard(current_date=None):
    """Генерация клавиатуры с днями недели"""
    try:
        tz = pytz.timezone(TIMEZONE)
        now = datetime.now(tz)
        current_date = current_date or now
        
        year = current_date.year
        week_num = current_date.isocalendar()[1]
        week_start = current_date - timedelta(days=current_date.weekday())
        
        # Кнопки дней недели
        day_buttons = []
        for i in range(7):
            day = week_start + timedelta(days=i)
            day_str = day.strftime('%Y-%m-%d')  # Формат должен совпадать с обработчиком
            day_buttons.append(
                InlineKeyboardButton(
                    day.strftime('%a %d.%m'),
                    callback_data=f"day_{day_str}"  # Важно: строка, а не число
                )
            )
        
        # Кнопки навигации
        nav_buttons = [
            InlineKeyboardButton("<< Пред", callback_data="prev_week"),
            InlineKeyboardButton("Сегодня", callback_data="current_week"),
            InlineKeyboardButton("След >>", callback_data="next_week")
        ]
        
        # Собираем клавиатуру
        keyboard = [nav_buttons, day_buttons[:3], day_buttons[3:]]
        
        return (
            f"Неделя {week_num}",
            InlineKeyboardMarkup(keyboard)
        )
    except Exception as e:
        logger.error(f"Ошибка в get_week_keyboard(): {str(e)}")
        raise

def get_day_keyboard(date_str):
    """Клавиатура для просмотра событий дня с кнопкой 'Назад к неделе'"""
    keyboard = [
        [InlineKeyboardButton("Добавить событие", callback_data=f"add_{date_str}")],
        [InlineKeyboardButton("Назад к неделе", callback_data="back_to_week")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_reminder_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("За 5 мин", callback_data="reminder_5")],
        [InlineKeyboardButton("За 15 мин", callback_data="reminder_15")],
        [InlineKeyboardButton("За 30 мин", callback_data="reminder_30")],
        [InlineKeyboardButton("За 1 час", callback_data="reminder_60")],
        [InlineKeyboardButton("За 2 часа", callback_data="reminder_120")],
        [InlineKeyboardButton("Назад", callback_data="back_to_time")]
    ])