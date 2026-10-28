"""Тесты бота без настоящего Telegram: диалоги через Dispatcher.

Апдейты подаются в dp.feed_update, а Bot API подменён FakeSession,
поэтому токен не нужен и сеть не используется.
"""

import asyncio
import importlib
import logging
import os
import subprocess
import sys
import unittest

from tests.helpers import BAD_CSV, BOT_DIR, GOOD_CSV, LOG_TEXT, TempPaths
from tests.fake_telegram import (
    callback_update, document, make_bot, message_update,
)

from aiogram.methods import AnswerCallbackQuery, EditMessageText  # noqa
from aiogram.methods import SendMessage  # noqa: E402

import analytics  # noqa: E402
import config  # noqa: E402
import session  # noqa: E402

bot_module = importlib.import_module("bot")


class ErrorCatcher(logging.Handler):
    """Собирает ERROR-записи логгера бота: их быть не должно."""

    def __init__(self):
        super().__init__(logging.ERROR)
        self.records = []

    def emit(self, record):
        self.records.append(record)


class ImportAndTokenTests(unittest.TestCase):
    def test_dispatcher_built(self):
        dp = bot_module.dp
        self.assertGreater(len(dp.message.handlers), 10)
        self.assertGreater(len(dp.callback_query.handlers), 5)
        self.assertEqual(len(dp.errors.handlers), 1)
        states = {s.state.split(":")[1] for s in bot_module.BotState
                  .__all_states__}
        self.assertEqual(states, {"MENU", "UPLOAD", "WAIT_NAME",
                                  "BROADCAST"})

    def test_start_help_registered_first(self):
        first = bot_module.dp.message.handlers[0].callback.__name__
        second = bot_module.dp.message.handlers[1].callback.__name__
        self.assertEqual((first, second), ("cmd_start", "cmd_help"))

    def test_missing_token_clear_error(self):
        with self.assertRaises(SystemExit) as ctx:
            bot_module.create_bot("")
        self.assertIn("BOT_TOKEN", str(ctx.exception))
        with self.assertRaises(SystemExit) as ctx:
            bot_module.create_bot("not-a-token")
        self.assertIn("неверный формат", str(ctx.exception))
        self.assertIsNotNone(bot_module.create_bot(
            "123456789:AAFakeTokenForTestsOnly_abcdefghijk"))

    def test_run_without_token_exits_with_message(self):
        env = dict(os.environ, BOT_TOKEN="")
        # cwd = корень репозитория, как в README: python py_bot/bot.py
        proc = subprocess.run([sys.executable, str(BOT_DIR / "bot.py")],
                              cwd=BOT_DIR.parent, env=env, timeout=60,
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Не задан BOT_TOKEN", proc.stderr)


class DialogTests(unittest.TestCase):
    def setUp(self):
        self.paths = TempPaths().__enter__()
        self.cooldown = config.CLICK_COOLDOWN
        config.CLICK_COOLDOWN = 0
        self.admins = list(config.ADMIN_IDS)
        config.ADMIN_IDS[:] = [999]
        self.bot, self.tg = make_bot()
        self.catcher = ErrorCatcher()
        logging.getLogger("py_bot").addHandler(self.catcher)
        # свежее хранилище FSM для каждого теста
        bot_module.dp.fsm.storage = type(bot_module.dp.fsm.storage)()

    def tearDown(self):
        logging.getLogger("py_bot").removeHandler(self.catcher)
        config.CLICK_COOLDOWN = self.cooldown
        config.ADMIN_IDS[:] = self.admins
        self.paths.__exit__(None, None, None)
        self.assertEqual(self.catcher.records, [],
                         "хендлер упал в глобальный обработчик ошибок")

    def feed(self, update):
        asyncio.run(bot_module.dp.feed_update(self.bot, update))

    def start(self, uid):
        self.feed(message_update(uid, "/start"))
        return session.load_session(uid)["screen_message_id"]

    def press(self, uid, data, screen=None):
        screen = screen or session.load_session(uid)["screen_message_id"]
        self.feed(callback_update(uid, data, screen))

    def state(self, uid):
        return session.load_session(uid)["state"]

    def test_start_creates_session_and_menu(self):
        screen = self.start(1)
        self.assertIsNotNone(screen)
        self.assertEqual(self.state(1), "MENU")
        self.assertIn("Аналитик Pac-Man Hunt", self.tg.texts()[-1])
        self.assertTrue((config.SESSION_DIR / "1.json").exists())

    def test_buttons_edit_same_screen(self):
        screen = self.start(1)
        self.tg.reset()
        for data in ("top:0", "logstats", "menu", "sub", "upload", "menu"):
            self.press(1, data)
        self.assertEqual(self.tg.of(SendMessage), [])  # ни одного нового
        edits = self.tg.of(EditMessageText)
        self.assertEqual(len(edits), 6)
        self.assertTrue(all(e.message_id == screen for e in edits))
        self.assertEqual(len(self.tg.of(AnswerCallbackQuery)), 6)
        self.assertTrue(session.load_session(1)["subscribed"])

    def test_not_modified_is_silent(self):
        self.start(1)
        self.tg.edit_error = "Bad Request: message is not modified"
        self.tg.reset()
        self.press(1, "top:0")
        self.assertEqual(self.tg.of(SendMessage), [])

    def test_deleted_screen_sends_new(self):
        old = self.start(1)
        self.tg.edit_error = "Bad Request: message to edit not found"
        self.tg.reset()
        self.press(1, "logstats")
        self.assertEqual(len(self.tg.of(SendMessage)), 1)
        self.assertNotEqual(session.load_session(1)["screen_message_id"], old)

    def test_name_then_stats(self):
        config.GAME_RECORDS.write_text(GOOD_CSV, encoding="utf-8")
        self.start(1)
        self.press(1, "stats")
        self.assertEqual(self.state(1), "WAIT_NAME")
        self.feed(message_update(1, "ваня"))
        self.assertEqual(self.state(1), "MENU")
        self.assertEqual(session.load_session(1)["name"], "ваня")
        self.assertIn("Партий: <b>2</b>", self.tg.texts()[-1])
        self.press(1, "ach")
        self.assertIn("Ачивки", self.tg.texts()[-1])

    def test_upload_good_bad_and_notify(self):
        self.start(2)
        self.press(2, "sub")                    # 2 - подписчик
        self.start(1)
        self.press(1, "upload")
        self.assertEqual(self.state(1), "UPLOAD")
        self.tg.files["f1"] = GOOD_CSV.encode("utf-8")
        self.tg.reset()
        self.feed(message_update(1, document=document("f1", "records.csv")))
        report = self.tg.texts()[0]
        self.assertIn("Добавлено новых партий: <b>4</b>", report)
        self.assertEqual(self.state(1), "MENU")
        notes = [m for m in self.tg.of(SendMessage) if m.chat_id == 2]
        self.assertEqual(len(notes), 1)
        self.assertIn("&lt;b&gt;Хакер", notes[0].text)  # экранировано
        # повторная загрузка - только дубли, уведомлений нет
        self.press(1, "upload")
        self.tg.reset()
        self.feed(message_update(1, document=document("f1", "records.csv")))
        self.assertIn("Уже были в базе: 4", self.tg.texts()[0])
        self.assertEqual(self.tg.of(SendMessage), [])
        # битый файл: бот не падает, показывает причины
        self.press(1, "upload")
        self.tg.files["f2"] = BAD_CSV.encode("utf-8")
        self.tg.reset()
        self.feed(message_update(1, document=document("f2", "bad.csv")))
        self.assertIn("Отклонено строк: <b>9</b>", self.tg.texts()[0])
        db, _ = analytics.parse_scores_file(config.SCORES_DB)
        self.assertEqual(len(db), 5)

    def test_upload_checks_before_download(self):
        self.start(1)
        self.press(1, "upload")
        self.tg.reset()
        self.feed(message_update(1, document=document(
            "x", "virus.exe", "application/x-msdownload")))
        self.feed(message_update(1, document=document(
            "y", "big.csv", size=50 * 1024 * 1024)))
        self.tg.files["z"] = b"\xff\xfe\x00bad"
        self.feed(message_update(1, document=document("z", "r.csv")))
        texts = "\n".join(self.tg.texts())
        self.assertIn("нужен файл", texts)
        self.assertIn("больше", texts)
        self.assertIn("UTF-8", texts)
        self.assertEqual(self.state(1), "UPLOAD")   # всё ещё ждём файл
        self.feed(message_update(1, "просто текст"))
        self.assertIn("Жду именно файл", self.tg.texts()[-1])

    def test_upload_log_file(self):
        self.start(1)
        self.press(1, "upload")
        self.tg.files["l"] = LOG_TEXT.encode("utf-8")
        self.tg.reset()
        self.feed(message_update(1, document=document("l", "game.log",
                                                      "text/plain")))
        self.assertIn("Пакман убегал", self.tg.texts()[0])

    def test_document_outside_upload_ignored(self):
        self.start(1)
        self.tg.files["f1"] = GOOD_CSV.encode("utf-8")
        self.tg.reset()
        self.feed(message_update(1, document=document("f1", "records.csv")))
        self.assertIn("Загрузить результаты", self.tg.texts()[0])
        self.assertFalse(config.SCORES_DB.exists())

    def test_admin_rights(self):
        self.start(1)
        self.tg.reset()
        self.feed(message_update(1, "/log"))
        self.feed(message_update(1, "/broadcast"))
        self.press(1, "admin:broadcast")       # подделанная кнопка
        self.assertEqual(self.state(1), "MENU")
        texts = "\n".join(self.tg.texts())
        self.assertEqual(texts.count("только для администратора"), 2)
        alert = self.tg.of(AnswerCallbackQuery)[-1]
        self.assertTrue(alert.show_alert)

    def test_admin_broadcast_and_log(self):
        config.BOT_LOG.write_text("2026-10-28 10:00:00 | INFO | <тест>\n",
                                  encoding="utf-8")
        self.start(5)
        self.press(5, "sub")
        self.start(6)                             # не подписан
        self.start(999)
        self.feed(message_update(999, "/log 5"))
        self.assertIn("&lt;тест&gt;", self.tg.texts()[-1])
        self.feed(message_update(999, "/broadcast"))
        self.assertEqual(self.state(999), "BROADCAST")
        self.tg.reset()
        self.feed(message_update(999, "Турнир <в пятницу>"))
        sent = [m for m in self.tg.of(SendMessage) if m.chat_id == 5]
        self.assertEqual(len(sent), 1)
        self.assertIn("&lt;в пятницу&gt;", sent[0].text)
        self.assertFalse([m for m in self.tg.of(SendMessage)
                          if m.chat_id == 6])
        self.assertEqual(self.state(999), "MENU")

    def test_cancel_and_start_from_any_state(self):
        self.start(1)
        self.press(1, "name")
        self.assertEqual(self.state(1), "WAIT_NAME")
        self.press(1, "menu")
        self.assertEqual(self.state(1), "MENU")
        self.press(1, "upload")
        self.feed(message_update(1, "/start"))
        self.assertEqual(self.state(1), "MENU")
        self.press(1, "upload")
        self.feed(message_update(1, "/help"))
        self.assertIn("Справка", self.tg.texts()[-1])

    def test_sessions_isolated(self):
        self.start(1)
        self.start(2)
        self.press(1, "name")
        self.feed(message_update(1, "Ваня"))
        self.assertEqual(session.load_session(1)["name"], "Ваня")
        self.assertIsNone(session.load_session(2)["name"])
        self.assertEqual(self.state(2), "MENU")

    def test_throttle(self):
        config.CLICK_COOLDOWN = 5
        self.start(1)
        self.tg.reset()
        self.press(1, "top:0")
        self.press(1, "top:0")
        self.assertEqual(len(self.tg.of(EditMessageText)), 1)
        self.assertIn("Не так быстро",
                      self.tg.of(AnswerCallbackQuery)[-1].text)

    def test_foreign_screen_in_group(self):
        self.feed(message_update(1, "/start", chat_type="group"))
        screen = session.load_session(1)["screen_message_id"]
        self.tg.reset()
        self.feed(callback_update(2, "top:0", screen, chat_type="group"))
        self.assertEqual(self.tg.of(EditMessageText), [])
        self.assertIn("другого пользователя",
                      self.tg.of(AnswerCallbackQuery)[-1].text)

    def test_unknown_callback_and_bad_page(self):
        self.start(1)
        self.press(1, "top:abc")
        self.press(1, "что-то")
        self.assertIn("устарела", self.tg.of(AnswerCallbackQuery)[-1].text)

    def test_error_handler(self):
        """Падение хендлера ловит @dp.errors: пользователь получает ответ."""
        original = analytics.load_all_records

        def boom(*a, **k):
            raise RuntimeError("тестовый сбой")
        analytics.load_all_records = boom
        try:
            self.start(1)
            logging.getLogger("py_bot").removeHandler(self.catcher)
            self.feed(message_update(1, "/top"))
        finally:
            analytics.load_all_records = original
            logging.getLogger("py_bot").addHandler(self.catcher)
        self.assertIn("Временный сбой", self.tg.texts()[-1])

    def test_watch_game_records(self):
        self.start(3)
        self.press(3, "sub")
        known = set()
        config.GAME_RECORDS.write_text(GOOD_CSV, encoding="utf-8")
        self.tg.reset()
        fresh = asyncio.run(bot_module.check_game_updates(self.bot, known))
        self.assertEqual(len(fresh), 4)
        self.assertEqual(len(self.tg.of(SendMessage)), 1)
        fresh = asyncio.run(bot_module.check_game_updates(self.bot, known))
        self.assertEqual(fresh, [])


@unittest.skipUnless(importlib.util.find_spec("pygame"), "нет pygame")
class GameConsistencyTests(unittest.TestCase):
    """Порядок таблицы лидеров бота = топ-5 в самой игре."""

    def test_same_order_as_game(self):
        sys.path.insert(0, str(BOT_DIR.parent))
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        from pacman_hunt import storage
        records, _ = analytics.parse_scores_text(GOOD_CSV + BAD_CSV
                                                 .split("\n", 1)[1])
        game_rows = [r.as_row() for r in records]
        game_top = storage.top_records(game_rows, n=len(game_rows))
        ours = analytics.leaderboard(records)
        self.assertEqual([(r["Имя"], r["Время"]) for r in game_top],
                         [(r.name, r.time_sec) for r in ours])


if __name__ == "__main__":
    unittest.main()
