import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ConversationHandler, MessageHandler, filters,
    ContextTypes
)
from database import initialize_db, User, Event
from scheduler import setup_scheduler
from datetime import datetime, timedelta
import calendar

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
SELECTING_ACTION, ADDING_EVENT, SETTING_TIME, SETTING_REMINDER = range(4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    User.get_or_create(user_id=user_id)
    
    week_info, keyboard = await get_week_keyboard()
    await update.message.reply_text(
        f"📅 Добро пожаловать в ваш персональный планировщик!\n\n{week_info}",
        reply_markup=keyboard
    )

async def get_week_keyboard(current_date=None):
    if not current_date:
        current_date = datetime.now()
    
    year = current_date.year
    week_num = current_date.isocalendar()[1]
    total_weeks = datetime(year, 12, 28).isocalendar()[1]
    
    # Формируем заголовок
    week_info = f"Неделя {week_num} из {total_weeks}\n"
    
    # Создаем кнопки дней недели
    buttons = []
    week_start = current_date - timedelta(days=current_date.weekday())
    
    for i in range(7):
        day = week_start + timedelta(days=i)
        buttons.append(
            InlineKeyboardButton(
                f"{day.strftime('%a %d.%m')}",
                callback_data=f"day_{day.strftime('%Y-%m-%d')}"
            )
        )
    
    # Кнопки навигации
    navigation = [
        InlineKeyboardButton("<< Пред", callback_data=f"week_{week_num-1}_{year}"),
        InlineKeyboardButton("Сегодня", callback_data="current_week"),
        InlineKeyboardButton("След >>", callback_data=f"week_{week_num+1}_{year}")
    ]
    
    # Собираем клавиатуру
    keyboard = [
        navigation,
        buttons[:3],  # Пн, Вт, Ср
        buttons[3:]   # Чт, Пт, Сб, Вс
    ]
    
    return week_info, InlineKeyboardMarkup(keyboard)

async def week_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "current_week":
        week_info, keyboard = await get_week_keyboard()
        await query.edit_message_text(
            f"📅 Текущая неделя:\n\n{week_info}",
            reply_markup=keyboard
        )
        return
    
    _, week_num, year = query.data.split('_')
    week_num, year = int(week_num), int(year)
    
    # Проверка на выход за границы года
    total_weeks = datetime.strptime(f"{year}-12-28", "%Y-%m-%d").isocalendar()[1]
    if week_num < 1:
        week_num = 1
    elif week_num > total_weeks:
        week_num = total_weeks
    
    # Вычисляем дату для выбранной недели
    date = datetime.strptime(f"{year}-W{week_num}-1", "%Y-W%W-%w").date()
    
    week_info = f"Неделя {week_num} из {total_weeks}\n"
    _, keyboard = await get_week_keyboard(date)
    
    await query.edit_message_text(
        f"📅 Выбранная неделя:\n\n{week_info}",
        reply_markup=keyboard
    )

async def day_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    _, date_str = query.data.split('_')
    date = datetime.strptime(date_str, "%Y-%m-%d").date()
    
    # Получаем номер недели для заголовка
    week_num = date.isocalendar()[1]
    year = date.year
    total_weeks = datetime.strptime(f"{year}-12-28", "%Y-%m-%d").isocalendar()[1]
    week_info = f"Неделя {week_num} из {total_weeks}\n"
    
    # Получаем события на этот день
    user = User.get(user_id=query.from_user.id)
    events = Event.select().where(
        (Event.user == user) & 
        (Event.date == date)
    ).order_by(Event.time)
    
    if events:
        text = f"{week_info}События на {date.strftime('%d.%m.%Y')}:\n\n"
        for event in events:
            text += f"⏰ {event.time.strftime('%H:%M')} - {event.name}\n"
    else:
        text = f"{week_info}На {date.strftime('%d.%m.%Y')} событий нет."
    
    # Кнопки для добавления/удаления событий
    buttons = [
        InlineKeyboardButton("Добавить событие", callback_data=f"add_{date_str}"),
        InlineKeyboardButton("Назад к неделе", callback_data="back_to_week")
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([buttons])
    )

async def back_to_week(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    week_info, keyboard = await get_week_keyboard()
    await query.edit_message_text(
        f"📅 Текущая неделя:\n\n{week_info}",
        reply_markup=keyboard
    )

async def add_event(update: Update, context):
    query = update.callback_query
    query.answer()
    
    _, date_str = query.data.split('_')
    context.user_data['event_date'] = date_str
    
    query.edit_message_text("Введите название события:")
    return ADDING_EVENT

async def save_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    event_name = update.message.text
    context.user_data['event_name'] = event_name
    
    await update.message.reply_text("Введите время события в формате ЧЧ:ММ (например, 14:30):")
    return SETTING_TIME

async def set_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        event_time = datetime.strptime(update.message.text, "%H:%M").time()
        context.user_data['event_time'] = event_time
        
        # Предлагаем выбрать время напоминания
        keyboard = [
            [InlineKeyboardButton("За 5 минут", callback_data="reminder_5")],
            [InlineKeyboardButton("За 15 минут", callback_data="reminder_15")],
            [InlineKeyboardButton("За 30 минут", callback_data="reminder_30")],
            [InlineKeyboardButton("За 1 час", callback_data="reminder_60")],
            [InlineKeyboardButton("За 2 часа", callback_data="reminder_120")],
            [InlineKeyboardButton("За 1 день", callback_data="reminder_1440")],
        ]
        
        await update.message.reply_text(
            "Выберите, за сколько времени напомнить о событии:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return SETTING_REMINDER
    except ValueError:
        await update.message.reply_text("Некорректный формат времени. Попробуйте еще раз:")
        return SETTING_TIME

async def set_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    _, minutes = query.data.split('_')
    minutes = int(minutes)
    
    # Сохраняем событие в базу
    user = User.get(user_id=update.effective_user.id)
    event_date = datetime.strptime(context.user_data['event_date'], "%Y-%m-%d").date()
    
    event = Event.create(
        user=user,
        name=context.user_data['event_name'],
        date=event_date,
        time=context.user_data['event_time'],
        reminder_time=minutes
    )
    
    # Запланировать напоминание
    setup_scheduler(context.job_queue, event, update.effective_user.id)
    
    await query.edit_message_text(
        "Событие добавлено!",
        reply_markup=await get_week_keyboard(event_date)[1]
    )
    return ConversationHandler.END

def delete_event(update: Update, context):
    query = update.callback_query
    query.answer()
    
    _, event_id = query.data.split('_')
    event = Event.get(id=event_id)
    event.delete_instance()    
    query.edit_message_text("Событие удалено!")

def main():
    dp = initialize_db()
    
    application = Application.builder().token("YOUR_BOT_TOKEN").build()

    dp.add_handler(CallbackQueryHandler(delete_event, pattern='^delete_'))

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_event, pattern='^add_')],
        states={
            ADDING_EVENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_event)],
            SETTING_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_time)],
            SETTING_REMINDER: [CallbackQueryHandler(set_reminder, pattern='^reminder_')]
        },
        fallbacks=[]
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(week_handler, pattern='^week_'))
    application.add_handler(CallbackQueryHandler(day_handler, pattern='^day_'))
    application.add_handler(CallbackQueryHandler(back_to_week, pattern='^back_to_week$'))
    application.add_handler(conv_handler)
    
    application.run_polling()

if __name__ == '__main__':
    main()