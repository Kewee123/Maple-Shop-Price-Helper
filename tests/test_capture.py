import unittest

from shop_price_helper.capture import WindowInfo, inventory_rect, is_game_window, point_in_rect


class InventoryRegionTests(unittest.TestCase):
    def test_only_maplestory_client_is_scannable(self):
        maplestory = WindowInfo(1, 2, "MapleStory", "MapleStory Client", 0, 0, 800, 600)
        crossover = WindowInfo(3, 4, "CrossOver", "MapleStory", 0, 0, 800, 600)
        wine_client = WindowInfo(4, 5, "Wine64", "MapleStory", 0, 0, 800, 600)
        wine_preloader = WindowInfo(5, 6, "wine64-preloader", "MapleStory", 0, 0, 800, 600)
        chrome = WindowInfo(6, 7, "Google Chrome", "MesoWatch", 0, 0, 800, 600)
        self.assertTrue(is_game_window(maplestory))
        self.assertTrue(is_game_window(crossover))
        self.assertTrue(is_game_window(wine_client))
        self.assertTrue(is_game_window(wine_preloader))
        self.assertFalse(is_game_window(chrome))

    def test_inventory_region_is_anchored_to_game_window(self):
        window = WindowInfo(1, 2, "MapleStory", "", 100, 50, 1000, 800)
        self.assertEqual(inventory_rect(window), (140, 74, 700, 690))

    def test_points_outside_inventory_are_rejected(self):
        rect = (140, 74, 700, 690)
        self.assertTrue(point_in_rect((250, 200), rect))
        self.assertFalse(point_in_rect((900, 200), rect))
        self.assertFalse(point_in_rect((250, 720), rect))


if __name__ == "__main__":
    unittest.main()
