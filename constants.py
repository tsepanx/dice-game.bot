import os

from peewee import SqliteDatabase
from telegram import ParseMode


def does_exist(path):
    return os.path.exists(path)


PROJECT_PREFIX = os.path.dirname(__file__) + "/"
DATABASE_PATH = PROJECT_PREFIX + "db"

MY_DATABASE = SqliteDatabase(DATABASE_PATH)


class CommandName:
    GAME_ADD = 'join'
    GAME_RUN = 'play'
    GAME_SET_CUBES = 'setcubes'
    GAME_RESET = 'reset'


class MyDialogState:
    DEFAULT = 0
    WAITING_FOR_PLAYERS = 1
    GAME_IS_ON = 2


START_CUBES_COUNT = 3
TRUMP_CARD_VALUE = 1
MAX_START_CUBES_COUNT = 10


class Phrase:
    PLAYERS_LESS = 'Not enough players, try /join'
    WRONG_NUMBER = 'Type correct number'

    ON_NO_COMMAND_ENTITY = 'No expected entity provided'

    NUMBER_TOO_BIG = lambda x: f'Number is too big. Max is {x}'

    JOIN_BUTTON = "Join the game"
    ALREADY_JOINED = "You've already joined!"

    ROUND_MESSAGE_APPEND_TURN = lambda x, y: f'\n`{x}` - *{y}*'

    BUTTON_CUBES = 'My cubes'
    STOP_ROUND = 'Вскрываемся!'

    WRONG_MOVE_PATTERN = 'Incorrect move'

    GAME_INIT = {'text': 'Initializing new game session...'}
    ON_AGREE = {'text': 'Ok'}

    WAIT_FOR_PLAYERS = {'text': "Waiting for players..."}
    on_user_joined = lambda x: {'text': f'{x} joined game'}

    @staticmethod
    def on_new_round(n, boolean, users, cubes):
        res = f' --- Round: {n} ---\n --- Cubes: {len(cubes)} --- \n'

        for user in users:
            res += f'`{user.username}` - *{len(cubes[user.id])}*\n'

        res += f' --- \nMaputa: {boolean}\n---'
        return {'text': res, 'parse_mode': ParseMode.MARKDOWN}

    @staticmethod
    def on_end_round_1(cnt, default_value, use_base_value):
        res = f'There are {cnt} cubes of "{default_value}"' + \
              (f' and "{TRUMP_CARD_VALUE}"' if use_base_value else '') + \
              ', so...'

        return {'text': res, 'parse_mode': ParseMode.MARKDOWN}

    on_end_round_2 = lambda x: {'text': f'{x} loses his cube... :('}
    on_players_list = lambda x: {'text': 'Alright, starting game.. Players:\n' + "\n".join(x)}

    on_kick_player = lambda x: {'text': f'Player {x} just got kicked out of the game... :('}
    on_change_turn = lambda x: {'text': f"It's {x} turn"}
    on_congratulate_winner = lambda x: {'text': f'Congratulations! {x} is a winner!'}
