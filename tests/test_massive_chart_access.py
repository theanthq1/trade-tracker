import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app.market_data.massive import MassiveClient, MassiveDataError


class MassiveFreePlanChartTests(unittest.TestCase):
    def test_current_eastern_date_is_rejected_before_request(self):
        client = MassiveClient(api_key="test-key")
        start = datetime(2026, 10, 23, 4, 0, tzinfo=ZoneInfo("America/New_York"))
        end = datetime(2026, 10, 23, 10, 31, tzinfo=ZoneInfo("America/New_York"))

        with patch.object(MassiveClient, "_free_plan_today", return_value=start.date()):
            with patch.object(client, "_get") as request:
                with self.assertRaisesRegex(MassiveDataError, "after midnight ET"):
                    client.get_historical_bars("AAPL", start, end, "1m")

        request.assert_not_called()

    def test_completed_date_uses_free_minute_aggregate_endpoint(self):
        client = MassiveClient(api_key="test-key")
        start = datetime(2026, 10, 22, 4, 0, tzinfo=ZoneInfo("America/New_York"))
        end = datetime(2026, 10, 22, 10, 31, tzinfo=ZoneInfo("America/New_York"))
        payload = {"status": "OK", "results": [{
            "t": 1792670400000, "o": 100, "h": 101, "l": 99, "c": 100.5, "v": 10,
        }]}

        with patch.object(client, "_get", return_value=payload) as request:
            client.get_historical_bars("AAPL", start, end, "1m")

        request.assert_called_once()
        self.assertTrue(request.call_args.args[0].startswith("/v2/aggs/ticker/AAPL/range/1/minute/"))
        self.assertEqual(request.call_args.args[1], {"adjusted": "false", "sort": "asc", "limit": "50000"})


if __name__ == "__main__":
    unittest.main()
