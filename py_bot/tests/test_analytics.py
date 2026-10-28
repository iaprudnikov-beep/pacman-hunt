"""Тесты аналитики: разбор, проверка, рейтинг, статистика, ачивки, лог."""

import unittest

from tests.helpers import BAD_CSV, GOOD_CSV, LOG_TEXT, TempPaths

import analytics  # noqa: E402
import config  # noqa: E402
from analytics import Record  # noqa: E402


def rec(name="Ваня", result="Победа", time_sec=20.0, eaten=10, total=159,
        date="2026-10-20 10:00:00"):
    return Record(date, name, result, time_sec, eaten, total)


class ParseTests(unittest.TestCase):
    def test_good_csv_with_bom(self):
        records, errors = analytics.parse_scores_text(GOOD_CSV)
        self.assertEqual(errors, [])
        self.assertEqual(len(records), 4)
        self.assertEqual(records[0].name, "Ваня")
        self.assertEqual(records[0].time_sec, 12.5)

    def test_bad_rows_are_rejected_not_crash(self):
        records, errors = analytics.parse_scores_text(BAD_CSV)
        self.assertEqual(len(records), 1)          # только последняя строка
        self.assertEqual(len(errors), 9)
        joined = "\n".join(errors)
        for part in ("числами", "недопустимый результат", "съедено больше",
                     "не всю еду", "больше 0", "не успел бы",
                     "дата не в формате", "пустое имя", "полей"):
            self.assertIn(part, joined)
        self.assertTrue(errors[0].startswith("Строка 2:"))

    def test_wrong_header_and_empty(self):
        _, errors = analytics.parse_scores_text("a,b,c\n1,2,3\n")
        self.assertIn("Нет столбцов", errors[0])
        self.assertEqual(analytics.parse_scores_text("")[1], ["Файл пустой"])

    def test_garbage_binary_like_text(self):
        records, errors = analytics.parse_scores_text("\x00\x01\x02")
        self.assertEqual(records, [])
        self.assertTrue(errors)

    def test_verify_rules(self):
        self.assertEqual(analytics.verify_record(rec()), [])
        self.assertTrue(analytics.verify_record(rec(time_sec=5000)))
        self.assertTrue(analytics.verify_record(rec(name="x" * 17)))
        self.assertTrue(analytics.verify_record(rec(eaten=159)))  # победа
        self.assertTrue(analytics.verify_record(rec(total=0, eaten=0)))
        self.assertTrue(analytics.verify_record(
            rec(date="2099-01-01 00:00:00")))
        self.assertEqual(analytics.verify_record(
            rec(result="Поражение", eaten=159, time_sec=90)), [])


class DatabaseTests(unittest.TestCase):
    def test_append_dedup(self):
        with TempPaths():
            records, _ = analytics.parse_scores_text(GOOD_CSV)
            added, dup = analytics.append_records(records)
            self.assertEqual((len(added), dup), (4, 0))
            added, dup = analytics.append_records(records)
            self.assertEqual((len(added), dup), (0, 4))
            # записи, уже известные из records.csv игры, не дублируются
            added, dup = analytics.append_records([rec(date="2026-10-25 "
                                                       "10:00:00")],
                                                  known=[rec(date="2026-10-25"
                                                             " 10:00:00")])
            self.assertEqual((len(added), dup), (0, 1))
            db, errors = analytics.parse_scores_file(config.SCORES_DB)
            self.assertEqual((len(db), errors), (4, []))

    def test_load_all_merges_game_and_db(self):
        with TempPaths():
            config.GAME_RECORDS.write_text(GOOD_CSV, encoding="utf-8")
            records, _ = analytics.parse_scores_text(GOOD_CSV)
            analytics.append_records(records[:2] + [rec(date="2026-10-26 "
                                                         "09:00:00")])
            merged, bad = analytics.load_all_records()
            self.assertEqual((len(merged), bad), (5, 0))


class RankingTests(unittest.TestCase):
    def setUp(self):
        self.records = [
            rec("A", "Поражение", 100.0, 159),
            rec("B", "Победа", 40.0, 5),
            rec("C", "Победа", 20.0, 5),
            rec("D", "Победа", 10.0, 30),
            rec("E", "Поражение", 150.0, 159),
        ]

    def test_order_matches_game_top5(self):
        names = [r.name for r in analytics.leaderboard(self.records)]
        # победы: меньше еды -> быстрее; поражения: дольше продержался
        self.assertEqual(names, ["C", "B", "D", "E", "A"])

    def test_format_escapes_and_pages(self):
        many = self.records + [rec("<i>x</i>", time_sec=50 + i, eaten=i,
                                   date=f"2026-10-2{i % 9} 10:00:00")
                               for i in range(10)]
        text = analytics.format_leaderboard(many, page=1, highlight="c")
        self.assertIn("стр. 2/2", text)
        self.assertNotIn("<i>", text)
        self.assertIn("&lt;i&gt;", text)
        self.assertIn("<pre>", text)
        self.assertIn("Пока нет", analytics.format_leaderboard([]))

    def test_player_stats(self):
        records, _ = analytics.parse_scores_text(GOOD_CSV)
        st = analytics.player_stats(records, "  ваня ")
        self.assertEqual((st["games"], st["wins"], st["losses"]), (2, 1, 1))
        self.assertEqual(st["fastest_win"], 12.5)
        self.assertEqual(st["best_place"], 1)
        self.assertEqual(st["longest_loss"], 95.0)
        self.assertIsNone(analytics.player_stats(records, "Нет такого"))
        self.assertIn("нет", analytics.format_stats(None, "<x>"))
        self.assertIn("&lt;x&gt;", analytics.format_stats(None, "<x>"))

    def test_achievements(self):
        records = [rec("Ваня", time_sec=15.0, eaten=3,
                       date=f"2026-10-2{i} 10:00:00") for i in range(5)]
        got = {a.code for a in analytics.achievements(records, "Ваня")
               if a.unlocked}
        self.assertEqual(got, {"first", "lightning", "hungry", "crumbs",
                               "streak", "hunter"})
        none = analytics.achievements([], "Ваня")
        self.assertFalse(any(a.unlocked for a in none))
        self.assertIn("0/8", analytics.format_achievements([], "Ваня"))


class LogTests(unittest.TestCase):
    def test_parse_log(self):
        s = analytics.parse_log_text(LOG_TEXT)
        self.assertEqual(s["launches"], 1)
        self.assertEqual(s["games"], 2)
        self.assertEqual(s["flee"], 2)
        self.assertEqual(s["calm"], 1)
        self.assertEqual((s["wins"], s["losses"]), (1, 1))
        self.assertEqual(s["level_errors"], 1)
        self.assertEqual(s["bad_lines"], 1)
        self.assertEqual(s["avg_win_time"], 18.4)
        self.assertEqual(s["flee_per_game"], 1.0)
        text = analytics.format_log_summary(s)
        self.assertIn("Пакман убегал", text)

    def test_missing_log(self):
        with TempPaths():
            self.assertIsNone(analytics.parse_log_file())
            self.assertIn("не найден", analytics.format_log_summary(None))


if __name__ == "__main__":
    unittest.main()
