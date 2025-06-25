# from datetime import datetime, timedelta
# from telegram import Bot
# from telegram import InlineKeyboardButton, InlineKeyboardMarkup
# import pytz
# from config import TIMEZONE

# tz = pytz.timezone(TIMEZONE)
# now = datetime.now(tz)

# def setup_scheduler(job_queue, event, user_id):
#     event_time = datetime.combine(event.date, event.time)
#     reminder_time = event_time - timedelta(minutes=event.reminder_minutes)
    
#     # Проверяем, не прошло ли уже время напоминания
#     if reminder_time < datetime.now():
#         return
    
#     # Планируем напоминание
#     job_queue.run_once(
#         send_reminder, 
#         when=reminder_time, 
#         context={
#             'user_id': user_id,
#             'event_id': event.id,
#             'event_name': event.name,
#             'event_time': event.time.strftime('%H:%M')
#         }
#     )

# def send_reminder(context):
#     job = context.job
#     bot = context.bot
    
#     # Кнопка для удаления события
#     keyboard = InlineKeyboardMarkup([
#         [InlineKeyboardButton("Удалить", callback_data=f"delete_{job.context['event_id']}")]
#     ])
    
#     bot.send_message(
#         chat_id=job.context['user_id'],
#         text=f"🔔 Напоминание: {job.context['event_name']} в {job.context['event_time']}",
#         reply_markup=keyboard
#     )


from datetime import datetime, timedelta
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
import logging

def setup_scheduler(job_queue, event, user_id):
    try:
        # Собираем дату и время события
        event_datetime = datetime.combine(event.date, event.time)
        
        # Вычисляем время напоминания
        reminder_time = event_datetime - timedelta(minutes=event.reminder_minutes)
        
        # Проверяем, не прошло ли уже время напоминания
        if reminder_time < datetime.now():
            logging.warning(f"Напоминание для события {event.id} уже просрочено")
            return False
        
        # Уникальное имя задачи для избежания дублирования
        job_name = f"reminder_{event.id}_{user_id}"
        
        # Планируем напоминание
        job_queue.run_once(
            callback=send_reminder,
            when=reminder_time,
            name=job_name,
            data={
                'user_id': user_id,
                'event_id': event.id,
                'event_name': event.name,
                'event_time': event.time.strftime('%H:%M')
            }
        )
        return True
        
    except Exception as e:
        logging.error(f"Ошибка планирования напоминания: {e}")
        return False

async def send_reminder(context):
    try:
        job = context.job
        bot = context.bot
        
        # Кнопка для подтверждения
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{job.data['event_id']}")]
        ])
        
        # Отправляем напоминание
        message = await bot.send_message(
            chat_id=job.data['user_id'],
            text=f"🔔 Напоминание: {job.data['event_name']} в {job.data['event_time']}",
            reply_markup=keyboard
        )
        
        # Сохраняем ID сообщения для возможного редактирования
        context.job.data['message_id'] = message.message_id
        
    except Exception as e:
        logging.error(f"Ошибка отправки напоминания: {e}")