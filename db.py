import os
from peewee import *

db = SqliteDatabase('users.db')

class User(Model):
    username = CharField()
    games = IntegerField(default=0)
    winnings = IntegerField(default=0)

    class Meta:
        database = db

tables = [User]

# User.create(username='new')

def db_inc(username, attr):
    sel = User.get(User.username == username)
    setattr(sel, attr, getattr(sel, attr) + 1)
    sel.save()

# inc('new', 'winnings')
# inc('new', 'games')

def does_exist(path):
    return os.path.exists(path)

def create_database(db, tables):
    try:
        db.create_tables(tables)
    except Exception as e:
        print(e)

if __name__ == "__main__":
    for i in User.select():
        print(i.winnings, i.games)

    print(User.get(User.username == 'new'))

    create_database(db, tables)
