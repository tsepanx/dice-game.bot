import json

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup


def convert_string_to_dict(s: str) -> dict:
    return json.loads(s)


def convert(data: dict) -> str:
    return json.dumps(data, indent=2, separators=(',', ': '), default=str, ensure_ascii=False) \
        .encode("utf-8").decode("utf-8")


def get_reply_markup(data, button_text):
    button = InlineKeyboardButton(button_text, callback_data=data)
    return InlineKeyboardMarkup.from_button(button)


def get_reply_keyboard(buttons_list):
    keyboard = ReplyKeyboardMarkup.from_row(buttons_list)
    keyboard.one_time_keyboard = True
    keyboard.selective = True
    keyboard.resize_keyboard = True
    return keyboard
