import pyrogram
from functools import wraps
import localisation
from pyrogram import  Client
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import (
    CallbackQuery, Message
)


class State:
    def __init__(self, lang):
        self.loc = localisation.Localisation(lang)


USERS = {}
MARKDOWN = ParseMode.MARKDOWN
app = Client(
    "poster",
    api_id=1, api_hash="",
    bot_token=""
)

