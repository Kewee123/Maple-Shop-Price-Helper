import unittest

import numpy as np

from shop_price_helper.quantity import TEMPLATES, _classify, read_count


def _draw(mask: np.ndarray, image: np.ndarray, x: int, y: int) -> None:
    height, width = mask.shape
    image[y:y + height, x:x + width][mask] = 245


def _canvas(*digits: str, x: int = 30, y: int = 60) -> np.ndarray:
    image = np.zeros((120, 180, 3), dtype=np.uint8)
    for digit in digits:
        mask = TEMPLATES[digit]
        _draw(mask, image, x, y)
        x += mask.shape[1] + 4
    return image


class CountTemplateTests(unittest.TestCase):
    def test_templates_are_the_count_font_size(self):
        for digit, template in TEMPLATES.items():
            with self.subTest(digit=digit):
                self.assertEqual(template.shape, (18, 12))

    def test_every_template_classifies_itself(self):
        for digit, template in TEMPLATES.items():
            with self.subTest(digit=digit):
                found, distance = _classify(template)
                self.assertEqual(found, digit)
                self.assertEqual(distance, 0.0)

    def test_six_is_the_real_glyph_not_a_rotated_nine(self):
        # The real "6" has an open staircase on the left; an 8 or a rotated 9
        # would be a closed loop at the top.
        six = TEMPLATES["6"]
        self.assertTrue(six[0, 4])
        self.assertFalse(six[0, 2])
        self.assertTrue(six[6, 0])
        self.assertFalse(six[6, 10])


class CountReaderTests(unittest.TestCase):
    cursor = (110, 80)

    def test_reads_single_and_multi_digit_counts(self):
        for digits in ("1", "16", "32", "200", "159"):
            with self.subTest(digits=digits):
                self.assertEqual(read_count(_canvas(*digits), self.cursor, 2.0),
                                 int(digits))

    def test_leading_zero_is_not_a_count(self):
        self.assertIsNone(read_count(_canvas("0", "5"), self.cursor, 2.0))

    def test_icon_highlight_wide_component_is_trimmed(self):
        image = np.zeros((120, 180, 3), dtype=np.uint8)
        wide = np.zeros((18, 14), dtype=bool)
        wide[:, :12] = TEMPLATES["2"]
        wide[4:10, 12:14] = True
        _draw(wide, image, 30, 60)
        _draw(TEMPLATES["0"], image, 48, 60)
        self.assertEqual(read_count(image, self.cursor, 2.0), 20)

    def test_slot_border_rejects_a_count(self):
        image = _canvas("3", "2")
        image[45:95, 70:72] = 250          # a bright slot divider
        self.assertIsNone(read_count(image, self.cursor, 2.0))

    def test_blank_area_has_no_count(self):
        self.assertIsNone(read_count(np.zeros((120, 180, 3), dtype=np.uint8),
                                     self.cursor, 2.0))

    def test_cursor_outside_the_image_is_safe(self):
        self.assertIsNone(read_count(_canvas("3", "2"), (10_000, 10_000), 2.0))


if __name__ == "__main__":
    unittest.main()
