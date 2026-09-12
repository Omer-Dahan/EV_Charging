import json
import os
import sqlite3
import tempfile
import unittest

from bot.services.formatter import format_trip_plan
from bot.services.station_search import haversine_km
from bot.services.trip_planner import (
    TRIP_ROAD_DISTANCE_FACTOR,
    TRIP_STOP_SEARCH_FRACTION,
    calculate_available_range_km,
    calculate_stops_needed,
    find_station_near_point,
    interpolate_point,
    plan_trip,
)


def _make_locations_db(path: str) -> None:
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cello_id TEXT UNIQUE,
            name TEXT,
            address TEXT,
            city TEXT,
            lat REAL,
            lng REAL,
            provider_id TEXT,
            provider_name TEXT,
            max_per_kwh REAL,
            has_tariffs INTEGER,
            payment_options TEXT,
            facilities TEXT,
            status_summary TEXT,
            connectors TEXT,
            stations_count INTEGER,
            updated_at TEXT,
            sources TEXT,
            is_gov_official INTEGER
        )
    """)
    conn.commit()
    conn.close()


def _insert_station(
    db_path: str,
    cello_id: str,
    name: str,
    lat: float,
    lng: float,
    max_power_kw: float,
    provider_name: str = "TestProvider",
    max_per_kwh: float = 1.8,
) -> None:
    connectors = json.dumps([{"standard": "CCS2_COMBO", "maxPower": max_power_kw}])
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT INTO locations (cello_id, name, lat, lng, provider_name, max_per_kwh, connectors, stations_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (cello_id, name, lat, lng, provider_name, max_per_kwh, connectors),
    )
    conn.commit()
    conn.close()


class TestCalculateAvailableRangeKm(unittest.TestCase):
    def test_typical_case(self):
        # טווח 350, סוללה 80%, מרווח 10% -> 350 * 0.70 = 245
        self.assertAlmostEqual(calculate_available_range_km(350.0, 80.0, 10.0), 245.0)

    def test_full_battery_no_margin(self):
        self.assertAlmostEqual(calculate_available_range_km(400.0, 100.0, 0.0), 400.0)

    def test_battery_at_margin_gives_zero_range(self):
        self.assertEqual(calculate_available_range_km(350.0, 10.0, 10.0), 0.0)

    def test_battery_below_margin_gives_zero_range(self):
        self.assertEqual(calculate_available_range_km(350.0, 5.0, 10.0), 0.0)


class TestCalculateStopsNeeded(unittest.TestCase):
    def test_zero_stops_within_range(self):
        self.assertEqual(calculate_stops_needed(200, range_km=400.0), 0)
        self.assertEqual(calculate_stops_needed(400.0, range_km=400.0), 0)

    def test_one_stop_just_over_range(self):
        self.assertEqual(calculate_stops_needed(450, range_km=400.0), 1)

    def test_multiple_stops_for_long_distance(self):
        self.assertEqual(calculate_stops_needed(850, range_km=400.0), 2)
        self.assertEqual(calculate_stops_needed(1250, range_km=400.0), 3)

    def test_zero_or_negative_distance(self):
        self.assertEqual(calculate_stops_needed(0, range_km=400.0), 0)
        self.assertEqual(calculate_stops_needed(-10, range_km=400.0), 0)

    def test_zero_range_gives_zero_stops(self):
        self.assertEqual(calculate_stops_needed(500, range_km=0.0), 0)

    def test_smaller_real_range_needs_more_stops(self):
        # אותו מרחק, טווח זמין קטן יותר (רכב עם טווח אמיתי נמוך/סוללה נמוכה) -> יותר עצירות
        self.assertGreater(
            calculate_stops_needed(600, range_km=150.0),
            calculate_stops_needed(600, range_km=300.0),
        )


class TestInterpolatePoint(unittest.TestCase):
    def test_midpoint(self):
        lat, lng = interpolate_point(30.0, 34.0, 32.0, 36.0, 0.5)
        self.assertAlmostEqual(lat, 31.0)
        self.assertAlmostEqual(lng, 35.0)

    def test_endpoints(self):
        self.assertEqual(interpolate_point(30.0, 34.0, 32.0, 36.0, 0.0), (30.0, 34.0))
        self.assertEqual(interpolate_point(30.0, 34.0, 32.0, 36.0, 1.0), (32.0, 36.0))

    def test_fraction_clamped(self):
        self.assertEqual(interpolate_point(30.0, 34.0, 32.0, 36.0, -1.0), (30.0, 34.0))
        self.assertEqual(interpolate_point(30.0, 34.0, 32.0, 36.0, 2.0), (32.0, 36.0))


class TestFindStationNearPoint(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_stations.db")
        _make_locations_db(self.db_path)

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    async def test_prefers_ultra_fast_station_within_10km(self):
        _insert_station(self.db_path, "1", "Fast Station", 31.0, 35.0, max_power_kw=150.0)
        _insert_station(self.db_path, "2", "Slow Station", 31.0, 35.01, max_power_kw=50.0)

        station, relaxed = await find_station_near_point(self.db_path, 31.0, 35.0)
        self.assertIsNotNone(station)
        self.assertEqual(station["name"], "Fast Station")
        self.assertFalse(relaxed["providers"])
        self.assertFalse(relaxed["price"])
        self.assertEqual(relaxed["power_kw"], 150.0)

    async def test_falls_back_to_lower_power_when_no_preferred(self):
        _insert_station(self.db_path, "1", "Medium Station", 32.0, 35.0, max_power_kw=120.0)

        station, relaxed = await find_station_near_point(self.db_path, 32.0, 35.0)
        self.assertIsNotNone(station)
        self.assertEqual(station["name"], "Medium Station")
        self.assertEqual(relaxed["power_kw"], 100.0)

    async def test_relaxes_all_the_way_to_very_slow_station_as_last_resort(self):
        _insert_station(self.db_path, "1", "Slow AC Station", 33.0, 35.0, max_power_kw=7.0)

        station, relaxed = await find_station_near_point(self.db_path, 33.0, 35.0)
        self.assertIsNotNone(station)
        self.assertEqual(station["name"], "Slow AC Station")
        self.assertEqual(relaxed["power_kw"], 1.0)

    async def test_expands_radius_to_20km_when_needed(self):
        _insert_station(self.db_path, "1", "Far Fast Station", 34.15, 35.0, max_power_kw=180.0)

        station, relaxed = await find_station_near_point(self.db_path, 34.0, 35.0)
        self.assertIsNotNone(station)
        self.assertEqual(station["name"], "Far Fast Station")

    async def test_returns_none_when_no_stations_at_all(self):
        station, relaxed = await find_station_near_point(self.db_path, 29.0, 35.0)
        self.assertIsNone(station)

    async def test_respects_user_min_power_preference(self):
        _insert_station(self.db_path, "1", "200kW Station", 31.5, 35.5, max_power_kw=200.0)
        station, relaxed = await find_station_near_point(self.db_path, 31.5, 35.5, min_power_kw=200.0)
        self.assertIsNotNone(station)
        self.assertEqual(relaxed["power_kw"], 200.0)

    async def test_relaxes_power_when_user_preference_not_met(self):
        _insert_station(self.db_path, "1", "100kW Station", 31.6, 35.6, max_power_kw=100.0)
        station, relaxed = await find_station_near_point(self.db_path, 31.6, 35.6, min_power_kw=200.0)
        self.assertIsNotNone(station)
        self.assertEqual(station["name"], "100kW Station")
        self.assertEqual(relaxed["power_kw"], 100.0)

    async def test_filters_by_allowed_providers(self):
        _insert_station(self.db_path, "1", "Other Provider Station", 31.7, 35.7, max_power_kw=150.0, provider_name="OtherCo")
        station, relaxed = await find_station_near_point(
            self.db_path, 31.7, 35.7, allowed_providers=["OnlyThisCo"]
        )
        # אין עמדה של OnlyThisCo, אבל יש הקלה שמסירה את הגבלת המפעיל -> נמצאת עמדה
        self.assertIsNotNone(station)
        self.assertEqual(station["name"], "Other Provider Station")
        self.assertTrue(relaxed["providers"])

    async def test_prefers_allowed_provider_when_available(self):
        _insert_station(self.db_path, "1", "Preferred Station", 31.8, 35.8, max_power_kw=150.0, provider_name="PreferredCo")
        _insert_station(self.db_path, "2", "Other Station", 31.8, 35.8, max_power_kw=150.0, provider_name="OtherCo")
        station, relaxed = await find_station_near_point(
            self.db_path, 31.8, 35.8, allowed_providers=["PreferredCo"]
        )
        self.assertIsNotNone(station)
        self.assertEqual(station["name"], "Preferred Station")
        self.assertFalse(relaxed["providers"])

    async def test_relaxes_price_cap_when_no_cheap_station(self):
        _insert_station(self.db_path, "1", "Expensive Station", 31.9, 35.9, max_power_kw=150.0, max_per_kwh=3.0)
        station, relaxed = await find_station_near_point(self.db_path, 31.9, 35.9, max_price=1.0)
        self.assertIsNotNone(station)
        self.assertTrue(relaxed["price"])


class TestPlanTrip(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_stations.db")
        _make_locations_db(self.db_path)

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    async def test_no_stops_for_short_trip(self):
        # תל אביב -> ירושלים, מרחק קצר בהרבה מהטווח הזמין
        plan = await plan_trip(
            32.0853, 34.7818, 31.7683, 35.2137, self.db_path,
            real_range_km=350.0, battery_percent=80.0, safety_margin_percent=10.0,
        )
        self.assertEqual(plan["num_stops"], 0)
        self.assertEqual(plan["stops"], [])
        self.assertEqual(plan["missing_segments"], [])
        self.assertGreater(plan["total_distance_km"], 0)
        self.assertGreater(plan["duration_hours"], 0)

    async def test_road_distance_exceeds_straight_line_distance(self):
        plan = await plan_trip(31.0, 34.0, 32.0, 34.0, self.db_path)
        self.assertAlmostEqual(
            plan["total_distance_km"], plan["straight_line_km"] * TRIP_ROAD_DISTANCE_FACTOR
        )
        self.assertGreater(plan["total_distance_km"], plan["straight_line_km"])

    async def test_finds_station_for_long_trip_stop(self):
        origin_lat, origin_lng = 31.0, 34.0
        dest_lat, dest_lng = 36.4, 34.0

        available_range_km = 245.0  # 350 * (80-10)/100
        straight_total = haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)
        road_total = straight_total * TRIP_ROAD_DISTANCE_FACTOR
        target_km = available_range_km * TRIP_STOP_SEARCH_FRACTION
        fraction = target_km / road_total
        stop_lat, stop_lng = interpolate_point(origin_lat, origin_lng, dest_lat, dest_lng, fraction)
        _insert_station(self.db_path, "1", "Route Station", stop_lat, stop_lng, max_power_kw=180.0)

        plan = await plan_trip(
            origin_lat, origin_lng, dest_lat, dest_lng, self.db_path,
            real_range_km=350.0, battery_percent=80.0, safety_margin_percent=10.0,
        )

        self.assertGreaterEqual(plan["num_stops"], 1)
        first_stop = next(s for s in plan["stops"] if s["segment_index"] == 1)
        self.assertEqual(first_stop["station"]["name"], "Route Station")

    async def test_reports_missing_segment_when_no_station_found(self):
        origin_lat, origin_lng = 31.0, 34.0
        dest_lat, dest_lng = 36.4, 34.0

        plan = await plan_trip(
            origin_lat, origin_lng, dest_lat, dest_lng, self.db_path,
            real_range_km=350.0, battery_percent=80.0, safety_margin_percent=10.0,
        )

        self.assertGreaterEqual(plan["num_stops"], 1)
        self.assertEqual(plan["stops"], [])
        self.assertGreaterEqual(len(plan["missing_segments"]), 1)
        self.assertEqual(plan["missing_segments"][0]["segment_index"], 1)

    async def test_larger_real_range_reduces_stops(self):
        origin_lat, origin_lng = 31.0, 34.0
        dest_lat, dest_lng = 33.0, 34.0

        plan_small_range = await plan_trip(
            origin_lat, origin_lng, dest_lat, dest_lng, self.db_path,
            real_range_km=150.0, battery_percent=80.0, safety_margin_percent=10.0,
        )
        plan_large_range = await plan_trip(
            origin_lat, origin_lng, dest_lat, dest_lng, self.db_path,
            real_range_km=500.0, battery_percent=80.0, safety_margin_percent=10.0,
        )
        self.assertGreaterEqual(plan_small_range["num_stops"], plan_large_range["num_stops"])

    async def test_car_params_reflected_in_plan(self):
        plan = await plan_trip(
            32.0853, 34.7818, 31.7683, 35.2137, self.db_path,
            real_range_km=300.0, battery_percent=70.0, safety_margin_percent=15.0,
            consumption_kwh_per_100km=20.0, min_power_kw=100.0,
        )
        self.assertEqual(plan["car_params"]["real_range_km"], 300.0)
        self.assertEqual(plan["car_params"]["battery_percent"], 70.0)
        self.assertEqual(plan["car_params"]["safety_margin_percent"], 15.0)
        self.assertEqual(plan["car_params"]["consumption_kwh_per_100km"], 20.0)
        self.assertEqual(plan["car_params"]["min_power_kw"], 100.0)
        self.assertAlmostEqual(plan["available_range_km"], calculate_available_range_km(300.0, 70.0, 15.0))


class TestFormatTripPlan(unittest.TestCase):
    def test_format_no_stops(self):
        plan = {
            "total_distance_km": 60.0,
            "straight_line_km": 48.0,
            "duration_hours": 60.0 / 90.0,
            "num_stops": 0,
            "available_range_km": 245.0,
            "car_params": {
                "real_range_km": 350.0, "battery_percent": 80.0,
                "safety_margin_percent": 10.0, "consumption_kwh_per_100km": 18.0,
                "min_power_kw": None,
            },
            "stops": [],
            "missing_segments": [],
        }
        text = format_trip_plan(plan, "תל אביב", "ירושלים")
        self.assertIn("תל אביב", text)
        self.assertIn("ירושלים", text)
        self.assertIn("ללא עצירת טעינה", text)
        self.assertIn("350", text)

    def test_format_with_stops(self):
        plan = {
            "total_distance_km": 600.0,
            "straight_line_km": 480.0,
            "duration_hours": 600.0 / 90.0,
            "num_stops": 1,
            "available_range_km": 245.0,
            "car_params": {
                "real_range_km": 350.0, "battery_percent": 80.0,
                "safety_margin_percent": 10.0, "consumption_kwh_per_100km": 18.0,
                "min_power_kw": 150.0,
            },
            "stops": [
                {
                    "segment_index": 1,
                    "distance_from_origin_km": 320.0,
                    "station": {
                        "name": "עמדת דוגמה",
                        "provider_name": "ChargeCo",
                        "max_power": 180.0,
                        "max_per_kwh": 1.9,
                        "connectors": json.dumps([{"standard": "CCS2_COMBO", "maxPower": 180.0}]),
                    },
                    "relaxation": {"providers": False, "price": False, "power_kw": 150.0},
                }
            ],
            "missing_segments": [],
        }
        text = format_trip_plan(plan, "תל אביב", "אילת")
        self.assertIn("עמדת דוגמה", text)
        self.assertIn("ChargeCo", text)
        self.assertIn("180", text)
        self.assertIn("עצירה 1", text)
        self.assertNotIn("הועדפו הקלות", text)

    def test_format_shows_relaxation_note(self):
        plan = {
            "total_distance_km": 600.0,
            "straight_line_km": 480.0,
            "duration_hours": 600.0 / 90.0,
            "num_stops": 1,
            "available_range_km": 245.0,
            "car_params": {
                "real_range_km": 350.0, "battery_percent": 80.0,
                "safety_margin_percent": 10.0, "consumption_kwh_per_100km": 18.0,
                "min_power_kw": 200.0,
            },
            "stops": [
                {
                    "segment_index": 1,
                    "distance_from_origin_km": 320.0,
                    "station": {
                        "name": "עמדה חלשה יותר",
                        "provider_name": "ChargeCo",
                        "max_power": 100.0,
                        "max_per_kwh": 1.9,
                        "connectors": json.dumps([{"standard": "CCS2_COMBO", "maxPower": 100.0}]),
                    },
                    "relaxation": {"providers": True, "price": True, "power_kw": 100.0},
                }
            ],
            "missing_segments": [],
        }
        text = format_trip_plan(plan, "תל אביב", "אילת")
        self.assertIn("הועדפו הקלות", text)
        self.assertIn("כל המפעילים", text)
        self.assertIn("תקרת המחיר", text)
        self.assertIn("100kW", text)

    def test_format_with_missing_segment(self):
        plan = {
            "total_distance_km": 600.0,
            "straight_line_km": 480.0,
            "duration_hours": 600.0 / 90.0,
            "num_stops": 1,
            "available_range_km": 245.0,
            "car_params": {
                "real_range_km": 350.0, "battery_percent": 80.0,
                "safety_margin_percent": 10.0, "consumption_kwh_per_100km": 18.0,
                "min_power_kw": None,
            },
            "stops": [],
            "missing_segments": [{"segment_index": 1, "distance_km": 320.0}],
        }
        text = format_trip_plan(plan, "תל אביב", "אילת")
        self.assertIn("לא נמצאה עמדת טעינה מתאימה", text)


if __name__ == "__main__":
    unittest.main()
