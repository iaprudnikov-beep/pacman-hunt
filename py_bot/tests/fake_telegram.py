"""Поддельный Telegram для тестов: бот «общается» без сети и токена.

FakeSession подменяет HTTP-сессию aiogram: каждый вызов Bot API
записывается в список calls и получает правдоподобный ответ.
"""

import itertools
from datetime import datetime

from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import (
    AnswerCallbackQuery, EditMessageText, GetFile, GetMe, SendMessage,
)
from aiogram.types import (
    CallbackQuery, Chat, Document, File, Message, Update, User,
)

DUMMY_TOKEN = "123456789:AAFakeTokenForTestsOnly_abcdefghijk"
_ids = itertools.count(1000)


class FakeSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.calls = []
        self.edit_error = None     # текст TelegramBadRequest для edit
        self.files = {}            # file_id -> bytes

    async def make_request(self, bot, method, timeout=None):
        self.calls.append(method)
        if isinstance(method, SendMessage):
            return Message(message_id=next(_ids), date=datetime.now(),
                           chat=Chat(id=method.chat_id, type="private"),
                           text=method.text)
        if isinstance(method, EditMessageText):
            if self.edit_error:
                raise TelegramBadRequest(method=method,
                                         message=self.edit_error)
            return True
        if isinstance(method, AnswerCallbackQuery):
            return True
        if isinstance(method, GetFile):
            return File(file_id=method.file_id, file_unique_id="u",
                        file_path=f"documents/{method.file_id}")
        if isinstance(method, GetMe):
            return User(id=1, is_bot=True, first_name="Bot",
                        username="test_bot")
        raise AssertionError(f"неожиданный метод {type(method).__name__}")

    async def stream_content(self, url, headers=None, timeout=30,
                             chunk_size=65536, raise_for_status=True):
        file_id = url.rsplit("/", 1)[-1]
        yield self.files[file_id]

    async def close(self):
        pass

    # удобные выборки
    def of(self, kind):
        return [c for c in self.calls if isinstance(c, kind)]

    def texts(self):
        return [c.text for c in self.calls
                if isinstance(c, (SendMessage, EditMessageText))]

    def reset(self):
        self.calls.clear()


def make_bot():
    sess = FakeSession()
    return Bot(token=DUMMY_TOKEN, session=sess), sess


def user(uid):
    return User(id=uid, is_bot=False, first_name=f"U{uid}",
                username=f"u{uid}")


def message_update(uid, text=None, document=None, chat_type="private"):
    msg = Message(message_id=next(_ids), date=datetime.now(),
                  chat=Chat(id=uid, type=chat_type), from_user=user(uid),
                  text=text, document=document)
    return Update(update_id=next(_ids), message=msg)


def callback_update(uid, data, message_id, chat_type="private"):
    msg = Message(message_id=message_id, date=datetime.now(),
                  chat=Chat(id=uid, type=chat_type), text="экран")
    cq = CallbackQuery(id=str(next(_ids)), from_user=user(uid),
                       chat_instance="ci", data=data, message=msg)
    return Update(update_id=next(_ids), callback_query=cq)


def document(file_id, name, mime="text/csv", size=100):
    return Document(file_id=file_id, file_unique_id=file_id + "u",
                    file_name=name, mime_type=mime, file_size=size)
