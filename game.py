import logging
import random as r
import time

import telegram
from telegram import ParseMode

from tglib.classes.chat import BotMessageException
from tglib.classes.message import Message

from constants import START_CUBES_COUNT, CHEAT_CARD_VALUE, Phrase, MyDialogState, users_emoji, winner_emoji
from functions import convert, get_reply_markup, get_reply_keyboard
from db import User, db_inc

CUBES_REPLY_MARKUP = get_reply_markup('CUBES', Phrase.BUTTON_CUBES)
STOP_ROUND_MARKUP = get_reply_keyboard([Phrase.STOP_ROUND])

# SLEEP_RATIO = 0.9

# sleep = lambda x: time.sleep(x * SLEEP_RATIO)


def true_rand(a, b, n):
    res = []

    for i in range(n):
        t = r.randint(a, b)
        if i > 0 and t == res[i - 1]:
            t = r.randint(a, b)
        res.append(t)

    return sorted(res)


def move_matches(nums):
    if len(nums) > 2:
        return False

    if len(nums) == 1:
        return False

    if not (1 <= nums[1] <= 6):
        return False

    return True


class KickPLayerException(Exception):
    pass


class GameEndException(Exception):
    pass


class GameException(BotMessageException):
    def __init__(self, text, parse_mode=None):
        super().__init__(text, parse_mode=parse_mode)


class IncorrectMoveException(GameException):
    def __init__(self, parse_mode=None):
        super().__init__(Phrase.WRONG_MOVE_PATTERN, parse_mode=parse_mode)


class GameManager:
    current_game = None
    added_players = [] # TODO shared between different chats
    start_cubes_count = START_CUBES_COUNT

    def __init__(self, chat):
        self.chat = chat

    def start_session(self):
        self.added_players = list(set(self.added_players))  # Check for unique users

        self.current_game = GameSession(self.chat, self.start_cubes_count, players=self.added_players)

    def reset_to_defaults(self):
        self.current_game = None
        self.added_players = []

    def on_new_message(self, message: Message):
        if message.chat.id == self.current_game.chat.id:
            self.current_game.on_new_message(message)


class CubesSet:
    def __init__(self, players, start_cubes_cnt):
        self.__cubes = {}
        self.start_cubes_cnt = start_cubes_cnt
        self.prev_maputa = False
        self.players = players

        self.shuffle(start=True)

    def shuffle(self, start=False):
        for player in self.players:
            self.__cubes[player.id] = true_rand(1, 6, self.start_cubes_cnt if start else  len(self.__cubes[player.id]) )

    def __getitem__(self, item):
        try:
            return self.__cubes[item]
        except KeyError:
            logging.warning("No key: %s" % item)
            return None

    def __len__(self):
        res = 0
        for s in self.__cubes.values():
            res += len(s)

        return res

    def __str__(self):
        return convert(self.__cubes)

    def get_cubes_values(self):
        res = {}
        for i in range(1, 7):
            res[i] = 0

        for cube_set in self.__cubes.values():
            for val in cube_set:
                res[val] += 1

        return res

    def kick_player(self, player_id):
        try:
            self.__cubes.pop(player_id)
        except KeyError:
            logging.warning(f"Key Error: {player_id}")

    def remove_cube_from_player(self, player_id):
        self.__cubes[player_id].pop()
        self.shuffle()

        if len(self.__cubes[player_id]) == 0:
            self.kick_player(player_id)
            raise KickPLayerException


class PlayerMove:
    def __init__(self, count, value):
        self.count = count
        self.value = value

    def is_move_correct(self, prev, is_maputa, maputa_value=None):
        if prev is None:
            if is_maputa:
                return True
            else:
                return self.value != CHEAT_CARD_VALUE

        if not is_maputa:
            if self.value == CHEAT_CARD_VALUE:
                if prev.value == CHEAT_CARD_VALUE:
                    return self.count > prev.count
                return self.count * 2 >= prev.count
            else:
                if prev.value == CHEAT_CARD_VALUE:
                    return prev.count * 2 <= self.count
                if self.count == prev.count:
                    return self.value > prev.value
                return self.count > prev.count
        else:
            if maputa_value is None:
                return True
            if self.value == prev.value == maputa_value:
                return self.count > prev.count
            return False


class GameSession:
    def __init__(self, chat, start_cubes_count, players=None):
        self.chat = chat

        self.players = players
        self.cubes = CubesSet(players, start_cubes_count)

        self.is_maputa = False
        self.maputa_val = None

        self.stored_cheat_moves = set()

        self.current_player = 0
        self.current_round = 0
        self.prev_move = None

        self.mess_to_delete_on_new_turn = []
        self.last_round_message = None
        self.last_round_message_text = None

        self.new_round()

    def new_round(self):
        self.current_round += 1
        self.prev_move = None
        self.maputa_val = None
        self.stored_cheat_moves = set()

        mess_args = Phrase.on_new_round(self.current_round, self.is_maputa, self.players, self.cubes)
        text = mess_args['text']

        self.last_round_message = self.send_message(**mess_args, reply_markup=CUBES_REPLY_MARKUP)
        self.chat.pin_chat_message(self.last_round_message, disable_notification=True)
        self.last_round_message_text = text

        if self.is_maputa:
            self.current_player -= 1

        self.new_turn()

    def move_bot_greeting_under_round_message(self, user_answer: telegram.Message):
        if self.mess_to_delete_on_new_turn:
            edit_mess = self.last_round_message

            text_to_delete = user_answer.text
            sender = user_answer.from_user.username
            for delete_mess in self.mess_to_delete_on_new_turn:
                self.chat.delete_message(delete_mess)
            self.chat.delete_message(user_answer)

            new_text = Phrase.ROUND_MESSAGE_APPEND_TURN(text_to_delete, sender)
            self.last_round_message_text += new_text

            self.edit_message(text=self.last_round_message_text,
                                   message=edit_mess,
                                   parse_mode=ParseMode.MARKDOWN,
                                   reply_markup=CUBES_REPLY_MARKUP)

    def new_turn(self):
        self.current_player += 1
        if self.current_player >= len(self.players):
            self.current_player = self.current_player % len(self.players)

        self.mess_to_delete_on_new_turn = []

        mess_args = Phrase.on_change_turn(self.players[self.current_player].name)
        mess = self.send_message(**mess_args, reply_markup=STOP_ROUND_MARKUP)

        self.mess_to_delete_on_new_turn.append(mess)

    def on_new_message(self, message: Message):
        words = message.text.split()

        if message.user != self.players[self.current_player]:
            return

        if words[0] == Phrase.STOP_ROUND:
            if self.prev_move is not None:
                self.move_bot_greeting_under_round_message(message.mess_class)
                self.on_open_up()
                return
            else:
                raise IncorrectMoveException

        try:
            nums = list(map(int, words))
        except ValueError:
            return

        if not move_matches(nums):
            raise IncorrectMoveException

        move = PlayerMove(*nums)

        if not self.is_maputa:
            if move.value == CHEAT_CARD_VALUE:
                if move.count in self.stored_cheat_moves:
                    raise IncorrectMoveException
                else:
                    self.stored_cheat_moves.add(move.count)

        if not move.is_move_correct(self.prev_move, self.is_maputa, self.maputa_val):
            raise IncorrectMoveException

        if self.is_maputa and not self.maputa_val:
            self.maputa_val = move.value

        self.move_bot_greeting_under_round_message(message.mess_class)

        self.prev_move = move
        self.new_turn()

    def on_open_up(self): # Func runs on "Вскрываемся!"
        cubes_data = self.cubes.get_cubes_values()
        res_count = cubes_data[self.prev_move.value]

        use_cheat = not self.is_maputa and not self.prev_move.value == CHEAT_CARD_VALUE

        if use_cheat:
            res_count += cubes_data[CHEAT_CARD_VALUE]

        player_to_lose_ind = self.current_player - (0 if res_count >= self.prev_move.count else 1)
        player = self.players[player_to_lose_ind]

        mess_args1 = Phrase.on_end_round_1(res_count, self.prev_move.value, use_cheat)

        self.send_message(**mess_args1, reply_markup=telegram.ReplyKeyboardRemove(), )
        self.send_message(**Phrase.on_lose(player.name))

        self.current_player = player_to_lose_ind

        try:
            self.cubes.remove_cube_from_player(player.id)
        except KickPLayerException:
            try:
                self.kick_player(player)
                self.is_maputa = False
                self.new_round()
                return

            except GameEndException:
                return

        self.is_maputa = len(self.cubes[player.id]) == 1 and len(self.players) > 2
        self.new_round()

    def kick_player(self, player):
        self.players.remove(player)
        self.current_player += 1

        mess_args = Phrase.on_kick_player(player.name)
        self.send_message(**mess_args)

        if len(self.players) <= 1:
            self.end_game()

    def end_game(self):
        winner = self.players[0]
        # users_emoji[winner.username] = winner_emoji

        # inc('new', 'winnings')
        # inc('new', 'games')

        # for player in self.chat.gm.added_players:
        #     is_winner = int(player == winner)
        #     try:
        #         if is_winner:
        #             db_inc(player.username, 'winnings')
        #         db_inc(player.username, 'games')
        #     except Exception as e:
        #         user = User.create(username=player.username, games)


        mess_args = Phrase.on_congratulate_winner(winner.name)
        self.send_message(**mess_args)
        self.chat.state = MyDialogState.DEFAULT
        self.chat.gm.reset_to_defaults()

        raise GameEndException

    @staticmethod
    def decorate_nickname(s):
        def find_nick(s, n, emoji):
            if n in s:
                new = f'{emoji} {n} {emoji}'
                s = s.replace(n, new)
                return s
            return False

        for n in users_emoji:
            t = find_nick(s, '@' + n, users_emoji[n])
            if t:
                s = t
            else:
                t = find_nick(s, n, users_emoji[n])
                s = t if t else s

        return s

    def send_message(self, **kwargs):
        text = kwargs.pop('text')
        text = self.decorate_nickname(text)

        return self.chat.send_message(text=text, **kwargs)

    def edit_message(self, **kwargs):
        text = kwargs.pop('text')
        text = self.decorate_nickname(text)

        return self.chat.edit_message(text=text, **kwargs)

