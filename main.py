import logging

import telegram as tg

import tglib.classes.command as my
import tglib.classes.message as my
from constants import Phrase, MyDialogState
from game import GameException, GameManager
from tglib.bot import Bot
from tglib.classes.chat import ChatHandler, BotMessageException
from tglib.types import MESSAGE_TYPES
from tglib.utils import is_state, get_button_markup

debug = True


def game_exception_handling(e: Exception, update, _, chat):
    if isinstance(e, GameException):
        logging.warning('game ' + str(e))
        error_mess = chat.send_message(**e.mess_kwargs,
                                       reply_to_message_id=update.message.message_id)
        chat.gm.current_game.messages_to_delete.extend([error_mess, update.message])
        return error_mess
    return False


class MyChatHandler(ChatHandler):
    ONLY_ADMINS_COMMANDS = ['reset']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.join_message = None
        self.join_button = (Phrase.JOIN_BUTTON, 'JOIN')
        self.start_button = (Phrase.START_BUTTON, 'START')

        self.gm = GameManager(self)

    class CommandsEnum(ChatHandler.CommandsEnum):
        # <command_name> - (description, func to run)
        play = ('Start a new game', None)
        setdice = ('Set start dice count', None)
        # settimeout = ('Set timeout', None)
        reset = ('Reset', None)

    @is_state(MyDialogState.DEFAULT)
    def on_play(self, update: tg.Update):
        self.state = MyDialogState.WAITING_FOR_PLAYERS

        reply_markup = get_button_markup(self.join_button)

        self.join_message = self.send_message(**Phrase.WAIT_FOR_PLAYERS, reply_markup=reply_markup)

    def on_setdice(self, update: tg.Update):
        command = my.Command(self, update)

        try:
            cnt = int(command.entity_text)
            self.gm.dice_cnt = cnt
            self.send_message(**Phrase.ON_AGREE)
        except ValueError:
            raise BotMessageException(Phrase.ON_NO_COMMAND_ENTITY)

    def on_reset(self, _: tg.Update):
        self.state = MyDialogState.DEFAULT
        self.gm.reset_to_defaults()
        self.send_message(**Phrase.ON_AGREE, reply_markup=tg.ReplyKeyboardRemove())

    def on_keyboard_callback_query(self, update: tg.Update):
        query = update.callback_query
        data = query.data.split()
        user = query.from_user

        if data[0] == 'START':
            if self.state == MyDialogState.WAITING_FOR_PLAYERS:
                self.gm.start_session()
                self.state = MyDialogState.GAME_IS_ON

        elif data[0] == 'JOIN':
            if self.state != MyDialogState.WAITING_FOR_PLAYERS:
                return

            if user not in self.gm.added_players:
                self.gm.added_players.append(user)

                new_text = self.join_message.text + '\n' + Phrase.on_user_joined(user.name)['text']

                self.join_message = self.edit_message(
                    message=self.join_message,
                    text=new_text,
                )

            else:
                self.send_alert(query.id, text=Phrase.ALREADY_JOINED)

            if debug or len(self.gm.added_players) > 1:  # Enough players to start
                reply_markup = get_button_markup(self.join_button, self.start_button)

                self.edit_message(
                    message=self.join_message,
                    reply_markup=reply_markup
                )

        elif data[0] == 'DICE':
            if self.state != MyDialogState.GAME_IS_ON:
                return

            dice_set = self.gm.current_game.dice_manager[user.id]
            self.send_alert(query.id, text=str(dice_set))

        else:
            raise BotMessageException('unexpected callback_data string: ' + query.data)

    def reply(self, update: tg.Update, message_type: MESSAGE_TYPES):
        super().reply(update, message_type)

        print(update.message.text)

        if self.state == MyDialogState.GAME_IS_ON:
            self.gm.on_new_message(my.Message(self, update))


if __name__ == '__main__':
    Bot(MyChatHandler, game_exception_handling).main()
