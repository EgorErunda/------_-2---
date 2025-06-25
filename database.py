from peewee import *
from datetime import datetime
import pytz
from config import TIMEZONE
import logging


logger = logging.getLogger(__name__)
db = SqliteDatabase('calendar.db')

class BaseModel(Model):
    class Meta:
        database = db

class User(BaseModel):
    user_id = IntegerField(unique=True)
    created_at = DateTimeField(default=datetime.now(pytz.timezone(TIMEZONE)))

class Event(BaseModel):
    user = ForeignKeyField(User, backref='events')
    name = CharField(max_length=255)
    date = DateField(index=True)
    time = TimeField()
    reminder_minutes = IntegerField(default=15)
    created_at = DateTimeField(default=datetime.now(pytz.timezone(TIMEZONE)))
    is_completed = BooleanField(default=False, index=True)

def initialize_db():
    with db:
        db.create_tables([User, Event])
