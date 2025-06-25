from datetime import datetime, timedelta
from telegram import Bot
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import pytz
from config import TIMEZONE

tz = pytz.timezone(TIMEZONE)
now = datetime.now(tz)

def setup_scheduler(job_queue, event, user_id):
    event_time = datetime.combine(event.date, event.time)
    reminder_time = event_time - timedelta(minutes=event.reminder_minutes)
    
    # Проверяем, не прошло ли уже время напоминания
    if reminder_time < datetime.now():
        return
    
    # Планируем напоминание
    job_queue.run_once(
        send_reminder, 
        when=reminder_time, 
        context={
            'user_id': user_id,
            'event_id': event.id,
            'event_name': event.name,
            'event_time': event.time.strftime('%H:%M')
        }
    )

def send_reminder(context):
    job = context.job
    bot = context.bot
    
    # Кнопка для удаления события
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Удалить", callback_data=f"delete_{job.context['event_id']}")]
    ])
    
    bot.send_message(
        chat_id=job.context['user_id'],
        text=f"🔔 Напоминание: {job.context['event_name']} в {job.context['event_time']}",
        reply_markup=keyboard
    )
