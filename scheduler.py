from datetime import datetime, timedelta
import pytz
from config import TIMEZONE
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

async def send_reminder(context):
    try:
        job = context.job
        event = job.context['event']
        tz = pytz.timezone(TIMEZONE)
        
        # Проверяем, что событие еще не прошло
        event_datetime = tz.localize(datetime.combine(event.date, event.time))
        if event_datetime < datetime.now(tz):
            logger.info(f"Событие {event.id} уже прошло, напоминание не отправлено")
            return

        await context.bot.send_message(
            chat_id=event.user.user_id,
            text=f"🔔 Напоминание: {event.name} в {event.time.strftime('%H:%M')}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Подтвердить", callback_data=f"complete_{event.id}")
            ]])
        )
    except Exception as e:
        logger.error(f"Ошибка отправки напоминания: {e}")

def setup_scheduler(job_queue, event):
    try:
        tz = pytz.timezone(TIMEZONE)
        now = datetime.now(tz)
        event_datetime = tz.localize(datetime.combine(event.date, event.time))
        
        # Проверяем, что событие в будущем
        if event_datetime < now:
            logger.warning(f"Событие {event.id} уже прошло")
            return False
            
        reminder_time = event_datetime - timedelta(minutes=event.reminder_minutes)
        
        # Если время напоминания уже прошло, отправляем немедленно
        if reminder_time < now:
            reminder_time = now + timedelta(seconds=10)
            
        job_queue.run_once(
            send_reminder,
            when=reminder_time,
            name=f"reminder_{event.id}_{int(reminder_time.timestamp())}",
            context={'event': event}
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка планирования напоминания: {e}")
        return False