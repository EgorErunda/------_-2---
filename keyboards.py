from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime, timedelta
from config import TIMEZONE
import pytz
import calendar

def get_week_keyboard(current_date=None):
    """Генерация клавиатуры с днями недели"""
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    
    if not current_date:
        current_date = now
    
    year = current_date.year
    week_num = current_date.isocalendar()[1]
    total_weeks = datetime(year, 12, 28, tzinfo=tz).isocalendar()[1]
    
    week_start = current_date - timedelta(days=current_date.weekday())
    days = [(week_start + timedelta(days=i)) for i in range(7)]
    
    # Кнопки дней недели
    day_buttons = [
        InlineKeyboardButton(
            day.strftime('%a %d.%m'),
            callback_data=f"day_{day.strftime('%Y-%m-%d')}"
        ) for day in days
    ]
    
    # Кнопки навигации
    nav_buttons = [
        InlineKeyboardButton("<< Пред", callback_data=f"week_{week_num-1}_{year}"),
        InlineKeyboardButton("Сегодня", callback_data="current_week"),
        InlineKeyboardButton("След >>", callback_data=f"week_{week_num+1}_{year}")
    ]
    
    # Собираем клавиатуру
    keyboard = [nav_buttons, day_buttons[:3], day_buttons[3:]]
    
    return (
        f"Неделя {week_num} из {total_weeks}",
        InlineKeyboardMarkup(keyboard)
    )

def get_day_keyboard(date_str):
    """Клавиатура для просмотра событий дня с кнопкой 'Назад к неделе'"""
    keyboard = [
        [InlineKeyboardButton("Добавить событие", callback_data=f"add_{date_str}")],
        [InlineKeyboardButton("Назад к неделе", callback_data="back_to_week")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_reminder_keyboard():
    """Клавиатура выбора времени напоминания"""
    buttons = [
        [InlineKeyboardButton(f"За {mins} минут", callback_data=f"reminder_{mins}")]
        for mins in [5, 15, 30, 60, 120, 1440]
    ]
    return InlineKeyboardMarkup(buttons)