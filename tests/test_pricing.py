import tempfile
import unittest
from pathlib import Path

from shop_price_helper.model import PriceQuote, PriceSummary, ShopItem, parse_mesos
from shop_price_helper.pricing import (CozyMarketProvider, ManualPriceProvider, ManualStore,
                                       MesoWatchProvider, PriceService)


class MesosParsingTests(unittest.TestCase):
    def test_suffixes_and_commas(self):
        self.assertEqual(parse_mesos("1.2m"), 1_200_000)
        self.assertEqual(parse_mesos("500k"), 500_000)
        self.assertEqual(parse_mesos("2b"), 2_000_000_000)
        self.assertEqual(parse_mesos("1,234,567"), 1_234_567)
        self.assertEqual(parse_mesos("0"), 0)
        self.assertIsNone(parse_mesos(""))
        self.assertIsNone(parse_mesos("lots"))


class PriceSummaryTests(unittest.TestCase):
    def test_median_last_volume_range(self):
        summary = PriceSummary.from_quotes([
            PriceQuote(source="a", typical=100, last=90, volume=5, low=80, high=130),
            PriceQuote(source="b", typical=120, last=110, volume=7, low=70, high=150),
        ])
        self.assertEqual(summary.typical, 110)
        self.assertEqual(summary.last, 110)
        self.assertEqual(summary.volume, 12)
        self.assertEqual(summary.low, 70)
        self.assertEqual(summary.high, 150)
        self.assertEqual(summary.sources, ["a", "b"])

    def test_suggested_undercut_and_total(self):
        summary = PriceSummary.from_quotes([PriceQuote(source="a", typical=1_000_000)])
        self.assertEqual(summary.suggested(0.05), 950_000)
        self.assertEqual(summary.total_for(3), 2_850_000)

    def test_no_data(self):
        summary = PriceSummary.from_quotes([])
        self.assertIsNone(summary.typical)
        self.assertIsNone(summary.suggested())
        self.assertEqual(summary.sources, [])


class ManualStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ManualStore(Path(self.tmp.name) / "prices.json")
        self.item = ShopItem(name="Blue Dragon Helmet", category="equip",
                             stats={"Req Lev": "30", "STR": "+2", "Slots": "7"})

    def tearDown(self):
        self.tmp.cleanup()

    def test_round_trip_exact_variant(self):
        self.store.put(self.item, typical=1_200_000, last=1_100_000, volume=4, low=900_000, high=1_400_000)
        quote = self.store.quote(self.item)
        self.assertEqual(quote.typical, 1_200_000)
        self.assertEqual(quote.last, 1_100_000)
        self.assertEqual(quote.volume, 4)
        self.assertEqual(quote.note, "")

    def test_different_variant_warns(self):
        self.store.put(self.item, typical=1_200_000, last=None, volume=None, low=None, high=None)
        other = ShopItem(name="Blue Dragon Helmet", category="equip",
                         stats={"Req Lev": "30", "STR": "+5", "Slots": "7"})
        quote = self.store.quote(other)
        self.assertEqual(quote.typical, 1_200_000)
        self.assertIn("different stat variant", quote.note)

    def test_provider_and_service(self):
        provider = ManualPriceProvider(self.store)
        service = PriceService([provider, MesoWatchProvider(), CozyMarketProvider()])
        summary, notices = service.lookup(self.item)
        self.assertEqual(summary.quotes, [])
        self.assertTrue(any("MesoWatch" in note for note in notices))
        self.assertTrue(any("Cozy Market" in note for note in notices))
        self.store.put(self.item, typical=1_000_000, last=950_000, volume=2, low=900_000, high=1_100_000)
        summary, _ = service.lookup(self.item)
        self.assertEqual(summary.typical, 1_000_000)
        self.assertEqual(summary.sources, ["manual"])

    def test_links_encode_names(self):
        item = ShopItem(name="Blue Dragon Helmet")
        self.assertIn("Blue+Dragon+Helmet", MesoWatchProvider().url_for(item))
        self.assertIn("Blue+Dragon+Helmet", CozyMarketProvider().url_for(item))


if __name__ == "__main__":
    unittest.main()
