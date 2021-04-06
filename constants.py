import os
from telegram import ParseMode

class MyDialogState:
    DEFAULT = 0
    WAITING_FOR_PLAYERS = 1
    GAME_IS_ON = 2


START_CUBES_COUNT = 3
CHEAT_CARD_VALUE = 1
MAX_START_CUBES_COUNT = 10

winner_emoji = '🏆'
bool_emoji = lambda x: '✅' if x else '❌'

users_emoji = {
    'tsepan': '🔆',
    'aqlez': '♨️',
    'Troyanez373': '🔱',
    'alexanderchmykhov': '🔓',
    'degra_dator': '☣',
    'EvgenyCuSO4': '💤',
    'universitet1971': '❇️',
}


class Phrase:
    PLAYERS_NOT_ENOUGH = {'text': 'Not enough players, try /join'}
    WRONG_NUMBER = 'Type correct number'

    ON_NO_COMMAND_ENTITY = 'e.g /setcubes 5'

    NUMBER_TOO_BIG = lambda x: f'Number is too big. Max is {x}'

    JOIN_BUTTON = "Join the game"
    START_BUTTON = 'Start game'
    ALREADY_JOINED = "You've already joined!"

    ROUND_MESSAGE_APPEND_TURN = lambda x, y: f'\n*{x}* - `{y}`'

    BUTTON_CUBES = 'My cubes'
    STOP_ROUND = 'Вскрываемся!'

    WRONG_MOVE_PATTERN = 'Incorrect move'

    ON_AGREE = {'text': 'Ok'}

    WAIT_FOR_PLAYERS = {'text': "🤔 Waiting for players... 🤔\n\nJoined players:"}
    on_user_joined = lambda x: {'text': f'{x}'}

    @staticmethod
    def on_new_round(n, boolean, users, cubes):
        res = f'*{n}* Round \n*{len(cubes)}* Cubes \nMaputa: *{bool_emoji(boolean)}*\n\n🎲 *Players Cubes* 🎲\n\n'

        for user in users:
            res += f'`{user.username}` - *{len(cubes[user.id])}*\n'

        res += f'\n\n*Moves History*'
        return {'text': res, 'parse_mode': ParseMode.MARKDOWN}

    @staticmethod
    def on_end_round_1(cnt, default_value, use_base_value):
        res = f'There are {cnt} cubes of *' + \
            (f' *{CHEAT_CARD_VALUE}*, ' if use_base_value else '') + f'{default_value}*'

        return {'text': res, 'parse_mode': ParseMode.MARKDOWN}

    on_lose = lambda x: {'text': f'{x} - ❌'}

    on_kick_player = lambda x: {'text': f'Player {x} just got kicked out of the game... 🤬'}
    on_change_turn = lambda x: {'text': f"It's {x} turn"}
    on_congratulate_winner = lambda x: {'text': f'Congratulations! {x} is a winner! 😃 👍'}
