import json
import os
import sqlite3
import tempfile
import unittest

from bot.services.formatter import format_trip_plan
from bot.services.trip_planner import (
    TRIP_RANGE_KM,
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


class TestCalculateStopsNeeded(unittest.TestCase):
    def test_zero_stops_within_range(self):
        self.assertEqual(calculate_stops_needed(200, range_km=TRIP_RANGE_KM), 0)
        self.assertEqual(calculate_stops_needed(TRIP_RANGE_KM, range_km=TRIP_RANGE_KM), 0)

    def test_one_stop_just_over_range(self):
        self.assertEqual(calculate_stops_needed(450, range_km=TRIP_RANGE_KM), 1)

    def test_multiple_stops_for_long_distance(self):
        self.assertEqual(calculate_stops_needed(850, range_km=TRIP_RANGE_KM), 2)
        self.assertEqual(calculate_stops_needed(1250, range_km=TRIP_RANGE_KM), 3)

    def test_zero_or_negative_distance(self):
        self.assertEqual(calculate_stops_needed(0), 0)
        self.assertEqual(calculate_stops_needed(-10), 0)


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
        # שתי עמדות סביב אותה נקודה (31.0, 35.0): אחת 150kW ואחת 50kW - יש להעדיף את המהירה
        _insert_station(self.db_path, "1", "Fast Station", 31.0, 35.0, max_power_kw=150.0)
        _insert_station(self.db_path, "2", "Slow Station", 31.0, 35.01, max_power_kw=50.0)

        station = await find_station_near_point(self.db_path, 31.0, 35.0)
        self.assertIsNotNone(station)
        self.assertEqual(station["name"], "Fast Station")

    async def test_falls_back_to_100kw_when_no_ultra_fast(self):
        _insert_station(self.db_path, "1", "Medium Station", 32.0, 35.0, max_power_kw=120.0)

        station = await find_station_near_point(self.db_path, 32.0, 35.0)
        self.assertIsNotNone(station)
        self.assertEqual(station["name"], "Medium Station")

    async def test_returns_none_when_only_slow_station_nearby(self):
        _insert_station(self.db_path, "1", "AC Station", 33.0, 35.0, max_power_kw=22.0)

        station = await find_station_near_point(self.db_path, 33.0, 35.0)
        self.assertIsNone(station)

    async def test_expands_radius_to_20km_when_needed(self):
        # כ-0.15 מעלות רוחב ~ 16.7 ק"מ: מחוץ לרדיוס הראשוני (10 ק"מ) אך בתוך הרדיוס המורחב (20 ק"מ)
        _insert_station(self.db_path, "1", "Far Fast Station", 34.15, 35.0, max_power_kw=180.0)

        station = await find_station_near_point(self.db_path, 34.0, 35.0)
        self.assertIsNotNone(station)
        self.assertEqual(station["name"], "Far Fast Station")

    async def test_returns_none_when_no_stations_at_all(self):
        station = await find_station_near_point(self.db_path, 29.0, 35.0)
        self.assertIsNone(station)


class TestPlanTrip(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_stations.db")
        _make_locations_db(self.db_path)

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    async def test_no_stops_for_short_trip(self):
        # תל אביב -> ירושלים, מרחק קצר בהרבה מטווח הסוללה
        plan = await plan_trip(32.0853, 34.7818, 31.7683, 35.2137, self.db_path)
        self.assertEqual(plan["num_stops"], 0)
        self.assertEqual(plan["stops"], [])
        self.assertEqual(plan["missing_segments"], [])
        self.assertGreater(plan["total_distance_km"], 0)
        self.assertGreater(plan["duration_hours"], 0)

    async def test_finds_station_for_long_trip_stop(self):
        # מוצא ויעד במרחק ~600 ק"מ ישר צפונה, מצריך עצירה אחת
        origin_lat, origin_lng = 31.0, 34.0
        dest_lat, dest_lng = 36.4, 34.0

        # ממקמים עמדה מהירה בדיוק על הנקודה המתוכננת לעצירה הראשונה (80% מהטווח, 320 ק"מ)
        from bot.services.trip_planner import TRIP_STOP_FRACTION
        from bot.services.station_search import haversine_km

        total_distance = haversine_km(origin_lat, origin_lng, dest_lat, dest_lng)
        target_km = TRIP_STOP_FRACTION * TRIP_RANGE_KM
        fraction = target_km / total_distance
        stop_lat, stop_lng = interpolate_point(origin_lat, origin_lng, dest_lat, dest_lng, fraction)
        _insert_station(self.db_path, "1", "Route Station", stop_lat, stop_lng, max_power_kw=180.0)

        plan = await plan_trip(origin_lat, origin_lng, dest_lat, dest_lng, self.db_path)

        self.assertEqual(plan["num_stops"], 1)
        self.assertEqual(len(plan["stops"]), 1)
        self.assertEqual(plan["stops"][0]["station"]["name"], "Route Station")
        self.assertEqual(plan["missing_segments"], [])

    async def test_reports_missing_segment_when_no_station_found(self):
        origin_lat, origin_lng = 31.0, 34.0
        dest_lat, dest_lng = 36.4, 34.0

        # אין עמדות טעינה בכלל לאורך המסלול
        plan = await plan_trip(origin_lat, origin_lng, dest_lat, dest_lng, self.db_path)

        self.assertEqual(plan["num_stops"], 1)
        self.assertEqual(plan["stops"], [])
        self.assertEqual(len(plan["missing_segments"]), 1)
        self.assertEqual(plan["missing_segments"][0]["segment_index"], 1)


class TestFormatTripPlan(unittest.TestCase):
    def test_format_no_stops(self):
        plan = {
            "total_distance_km": 60.0,
            "duration_hours": 60.0 / 90.0,
            "num_stops": 0,
            "stops": [],
            "missing_segments": [],
        }
        text = format_trip_plan(plan, "תל אביב", "ירושלים")
        self.assertIn("תל אביב", text)
        self.assertIn("ירושלים", text)
        self.assertIn("ללא עצירת טעינה", text)

    def test_format_with_stops(self):
        plan = {
            "total_distance_km": 600.0,
            "duration_hours": 600.0 / 90.0,
            "num_stops": 1,
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
                }
            ],
            "missing_segments": [],
        }
        text = format_trip_plan(plan, "תל אביב", "אילת")
        self.assertIn("עמדת דוגמה", text)
        self.assertIn("ChargeCo", text)
        self.assertIn("180", text)
        self.assertIn("עצירה 1", text)

    def test_format_with_missing_segment(self):
        plan = {
            "total_distance_km": 600.0,
            "duration_hours": 600.0 / 90.0,
            "num_stops": 1,
            "stops": [],
            "missing_segments": [{"segment_index": 1, "distance_km": 320.0}],
        }
        text = format_trip_plan(plan, "תל אביב", "אילת")
        self.assertIn("לא נמצאה עמדת טעינה מתאימה", text)


if __name__ == "__main__":
    unittest.main()
