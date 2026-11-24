import unittest
from unittest.mock import patch

from app.market_data.massive import MassiveClient


class MassiveWatchlistBatchTests(unittest.TestCase):
    def test_watchlist_uses_one_snapshot_request_for_all_symbols(self):
        client = MassiveClient(api_key="test-key")
        payload = {
            "status": "OK",
            "results": [
                {"ticker": "AAPL", "session": {"high": 110, "low": 100, "close": 105}},
                {"ticker": "MSFT", "session": {"high": 220, "low": 200, "close": 210}},
            ],
        }

        with patch.object(client, "_get", return_value=payload) as request:
            rows, errors = client.get_watchlist_statistics(["AAPL", "MSFT"])

        self.assertEqual(request.call_count, 1)
        request.assert_called_once_with("/v3/snapshot", {
            "ticker.any_of": "AAPL,MSFT",
            "type": "stocks",
            "limit": "2",
        })
        self.assertEqual(errors, [])
        self.assertEqual(rows[0]["daily_range"], 10.0)
        self.assertEqual(rows[1]["range_percent"], 20 / 210 * 100)


if __name__ == "__main__":
    unittest.main()
