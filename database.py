from peewee import *

db = SqliteDatabase('calendar.db')

class BaseModel(Model):
    class Meta:
        database = db

class User(BaseModel):
    user_id = IntegerField(unique=True)
    timezone = CharField(default='UTC')

class Event(BaseModel):
    user = ForeignKeyField(User, backref='events')
    name = TextField()
    date = DateField()
    time = TimeField()
    reminder_time = IntegerField()  # за сколько минут напоминать
    is_completed = BooleanField(default=False)

def initialize_db():
    db.connect()
    db.create_tables([User, Event], safe=True)
    db.close()