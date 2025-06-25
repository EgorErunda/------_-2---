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
from datetime import datetime, timedelta
from config import TIMEZONE, BOT_TOKEN
import pytz
#from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from keyboards import get_day_keyboard

tz = pytz.timezone(TIMEZONE)
now = datetime.now(tz)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния ConversationHandler
(
    SELECTING_ACTION,
    ADDING_EVENT,
    SETTING_TITLE,
    SETTING_TIME,
    SETTING_REMINDER
) = range(5)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка команды /start"""
    try:
        user_id = update.effective_user.id
        User.get_or_create(user_id=user_id)
        
        week_info, keyboard = get_week_keyboard()
        await update.message.reply_text(
            f"📅 Добро пожаловать в планировщик!\n\n{week_info}",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка в start(): {str(e)}")
        await update.message.reply_text("⚠️ Произошла ошибка при запуске. Попробуйте позже.")


async def show_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать неделю"""
    query = update.callback_query
    await query.answer()
    
    # Обработка кнопки "Назад к неделе"
    if query.data == "back_to_week":
        week_info, keyboard = get_week_keyboard()
        await query.edit_message_text(
            f"📅 Текущая неделя:\n\n{week_info}",
            reply_markup=keyboard
        )
        return
    
    # Обработка других callback_data
    try:
        if query.data.startswith('week_'):
            _, week_num, year = query.data.split('_')
            week_num, year = int(week_num), int(year)
        elif query.data == "current_week":
            week_info, keyboard = get_week_keyboard()
            await query.edit_message_text(
                f"📅 Текущая неделя:\n\n{week_info}",
                reply_markup=keyboard
            )
            return
    except ValueError as e:
        logging.error(f"Ошибка обработки callback_data: {query.data}, ошибка: {e}")
        await query.edit_message_text("Произошла ошибка. Попробуйте ещё раз.")
        return
    
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
    date = datetime.strptime(date_str, "%Y-%m-%d").date()
    
    # Получаем события из базы данных
    user = User.get(user_id=query.from_user.id)
    events = Event.select().where(
        (Event.user == user) & 
        (Event.date == date)
    ).order_by(Event.time)
    
    # Формируем текст сообщения
    if events:
        text = f"События на {date.strftime('%d.%m.%Y')}:\n\n" + \
               "\n".join(f"⏰ {e.time.strftime('%H:%M')} - {e.name}" for e in events)
    else:
        text = f"На {date.strftime('%d.%m.%Y')} событий нет."
    
    # Создаем клавиатуру
    keyboard = get_day_keyboard(date_str)
    
    await query.edit_message_text(text, reply_markup=keyboard)

async def back_to_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат к просмотру недели"""
    query = update.callback_query
    await query.answer()
    
    week_info, keyboard = get_week_keyboard()
    await query.edit_message_text(
        f"📅 Текущая неделя:\n\n{week_info}",
        reply_markup=keyboard
    )

async def add_event_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    _, date_str = query.data.split('_', 1)
    context.user_data['event_data'] = {'date': date_str}
    
    await query.edit_message_text("Введите название события:")
    return SETTING_TITLE


async def save_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сохранение названия события"""
    context.user_data['event_name'] = update.message.text
    await update.message.reply_text("Введите время события (формат ЧЧ:ММ):")
    return SETTING_TIME

async def set_event_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['event_data']['title'] = update.message.text
    await update.message.reply_text("Введите время события в формате ЧЧ:ММ (например, 14:30):")
    return SETTING_TIME

async def set_event_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        time_str = update.message.text.strip()
        time_obj = datetime.strptime(time_str, "%H:%M").time()
        
        # Сохраняем время с учетом временной зоны
        tz = pytz.timezone(TIMEZONE)
        event_date = datetime.strptime(context.user_data['event_data']['date'], "%Y-%m-%d").date()
        event_datetime = tz.localize(datetime.combine(event_date, time_obj))
        
        # Проверяем, что время еще не прошло
        if event_datetime < datetime.now(tz):
            await update.message.reply_text("Это время уже прошло. Введите будущее время:")
            return SETTING_TIME
            
        context.user_data['event_data']['time'] = time_obj
        await update.message.reply_text(
            "Выберите время напоминания:",
            reply_markup=get_reminder_keyboard()
        )
        return SETTING_REMINDER
        
    except ValueError:
        await update.message.reply_text("Неверный формат времени. Введите в формате ЧЧ:ММ:")
        return SETTING_TIME

async def set_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        _, minutes_str = query.data.split('_')
        minutes = int(minutes_str)
        event_data = context.user_data['event_data']
        
        # Получаем временную зону
        tz = pytz.timezone(TIMEZONE)
        event_date = datetime.strptime(event_data['date'], "%Y-%m-%d").date()
        event_time = event_data['time']
        event_datetime = tz.localize(datetime.combine(event_date, event_time))
        
        # Проверяем напоминание
        reminder_time = event_datetime - timedelta(minutes=minutes)
        if reminder_time < datetime.now(tz):
            await query.edit_message_text(
                "Напоминание не может быть раньше текущего времени",
                reply_markup=get_reminder_keyboard()
            )
            return SETTING_REMINDER
        
        # Создаем событие
        user = User.get(user_id=update.effective_user.id)
        event = Event.create(
            user=user,
            name=event_data['title'],
            date=event_date,
            time=event_time,
            reminder_minutes=minutes
        )
        
        # Настраиваем напоминание
        if not setup_scheduler(context.application.job_queue, event):
            raise ValueError("Не удалось запланировать напоминание")
        
        # Успешное завершение
        await query.edit_message_text(
            text=f"✅ Событие создано!\n{event_data['title']} в {event_time.strftime('%H:%M')}",
            reply_markup=get_week_keyboard()[1]
        )
        context.user_data.clear()
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Ошибка создания события: {e}", exc_info=True)
        await query.edit_message_text(
            text=f"Ошибка: {str(e)}",
            reply_markup=get_reminder_keyboard()
        )
        return SETTING_REMINDER

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена операции"""
    await update.message.reply_text("Действие отменено")
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Логируем ошибки и сообщаем пользователю"""
    logging.error(f"Ошибка: {context.error}", exc_info=True)
    
    if update.callback_query:
        await update.callback_query.answer("Произошла ошибка. Попробуйте ещё раз.")
    elif update.message:
        await update.message.reply_text("Произошла ошибка. Попробуйте ещё раз.")

def main():
    """Запуск бота"""
    initialize_db()
    
    #application.add_handler(CallbackQueryHandler(add_event, pattern='^add_'))
    #application.add_handler(CallbackQueryHandler(back_to_week, pattern='^back_to_week$'))

    application = Application.builder() \
        .token(BOT_TOKEN) \
        .concurrent_updates(True) \
        .build()
    
    application.add_error_handler(error_handler)

    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(add_event_start, pattern='^add_')
        ],
        states={
            SETTING_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_event_title)],
            SETTING_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_event_time)],
            SETTING_REMINDER: [CallbackQueryHandler(set_reminder, pattern='^reminder_')]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=False
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