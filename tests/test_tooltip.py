import unittest

from shop_price_helper.model import TextLine
from shop_price_helper.tooltip import parse


def line(text: str, top: float, *, height: float = 0.04, x: float = 0.10,
         width: float = 0.45, confidence: float = 0.95) -> TextLine:
    return TextLine(text=text, confidence=confidence, box=(x, top - height, width, height))


def stack(*texts: str, top: float = 0.80, step: float = 0.05) -> list[TextLine]:
    return [line(text, top - i * step) for i, text in enumerate(texts)]


class TooltipParseTests(unittest.TestCase):
    def test_equipment_name_and_stats(self):
        item = parse(stack(
            "Blue Dragon Helmet",
            "Req Lev: 30",
            "STR +2",
            "DEX +1",
            "Weapon DEF: 42",
            "Slots: 7",
        ))
        self.assertIsNotNone(item)
        self.assertEqual(item.name, "Blue Dragon Helmet")
        self.assertEqual(item.stats["Req Lev"], "30")
        self.assertEqual(item.stats["STR"], "+2")
        self.assertEqual(item.stats["DEX"], "+1")
        self.assertEqual(item.stats["Weapon DEF"], "42")
        self.assertEqual(item.stats["Slots"], "7")
        self.assertEqual(item.category, "equip")
        self.assertEqual(item.quantity, 1)
        self.assertIn("STR=+2", item.variant)

    def test_quantity_and_stackable(self):
        item = parse(stack("Blue Potion", "Quantity: 100"))
        self.assertIsNotNone(item)
        self.assertEqual(item.name, "Blue Potion")
        self.assertEqual(item.quantity, 100)
        self.assertEqual(item.category, "stackable")
        self.assertEqual(item.key, "bluepotion")

    def test_quantity_suffix_in_name(self):
        item = parse(stack("Blue Potion x 250"))
        self.assertIsNotNone(item)
        self.assertEqual(item.name, "Blue Potion")
        self.assertEqual(item.quantity, 250)

    def test_chat_and_pickup_noise_is_ignored(self):
        item = parse(stack(
            "You received EXP (+13)",
            "You have gained mesos (+24)",
            "Blue Potion",
            "Quantity: 3",
        ))
        self.assertIsNotNone(item)
        self.assertEqual(item.name, "Blue Potion")
        self.assertEqual(item.quantity, 3)

    def test_item_name_starting_with_party_is_not_chat(self):
        item = parse(stack("Party Hat", "Quantity: 1"))
        self.assertIsNotNone(item)
        self.assertEqual(item.name, "Party Hat")

    def test_stats_variant_changes_key(self):
        clean = parse(stack("Blue Dragon Helmet", "Req Lev: 30", "STR +0", "Slots: 7"))
        scrolled = parse(stack("Blue Dragon Helmet", "Req Lev: 30", "STR +5", "Slots: 7"))
        self.assertNotEqual(clean.key, scrolled.key)

    def test_nothing_item_like(self):
        self.assertIsNone(parse([]))
        self.assertIsNone(parse(stack("You can't get anymore items.")))

    def test_code_or_terminal_text_is_not_an_item(self):
        self.assertIsNone(parse(stack(
            "hop-Price-Helper && . venv/bin/python -m shop_price_helper",
            ">/tmp/shopui.log",
            "cd /Users/kewee",
        )))

    def test_ocr_letter_numbers_are_fixed(self):
        item = parse(stack("Blue Dragon Helmet", "Req Lev: 3O", "Slots: 7"))
        self.assertEqual(item.stats["Req Lev"], "30")


if __name__ == "__main__":
    unittest.main()
