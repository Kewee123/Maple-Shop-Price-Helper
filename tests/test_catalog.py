import unittest

from shop_price_helper.catalog import lookup


class CatalogTests(unittest.TestCase):
    def test_lookup_is_case_and_punctuation_insensitive(self):
        item = lookup("iron-ore")
        self.assertIsNotNone(item)
        self.assertEqual(item.name, "Iron Ore")
        self.assertEqual(item.category, "Etc")

    def test_level_suffix_is_metadata(self):
        item = lookup("Jean Capris")
        self.assertIsNotNone(item)
        self.assertEqual(item.name, "Jean Capris")

    def test_unknown_text_is_rejected(self):
        self.assertIsNone(lookup("MapleStory World 31"))
        self.assertIsNone(lookup(""))

    def test_small_ocr_error_can_resolve_uniquely(self):
        item = lookup("Firewcod")
        self.assertIsNotNone(item)
        self.assertEqual(item.name, "Firewood")


if __name__ == "__main__":
    unittest.main()
