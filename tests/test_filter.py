import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import check  # noqa: E402

# 仿照 2026-11-18 實測的 Steam 搜尋結果格式：一筆 100% off、一筆 75% off、一筆套組（多個 appid）
FAKE_HTML = """
<a href="https://store.steampowered.com/app/111/Free_Game/" data-ds-appid="111" data-ds-itemkey="App_111" onmouseover="GameHover( this, event, 'global_hover', {&quot;type&quot;:&quot;app&quot;} );" class="search_result_row ds_collapse_flag ">
  <span class="title">Free &amp; Fun</span>
  <div class="discount_block search_discount_block" data-price-final="0" data-bundlediscount="0" data-discount="100"></div>
</a>
<a href="https://store.steampowered.com/app/222/Cheap/" data-ds-appid="222" class="search_result_row ds_collapse_flag ">
  <span class="title">Cheap Game</span>
  <div class="discount_block" data-price-final="11300" data-discount="75"></div>
</a>
<a href="https://store.steampowered.com/sub/9/" data-ds-appid="333,444" data-ds-packageid="9" class="search_result_row">
  <span class="title">Bundle</span>
  <div class="discount_block" data-discount="100"></div>
</a>
"""

GIVEAWAY = {"type": "game", "is_free": False,
            "price_overview": {"initial": 45500, "final": 0, "discount_percent": 100}}
F2P = {"type": "game", "is_free": True}
NORMAL_SALE = {"type": "game", "is_free": False,
               "price_overview": {"initial": 45500, "final": 11300, "discount_percent": 75}}


class TestParse(unittest.TestCase):
    def test_finds_100_percent_row(self):
        rows = {r["appid"]: r for r in check.parse_search_html(FAKE_HTML)}
        self.assertEqual(rows["111"]["discount"], 100)
        self.assertEqual(rows["111"]["name"], "Free & Fun")
        self.assertEqual(rows["222"]["discount"], 75)

    def test_skips_bundles(self):
        rows = check.parse_search_html(FAKE_HTML)
        self.assertEqual(sorted(r["appid"] for r in rows), ["111", "222"])


class TestGiveaway(unittest.TestCase):
    def test_giveaway_detected(self):
        self.assertTrue(check.is_giveaway(GIVEAWAY))

    def test_f2p_excluded(self):
        self.assertFalse(check.is_giveaway(F2P))

    def test_normal_sale_excluded(self):
        self.assertFalse(check.is_giveaway(NORMAL_SALE))

    def test_missing_data_excluded(self):
        self.assertFalse(check.is_giveaway(None))


class TestDiff(unittest.TestCase):
    def test_only_new_notified_and_ended_removed(self):
        seen = {"1": {"name": "old"}, "2": {"name": "ended"}}
        current = {"1": {"name": "old-now"}, "3": {"name": "new"}}
        new_ids, items = check.diff_seen(seen, current)
        self.assertEqual(new_ids, ["3"])
        self.assertEqual(set(items), {"1", "3"})
        self.assertEqual(items["1"]["name"], "old")  # 保留第一次看到時的資料


if __name__ == "__main__":
    unittest.main()
