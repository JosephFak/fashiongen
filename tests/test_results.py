import unittest

from fashiongen.fixtures import demo_results
from fashiongen.results import rank_results, safe_http_url


class ResultTests(unittest.TestCase):
    def test_premium_is_above_average_and_ranked_first(self):
        results = rank_results([
            {"link": "https://shop.test/low", "image_width": 100, "image_height": 100},
            {"link": "https://shop.test/high", "image_width": "1000", "image_height": "1000"},
            {"link": "https://shop.test/unknown"},
        ])
        self.assertTrue(results[0]["premium"])
        self.assertFalse(results[1]["premium"])
        self.assertFalse(results[2]["premium"])
        self.assertEqual(results[0]["link"], "https://shop.test/high")

    def test_unknown_dimensions_do_not_invent_quality(self):
        results = rank_results([{"link": "https://shop.test/a"}, {"link": "https://shop.test/b"}])
        self.assertTrue(all(not item["premium"] for item in results))

    def test_full_titles_are_preserved_and_duplicates_skipped(self):
        title = "A full product title " * 40
        results = rank_results([{"link": "https://shop.test/a", "title": title}, {"link": "https://shop.test/a"}])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], title)

    def test_unsafe_links_are_discarded(self):
        for url in ["javascript:alert(1)", "data:text/html,x", "//evil.test", "https://user:secret@shop.test/a", "https://[broken", "https://test.com\n"]:
            with self.subTest(url=url):
                self.assertEqual(safe_http_url(url), "")

    def test_malformed_optional_fields_and_thumbnail_dimensions(self):
        results = rank_results([None, {"link": "https://shop.test/a", "image_width": "NaN", "price": None,
                                     "thumbnail_width": 100, "thumbnail_height": 200}])
        self.assertEqual(results[0]["resolution"], 20000)
        self.assertEqual(results[0]["price"], "")

    def test_demo_has_multiple_pages_and_is_explicitly_marked(self):
        results = demo_results()
        self.assertEqual(len(results), 14)
        self.assertTrue(all(item["demo"] for item in results))
        self.assertTrue(results[0]["premium"])
