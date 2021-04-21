import logging
import random
import time

import telegram
from telegram import ParseMode

from tglib.classes.chat import BotMessageException
from tglib.classes.message import Message

from constants import START_DICE_COUNT, MIN_CARD_VALUE, MAX_CARD_VALUE, CHEAT_CARD_VALUE, Phrase, MyDialogState, users_emoji, winner_emoji
from functions import convert, get_reply_markup, get_reply_keyboard
from db import User, db_inc

DICE_REPLY_MARKUP = get_reply_markup('DICE', Phrase.BUTTON_DICE)


def random_list(a, b, n):
    # Attempt to make python random() more `random`
    res = []

    for i in range(n):
        t = random.randint(a, b)
        if i > 0 and t == res[i - 1]: # if got the same value, then `rerand` it
            t = random.randint(a, b)
        res.append(t)

    return sorted(res)


def player_move_is_available(ints):
    # Checks if move with couple of ints fits to the game rules

    if len(ints) != 2:
        return False

    if not (MIN_CARD_VALUE <= ints[1] <= MAX_CARD_VALUE):
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
    dice_cnt = START_DICE_COUNT

    def __init__(self, chat):
        self.chat = chat

    def start_session(self):
        self.added_players = list(set(self.added_players))  # Check for unique users
        random.shuffle(self.added_players)

        self.current_game = GameSession(self.chat, self.dice_cnt, players=self.added_players)

    def reset_to_defaults(self):
        self.current_game = None
        self.added_players = []

    def on_new_message(self, message: Message):
        if message.chat.id == self.current_game.chat.id:
            self.current_game.on_new_message(message)


class DiceManager:
    def __init__(self, players, dice_cnt):
        self.dice_dict = {}
        self.dice_cnt = dice_cnt
        self.players = players

        self.roll_dice(first=True)

    def roll_dice(self, first=False):
        for player in self.players:
            if first:
                n = self.dice_cnt
            else:
                n = len(self.dice_dict[player.id])

            self.dice_dict[player.id] = random_list(MIN_CARD_VALUE, MAX_CARD_VALUE, n)

    def __getitem__(self, item):
        try:
            return self.dice_dict[item]
        except KeyError:
            logging.warning("No key: %s, returning other players dice" % item)
            return self.str_dice_dict()

    def __len__(self):
        res = 0
        for s in self.dice_dict.values():
            res += len(s)

        return res

    def __str__(self):
        return convert(self.dice_dict)

    def get_dice_map(self):
        # Get list of count for each dice card

        res = [0] * (MAX_CARD_VALUE - MIN_CARD_VALUE + 1)

        for nums in self.dice_dict.values():
            for i in nums:
                res[i - 1] += 1

        return res

    def kick_player(self, player_id):
        try:
            self.dice_dict.pop(player_id)
        except KeyError:
            logging.warning(f"Key Error: {player_id}")

    def pop_dice_from(self, player_id):
        self.dice_dict[player_id].pop()

        if not len(self.dice_dict[player_id]):
            self.kick_player(player_id)
            raise KickPLayerException

    def str_dice_dict(self):
        items = list(self.dice_dict.items())
        s = '*Players dice*\n'

        for i in items:
            user = list(filter(lambda x: x.id == i[0], self.players))[0].username
            s += f'{user}: {i[1]}\n'

        return s


class PlayerMove:
    def __init__(self, count, value):
        self.count = count
        self.value = value

    def is_valid(self, prev, is_maputa, maputa_value=None):
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
    def __init__(self, chat, dice_cnt, players=None):
        self.chat = chat

        self.players = players
        self.dice_manager = DiceManager(players, dice_cnt)

        self.is_maputa = False
        self.maputa_val = None

        self.stored_cheat_moves = set()

        self.current_player = 0
        self.current_round = 0
        self.prev_move = None

        self.messages_to_delete = [] # List of messages, deleted on turn passes to next player
        self.pinned_message = None
        self.pinned_message_text = None

        self.new_round()

    def new_round(self):
        self.current_round += 1
        self.prev_move = None
        self.maputa_val = None
        self.stored_cheat_moves = set()
        self.dice_manager.roll_dice()

        mess_args = Phrase.on_new_round(self.current_round, self.is_maputa, self.players, self.dice_manager)
        text = mess_args['text']

        self.pinned_message = self.send_message(**mess_args, reply_markup=DICE_REPLY_MARKUP)
        self.chat.pin_chat_message(self.pinned_message, disable_notification=True)
        self.pinned_message_text = text

        if self.is_maputa:
            self.current_player -= 1

        self.new_turn()

    def edit_pinned_message_by(self, user_answer: telegram.Message):
        # import pdb;pdb.set_trace()
        # if self.messages_to_delete:
        for d in self.messages_to_delete:
            self.chat.delete_message(d)

        sender = user_answer.from_user.username
        to_delete_text = user_answer.text
        self.chat.delete_message(user_answer)

        append_text = Phrase.ROUND_MESSAGE_APPEND_TURN(to_delete_text, sender)
        self.pinned_message_text += append_text 

        self.edit_message(
            message=self.pinned_message,
            text=self.pinned_message_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=DICE_REPLY_MARKUP
        )

    def new_turn(self):
        self.current_player += 1
        if self.current_player >= len(self.players):
            self.current_player = self.current_player % len(self.players)

        self.messages_to_delete = []

        mess_args = Phrase.on_change_turn(self.players[self.current_player].name)
        mess = self.send_message(**mess_args)

        self.messages_to_delete.append(mess)

    def on_new_message(self, message: Message):
        words = message.text.split()

        if message.user != self.players[self.current_player]:
            return

        if words[0] in Phrase.STOP_ROUND:
            if self.prev_move is not None:
                self.edit_pinned_message_by(message.mess_class)
                self.on_open_up()
                return
            else:
                raise IncorrectMoveException

        try:
            new_move_integers = list(map(int, words))
        except ValueError:
            return

        if not player_move_is_available(new_move_integers):
            raise IncorrectMoveException

        player_move = PlayerMove(*new_move_integers)

        if not player_move.is_valid(self.prev_move, self.is_maputa, self.maputa_val):
            raise IncorrectMoveException

        if not self.is_maputa:
            if player_move.value == CHEAT_CARD_VALUE:
                if player_move.count in self.stored_cheat_moves:
                    raise IncorrectMoveException
                else:
                    self.stored_cheat_moves.add(player_move.count)

        if self.is_maputa and not self.maputa_val:
            self.maputa_val = player_move.value

        self.edit_pinned_message_by(message.mess_class)

        self.prev_move = player_move
        self.new_turn()

    def on_open_up(self): # Func runs on "Вскрываемся!"
        dice_map = self.dice_manager.get_dice_map()
        res_count = dice_map[self.prev_move.value - 1]

        use_cheat = not self.is_maputa and not self.prev_move.value == CHEAT_CARD_VALUE
        res_count += dice_map[CHEAT_CARD_VALUE - 1] if use_cheat else 0

        player_to_lose_ind = self.current_player - (0 if res_count >= self.prev_move.count else 1)
        player = self.players[player_to_lose_ind]

        mess_args1 = Phrase.on_end_round_1(res_count, self.prev_move.value, use_cheat)

        s = self.dice_manager.str_dice_dict()
        self.send_message(text=s, parse_mode=ParseMode.MARKDOWN)

        self.send_message(**mess_args1, reply_markup=telegram.ReplyKeyboardRemove(), )
        self.send_message(**Phrase.on_lose(player.name))

        self.current_player = player_to_lose_ind

        try:
            self.dice_manager.pop_dice_from(player.id)
        except KickPLayerException:
            try:
                self.kick_player(player)
                self.is_maputa = False
                self.new_round()
                return

            except GameEndException:
                return

        self.is_maputa = len(self.dice_manager[player.id]) == 1 and len(self.players) > 2
        self.new_round()

    def kick_player(self, player):
        self.players.remove(player)
        self.current_player += 1

        try:
            self.dice_manager.dice_dict.pop(player)
        except Exception:
            pass

        mess_args = Phrase.on_kick_player(player.name)
        self.send_message(**mess_args)

        if len(self.players) <= 1:
            self.end_game()

    def end_game(self):
        winner = self.players[0].name if len(self.players > 0) else 'NULL'

        mess_args = Phrase.on_congratulate_winner(winner)
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

