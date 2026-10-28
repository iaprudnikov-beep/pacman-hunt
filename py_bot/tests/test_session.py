"""Тесты JSON-сессий: создание, сохранение, изоляция, битый файл."""

import json
import unittest

from tests.helpers import TempPaths

import config  # noqa: E402
import session  # noqa: E402


class SessionTests(unittest.TestCase):
    def test_new_session_when_no_file(self):
        with TempPaths():
            s = session.load_session(42)
            self.assertEqual(s["state"], "MENU")
            self.assertFalse(s["subscribed"])
            self.assertIsNone(s["name"])
            self.assertFalse((config.SESSION_DIR / "42.json").exists())

    def test_save_load_and_isolation(self):
        with TempPaths():
            session.update_session(1, name="Ваня", subscribed=True)
            session.update_session(2, name="Петя")
            self.assertEqual(session.load_session(1)["name"], "Ваня")
            self.assertEqual(session.load_session(2)["name"], "Петя")
            self.assertEqual(session.subscribers(), [1])
            self.assertEqual(session.subscribers(exclude=1), [])
            raw = (config.SESSION_DIR / "1.json").read_text(encoding="utf-8")
            self.assertIn("Ваня", raw)  # ensure_ascii=False
            self.assertEqual(json.loads(raw)["user_id"], 1)

    def test_corrupted_file(self):
        with TempPaths():
            config.SESSION_DIR.mkdir(parents=True)
            (config.SESSION_DIR / "7.json").write_text("{битый",
                                                       encoding="utf-8")
            (config.SESSION_DIR / "8.json").write_text("[1, 2]",
                                                       encoding="utf-8")
            self.assertEqual(session.load_session(7)["state"], "MENU")
            self.assertEqual(session.load_session(8)["state"], "MENU")

    def test_missing_keys_filled_and_clear(self):
        with TempPaths():
            config.SESSION_DIR.mkdir(parents=True)
            (config.SESSION_DIR / "9.json").write_text('{"name": "Old"}',
                                                       encoding="utf-8")
            s = session.load_session(9)
            self.assertEqual(s["name"], "Old")
            self.assertIn("screen_message_id", s)
            session.clear_session(9)
            self.assertIsNone(session.load_session(9)["name"])


if __name__ == "__main__":
    unittest.main()
