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
    
    # Получаем дату из callback_data (формат: add_YYYY-MM-DD)
    _, date_str = query.data.split('_', 1)
    
    # Инициализируем данные события
    context.user_data['event_data'] = {
        'date': date_str
    }
    
    await query.edit_message_text("Введите название события:")
    return SETTING_TITLE
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

async def set_event_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Инициализируем словарь, если его нет
    if 'event_data' not in context.user_data:
        context.user_data['event_data'] = {}
    
    context.user_data['event_data']['title'] = update.message.text
    await update.message.reply_text("Введите время события (формат ЧЧ:ММ):")
    return SETTING_TIME

async def set_event_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        time_obj = datetime.strptime(update.message.text, "%H:%M").time()
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
    try:
        await query.answer()
        
        # Проверяем наличие необходимых данных
        if 'event_data' not in context.user_data:
            raise ValueError("Данные события не найдены")
        
        # Получаем минуты напоминания
        if not query.data.startswith('reminder_'):
            raise ValueError("Неверный формат callback_data")
            
        _, minutes_str = query.data.split('_')
        try:
            minutes = int(minutes_str)
        except ValueError:
            raise ValueError("Неверное значение минут напоминания")
        
        # Проверяем время события
        event_data = context.user_data['event_data']
        event_time = datetime.combine(
            datetime.strptime(event_data['date'], "%Y-%m-%d").date(),
            event_data['time']
        )
        
        # Проверяем, не прошло ли уже время события
        if event_time < datetime.now():
            raise ValueError("Время события уже прошло")
        
        # Проверяем, чтобы напоминание было до события
        reminder_time = event_time - timedelta(minutes=minutes)
        if reminder_time < datetime.now():
            raise ValueError("Время напоминания уже прошло")
        
        # Сохраняем событие в БД
        try:
            user = User.get(user_id=update.effective_user.id)
            event = Event.create(
                user=user,
                name=event_data['title'],
                date=datetime.strptime(event_data['date'], "%Y-%m-%d").date(),
                time=event_data['time'],
                reminder_minutes=minutes
            )
        except Exception as db_error:
            raise ValueError(f"Ошибка сохранения в БД: {db_error}")
        
        # Планируем напоминание
        try:
            if not setup_scheduler(context.job_queue, event, user.user_id):
                raise ValueError("Не удалось запланировать напоминание")
        except Exception as scheduler_error:
            raise ValueError(f"Ошибка планировщика: {scheduler_error}")
        
        # Формируем сообщение об успехе
        success_text = (
            f"✅ Событие успешно создано!\n\n"
            f"📌 Название: {event_data['title']}\n"
            f"⏰ Время: {event_data['time'].strftime('%H:%M')}\n"
            f"🔔 Напоминание за: {minutes} минут"
        )
        
        # Отправляем сообщение
        try:
            await query.edit_message_text(
                text=success_text,
                reply_markup=get_week_keyboard()[1]
            )
        except Exception as msg_error:
            logging.error(f"Ошибка редактирования сообщения: {msg_error}")
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=success_text,
                reply_markup=get_week_keyboard()[1]
            )
        
        # Очищаем временные данные
        context.user_data.pop('event_data', None)
        return ConversationHandler.END
        
    except ValueError as ve:
        error_text = f"⚠️ Ошибка: {str(ve)}"
        logging.error(error_text)
        
        # Пытаемся отредактировать сообщение или отправить новое
        try:
            await query.edit_message_text(
                text=error_text,
                reply_markup=get_reminder_keyboard()
            )
        except Exception:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=error_text,
                reply_markup=get_reminder_keyboard()
            )
        return SETTING_REMINDER
        
    except Exception as e:
        error_text = "⚠️ Произошла непредвиденная ошибка. Пожалуйста, попробуйте позже."
        logging.error(f"Необработанная ошибка: {str(e)}")
        
        try:
            await query.edit_message_text(
                text=error_text,
                reply_markup=get_week_keyboard()[1]
            )
        except Exception:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=error_text,
                reply_markup=get_week_keyboard()[1]
            )
        return ConversationHandler.END

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