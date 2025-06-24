from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime, timedelta
import calendar

def get_week_keyboard(current_date=None):
    if not current_date:
        current_date = datetime.now()
    
    year = current_date.year
    week_num = current_date.isocalendar()[1]
    total_weeks = datetime(year, 12, 28).isocalendar()[1]  # Примерное количество недель
    
    # Кнопки дней недели
    buttons = []
    week_start = current_date - timedelta(days=current_date.weekday())
    
    for i in range(7):
        day = week_start + timedelta(days=i)
        buttons.append(InlineKeyboardButton(
            f"{day.strftime('%a %d.%m')}", 
            callback_data=f"day_{day.strftime('%Y-%m-%d')}"
        ))
    
    # Кнопки навигации
    navigation = [
        InlineKeyboardButton("<< Пред", callback_data=f"week_{week_num-1}_{year}"),
        InlineKeyboardButton(f"Неделя {week_num}/{total_weeks}", callback_data="current_week"),
        InlineKeyboardButton("След >>", callback_data=f"week_{week_num+1}_{year}")
    ]
    
    return InlineKeyboardMarkup([navigation, *[buttons[:3], buttons[3:]]])