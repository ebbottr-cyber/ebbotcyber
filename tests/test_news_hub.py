"""Offline tests for news ingestion, dedup, read-all and notification preferences."""
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from unittest.mock import patch
from xml.sax.saxutils import escape

from src.services import news_hub_service as news


def feed(title, guid):
    date = format_datetime(datetime.now(timezone.utc))
    xml = (
        "<rss><channel><item>"
        f"<title>{escape(title)}</title>"
        f"<guid>{escape(guid)}</guid>"
        "<link>https://news.google.com/rss/articles/test</link>"
        f"<pubDate>{date}</pubDate>"
        "<source>Example Publisher</source>"
        "</item></channel></rss>"
    )
    return xml.encode("utf-8")


class NewsHubTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_patch = patch.object(news, "DATABASE", Path(self.temp.name) / "etre_news.sqlite")
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)

    def test_rss_parsing_and_priority(self):
        items = news._rss_items("us", feed("BREAKING Fed raises interest rate", "one"))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["market"], "us")
        self.assertEqual(items[0]["severity"], "breaking")
        self.assertEqual(len(items[0]["id"]), 64)

    def test_first_import_is_read_then_new_article_notifies(self):
        with patch.object(news, "_CATEGORIES", {"tr": "test"}), patch.object(
            news, "_fetch_market", return_value=news._rss_items("tr", feed("BIST açıldı", "first"))
        ):
            first = news.refresh_news()
            again = news.refresh_news()
        self.assertEqual(first["inserted"], 1)
        self.assertTrue(first["bootstrapped"])
        self.assertEqual(again["inserted"], 0)
        self.assertEqual(news.news_status()["unread_count"], 0)

        with patch.object(news, "_CATEGORIES", {"tr": "test"}), patch.object(
            news, "_fetch_market", return_value=news._rss_items("tr", feed("BIST son dakika", "second"))
        ):
            next_run = news.refresh_news()
        self.assertEqual(next_run["inserted"], 1)
        self.assertEqual(news.news_status()["unread_count"], 1)
        rows = news.list_news()["items"]
        fresh = next(row for row in rows if not row["is_read"])
        self.assertEqual(news.mark_one_read(fresh["id"])["unread_count"], 0)

    def test_mark_all_and_persistent_mute(self):
        with closing(news._connect()) as db:
            for i in range(3):
                db.execute("""INSERT INTO news_articles(
                    id,market,title_original,source,url,published_at,inserted_at
                ) VALUES (?,?,?,?,?,?,?)""", (
                    str(i) * 64, "crypto", "Bitcoin market",
                    "Example", "https://news.google.com/item",
                    datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat(),
                ))
            db.commit()
        self.assertEqual(news.news_status()["unread_count"], 3)
        self.assertEqual(news.mark_all_read()["updated"], 3)
        self.assertEqual(news.news_status()["unread_count"], 0)
        news.set_notifications(False)
        self.assertFalse(news.news_status()["notifications_enabled"])
        with self.assertRaises(ValueError):
            news.mark_one_read("../bad")
        news.set_notifications(True)
        self.assertTrue(news.news_status()["notifications_enabled"])
        self.assertFalse(news.news_status()["ai_enabled"])
        news.set_ai_enabled(True)
        self.assertTrue(news.news_status()["ai_enabled"])
        news.set_ai_enabled(False)
        self.assertFalse(news.news_status()["ai_enabled"])

    def test_does_not_fabricate_a_translation_without_ai(self):
        item = news._rss_items("us", feed("Markets are volatile today", "plain"))[0]
        self.assertIsNone(item["title_tr"])
        self.assertEqual(news._extract_json('{"title_tr":"Piyasalar dalgalı"}')["title_tr"], "Piyasalar dalgalı")


if __name__ == "__main__":
    unittest.main()
