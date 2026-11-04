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

    def test_name_wins_over_a_nearer_description(self):
        # The description is lower on screen and closer to the capture centre; the
        # item name must still win.
        name = line("Aquamarine Ore", 0.78, width=0.30)
        description = line("The ore of a blue crystal.", 0.45, width=0.55)
        item = parse([name, description])
        self.assertIsNotNone(item)
        self.assertEqual(item.name, "Aquamarine Ore")

    def test_inventory_labels_are_not_item_names(self):
        item = parse(stack("ITEM INVENTORY", "Equip", "Use", "Set Up", "Etc", "Cash", "Deco"))
        self.assertIsNone(item)

    def test_hover_bullet_is_stripped_from_item_name(self):
        item = parse([line("• Diamond Ore", 0.52, x=0.18, width=0.13),
                      line("The ore of a transparent jewel.", 0.48, x=0.29, width=0.22)])
        self.assertIsNotNone(item)
        self.assertEqual(item.name, "Diamond Ore")

    def test_inventory_tab_fragment_does_not_beat_tooltip(self):
        # OCR output from a real inventory hover. "Ete" is a misread of "Etc";
        # the item name is lower and slightly left of the capture centre.
        lines = [
            line("Quest Helper (26)", 0.97, x=0.27, width=0.12),
            line("Arwen and the Glass Shoe", 0.93, x=0.28, width=0.19),
            line("ITEM INVENTORY", 0.91, x=0.00, width=0.10),
            line("Equip| Use SetUp", 0.87, x=0.00, width=0.13),
            line("Ete", 0.87, x=0.14, width=0.02),
            line("Cash", 0.87, x=0.18, width=0.03),
            line("Deco", 0.87, x=0.22, width=0.03),
            line("[Event] The Journey Begins", 0.86, x=0.28, width=0.20),
            line("30/30 Maple Leat", 0.83, x=0.28, width=0.12),
            line("19", 0.58, x=0.05, width=0.02),
            line("• Diamond Ore", 0.52, x=0.18, width=0.13),
            line("The ore of a transparent jewel.", 0.48, x=0.29, width=0.22),
            line("36", 0.47, x=0.16, width=0.02),
        ]
        item = parse(lines)
        self.assertIsNotNone(item)
        self.assertEqual(item.name, "Diamond Ore")

    def test_tab_words_are_not_an_item(self):
        for text in ("Ete", "Equip| Use SetUp", "Set Up", "ITEM INVENTORY"):
            with self.subTest(text=text):
                self.assertIsNone(parse([line(text, 0.80)]))

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
