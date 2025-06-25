import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from database import initialize_db, User, Event
from keyboards import get_week_keyboard, get_reminder_keyboard
from scheduler import setup_scheduler
from datetime import datetime
from config import TIMEZONE
import pytz

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния ConversationHandler
SELECTING_ACTION, ADDING_EVENT, SETTING_TIME, SETTING_REMINDER = range(4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /start"""
    user_id = update.effective_user.id
    User.get_or_create(user_id=user_id)
    
    week_info, keyboard = get_week_keyboard()
    await update.message.reply_text(
        f"📅 Добро пожаловать в планировщик!\n\n{week_info}",
        reply_markup=keyboard
    )

async def show_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать неделю"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "current_week":
        week_info, keyboard = get_week_keyboard()
        await query.edit_message_text(
            f"📅 Текущая неделя:\n\n{week_info}",
            reply_markup=keyboard
        )
        return
    
    _, week_num, year = query.data.split('_')
    week_num, year = int(week_num), int(year)
    
    tz = pytz.timezone(TIMEZONE)
    try:
        date = datetime.strptime(f"{year}-W{week_num}-1", "%Y-W%W-%w").date()
        date = tz.localize(datetime.combine(date, datetime.min.time()))
    except ValueError:
        date = datetime.now(tz)
    
    week_info, keyboard = get_week_keyboard(date)
    await query.edit_message_text(
        f"📅 Выбранная неделя:\n\n{week_info}",
        reply_markup=keyboard
    )

async def show_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать события дня"""
    query = update.callback_query
    await query.answer()
    
    _, date_str = query.data.split('_')
    tz = pytz.timezone(TIMEZONE)
    date = datetime.strptime(date_str, "%Y-%m-%d").date()
    
    user = User.get(user_id=query.from_user.id)
    events = Event.select().where(
        (Event.user == user) & 
        (Event.date == date)
    ).order_by(Event.time)
    
    week_num = date.isocalendar()[1]
    total_weeks = datetime(date.year, 12, 28).isocalendar()[1]
    week_info = f"Неделя {week_num} из {total_weeks}\n"
    
    if events:
        text = f"{week_info}События на {date.strftime('%d.%m.%Y')}:\n\n" + \
               "\n".join(f"⏰ {e.time.strftime('%H:%M')} - {e.name}" for e in events)
    else:
        text = f"{week_info}На {date.strftime('%d.%m.%Y')} событий нет."
    
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("Добавить событие", callback_data=f"add_{date_str}"),
        InlineKeyboardButton("Назад к неделе", callback_data="back_to_week")
    ]])
    
    await query.edit_message_text(text, reply_markup=keyboard)

async def back_to_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат к просмотру недели"""
    await show_week(update, context)

async def add_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления события"""
    query = update.callback_query
    await query.answer()
    
    _, date_str = query.data.split('_')
    context.user_data['event_date'] = date_str
    await query.edit_message_text("Введите название события:")
    return ADDING_EVENT

async def save_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение названия события"""
    context.user_data['event_name'] = update.message.text
    await update.message.reply_text("Введите время события (формат ЧЧ:ММ):")
    return SETTING_TIME

async def set_event_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установка времени события"""
    try:
        time = datetime.strptime(update.message.text, "%H:%M").time()
        context.user_data['event_time'] = time
        await update.message.reply_text(
            "Выберите время напоминания:",
            reply_markup=get_reminder_keyboard()
        )
        return SETTING_REMINDER
    except ValueError:
        await update.message.reply_text("Неверный формат времени. Попробуйте снова:")
        return SETTING_TIME

async def set_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение всего события"""
    query = update.callback_query
    await query.answer()
    
    _, minutes = query.data.split('_')
    tz = pytz.timezone(TIMEZONE)
    
    user = User.get(user_id=update.effective_user.id)
    event = Event.create(
        user=user,
        name=context.user_data['event_name'],
        date=datetime.strptime(context.user_data['event_date'], "%Y-%m-%d").date(),
        time=context.user_data['event_time'],
        reminder_minutes=int(minutes)
    )
    
    setup_scheduler(context.job_queue, event, user.user_id)
    
    date = tz.localize(datetime.combine(event.date, datetime.min.time()))
    week_info, keyboard = get_week_keyboard(date)
    
    await query.edit_message_text(
        f"✅ Событие добавлено!\n\n{week_info}",
        reply_markup=keyboard
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена операции"""
    await update.message.reply_text("Действие отменено")
    return ConversationHandler.END

def main():
    """Запуск бота"""
    initialize_db()
    
    application = Application.builder() \
        .token(BOT_TOKEN) \
        .concurrent_updates(True) \
        .build()
    
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_event, pattern='^add_')],
        states={
            ADDING_EVENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_event)],
            SETTING_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_event_time)],
            SETTING_REMINDER: [CallbackQueryHandler(set_reminder, pattern='^reminder_')]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=True
    )
    
    handlers = [
        CommandHandler('start', start),
        CallbackQueryHandler(show_week, pattern='^week_|^current_week|^back_to_week$'),
        CallbackQueryHandler(show_day, pattern='^day_'),
        conv_handler
    ]
    
    for handler in handlers:
        application.add_handler(handler)
    
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    from config import BOT_TOKEN
    main()