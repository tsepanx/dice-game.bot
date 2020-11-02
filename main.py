import enum
import logging

import telegram as tg

from tglib.classes.chat import ChatHandler, BotMessageException
from tglib.bot import Bot
from tglib.types import MESSAGE_TYPES
from tglib.utils import is_state, get_column_markup

import tglib.classes.message as my
import tglib.classes.command as my

from constants import Phrase, MyDialogState, MAX_START_CUBES_COUNT
from functions import get_reply_markup
from game import STOP_ROUND_MARKUP, GameException, GameManager

debug = True

def game_exception_handling(e: Exception, update, _, chat):
    if isinstance(e, GameException):
        logging.warning('game ' + str(e))
        error_mess = chat.send_message(**e.mess_kwargs,
                                       reply_markup=STOP_ROUND_MARKUP,
                                       reply_to_message_id=update.message.message_id)
        get_game_manager(chat).current_game.mess_to_delete_on_new_turn.extend([error_mess, update.message])
        return error_mess
    return False


class MyChatHandler(ChatHandler):
    ONLY_ADMINS_COMMANDS = ['reset']
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.join_message = None
        self.join_button = (Phrase.JOIN_BUTTON, 'PLAYER')
        self.start_button = (Phrase.START_BUTTON, 'START')

        self.gm = GameManager(self)

    class CommandsEnum(ChatHandler.CommandsEnum):
        # <command_name> - (description, func to run)
        play = ('*Play*!', None)
        setcubes = ('Set cubes', None)
        reset = ('Reset', None)

    @is_state(MyDialogState.DEFAULT)
    def on_play(self, update: tg.Update):
        self.state = MyDialogState.WAITING_FOR_PLAYERS

        reply_markup = get_column_markup(self.join_button)

        self.join_message = self.send_message(**Phrase.WAIT_FOR_PLAYERS, reply_markup=reply_markup)


    def on_setcubes(chat: ChatHandler, update: tg.Update):
        command = my.Command(chat, update)

        try:
            cnt = int(command.entity_text)
            if cnt > MAX_START_CUBES_COUNT:
                raise BotMessageException(Phrase.NUMBER_TOO_BIG(MAX_START_CUBES_COUNT))
            self.gm.start_cubes_count = cnt
            self.send_message(**Phrase.ON_AGREE)
        except ValueError:
            raise BotMessageException(Phrase.ON_NO_COMMAND_ENTITY)

    def on_reset(chat: ChatHandler, _: tg.Update):
        self.state = MyDialogState.DEFAULT
        self.gm.reset_to_defaults()
        self.send_message(**Phrase.ON_AGREE, reply_markup=tg.ReplyKeyboardRemove())


    def on_keyboard_callback_query(self, update: tg.Update):
        query = update.callback_query
        data = query.data.split()
        user = query.from_user

        if data[0] == 'START':
            self.gm.start_session()
            self.state = MyDialogState.GAME_IS_ON

        elif data[0] == 'PLAYER':
            if self.state != MyDialogState.WAITING_FOR_PLAYERS:
                return

            if user not in self.gm.added_players:
                logging.info('JOIN ' + user.name)

                self.gm.added_players.append(user)

                mess_args = Phrase.on_user_joined(user.name)
                self.send_message(**mess_args)
            else:
                self.send_alert(query.id, text=Phrase.ALREADY_JOINED)

            if debug or len(self.gm.added_players) > 1:
                reply_markup = get_column_markup(self.join_button, self.start_button)

                self.edit_message(
                    message=self.join_message,
                    reply_markup=reply_markup
                )

        elif data[0] == 'CUBES':
            if self.state != MyDialogState.GAME_IS_ON:
                return

            cubes_set = self.gm.current_game.cubes[user.id]
            self.send_alert(query.id, text=str(cubes_set))

        else:
            raise BotMessageException('unexpected callback_data string: ' + query.data)

    def reply(self, update: tg.Update, message_type: MESSAGE_TYPES):
        super().reply(update, message_type)

        if self.state == MyDialogState.GAME_IS_ON:
            self.gm.on_new_message(my.Message(self, update))


if __name__ == '__main__':
    Bot(MyChatHandler, game_exception_handling).main()
