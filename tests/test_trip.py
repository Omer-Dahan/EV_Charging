import json
import os
import sqlite3
import tempfile
import unittest
from typing import Optional

from unittest.mock import AsyncMock, patch

from bot.services import trip_planner
from bot.services.formatter import format_trip_plan
from bot.services.station_search import haversine_km
from bot.services.trip_planner import (
    TRIP_ROAD_DISTANCE_FACTOR,
    TripRangeError,
    battery_percent_after_km,
    build_route,
    build_straight_line_route,
    calculate_available_range_km,
    calculate_recharged_range_km,
    calculate_stops_needed,
    find_station_near_point,
    interpolate_point,
    plan_trip,
    point_at_km,
    project_on_route,
)

# כל בדיקות התכנון רצות על מסלול קו-אווירי כדי שלא ייגשו ל-OSRM ברשת. הניתוב
# האמיתי נבדק בנפרד ב-TestRouting, עם השירות ממוקק.
NO_ROUTING = {"use_routing": False}


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

    def test_nearly_empty_battery_gives_a_very_short_first_leg(self):
        # המקרה שדווח: 400 ק"מ רכב, 20% סוללה, 10% מרווח -> 10% מהטווח = 40 ק"מ
        self.assertAlmostEqual(calculate_available_range_km(400.0, 20.0, 10.0), 40.0)


class TestCalculateRechargedRangeKm(unittest.TestCase):
    def test_full_recharge_restores_almost_the_whole_range(self):
        # אחרי טעינה ל-100% נשאר רק מרווח הביטחון מחוץ לחשבון
        self.assertAlmostEqual(calculate_recharged_range_km(400.0, 100.0, 10.0), 360.0)

    def test_partial_recharge_target(self):
        self.assertAlmostEqual(calculate_recharged_range_km(400.0, 80.0, 10.0), 280.0)

    def test_recharged_range_is_independent_of_the_starting_battery(self):
        """זה הלב של התיקון: הטווח שאחרי הטעינה לא מושפע מהסוללה שאיתה יצאנו לדרך."""
        start_empty = calculate_available_range_km(400.0, 20.0, 10.0)
        start_full = calculate_available_range_km(400.0, 90.0, 10.0)
        self.assertNotAlmostEqual(start_empty, start_full)
        self.assertAlmostEqual(
            calculate_recharged_range_km(400.0, 100.0, 10.0),
            calculate_recharged_range_km(400.0, 100.0, 10.0),
        )
        self.assertAlmostEqual(calculate_recharged_range_km(400.0, 100.0, 10.0), 360.0)


class TestBatteryPercentAfterKm(unittest.TestCase):
    def test_consumes_proportionally_to_the_real_range(self):
        self.assertAlmostEqual(battery_percent_after_km(100.0, 200.0, 400.0), 50.0)
        self.assertAlmostEqual(battery_percent_after_km(20.0, 35.0, 400.0), 11.25)

    def test_never_reports_negative_battery(self):
        self.assertEqual(battery_percent_after_km(20.0, 500.0, 400.0), 0.0)

    def test_zero_range_is_a_no_op(self):
        self.assertEqual(battery_percent_after_km(55.0, 100.0, 0.0), 55.0)


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

    async def test_excluded_station_is_skipped(self):
        _insert_station(self.db_path, "1", "עמדה שכבר בשימוש", 31.4, 35.4, max_power_kw=200.0)
        _insert_station(self.db_path, "2", "עמדה חלופית", 31.4, 35.41, max_power_kw=150.0)

        used, _ = await find_station_near_point(self.db_path, 31.4, 35.4)
        self.assertEqual(used["name"], "עמדה שכבר בשימוש")

        other, _ = await find_station_near_point(self.db_path, 31.4, 35.4, exclude_ids={used["id"]})
        self.assertIsNotNone(other)
        self.assertEqual(other["name"], "עמדה חלופית")

    async def test_relaxes_price_cap_when_no_cheap_station(self):
        _insert_station(self.db_path, "1", "Expensive Station", 31.9, 35.9, max_power_kw=150.0, max_per_kwh=3.0)
        station, relaxed = await find_station_near_point(self.db_path, 31.9, 35.9, max_price=1.0)
        self.assertIsNotNone(station)
        self.assertTrue(relaxed["price"])


# מסלול הבדיקות הוא קו צפון-דרום על lng=35, כדי שמיקום עמדה לאורך המסלול ייגזר
# ישירות מקו הרוחב שלה ואפשר יהיה למקם עמדות במרחק מדויק מהמוצא.
CORRIDOR_LNG = 35.0
CORRIDOR_ORIGIN_LAT = 30.0


def _corridor_km_per_deg() -> float:
    """כמה ק"מ *לאורך המסלול* שווה מעלת רוחב אחת, כולל מקדם הכביש."""
    return haversine_km(CORRIDOR_ORIGIN_LAT, CORRIDOR_LNG, CORRIDOR_ORIGIN_LAT + 1.0, CORRIDOR_LNG) \
        * TRIP_ROAD_DISTANCE_FACTOR


def _corridor_lat_at_km(km: float) -> float:
    return CORRIDOR_ORIGIN_LAT + km / _corridor_km_per_deg()


class TestPlanTrip(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_stations.db")
        _make_locations_db(self.db_path)
        self.next_id = 0

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    def _station_at_km(self, km: float, power_kw: float = 180.0, name: Optional[str] = None) -> str:
        """שותל עמדה על מסלול הבדיקה, במרחק km מהמוצא לאורך המסלול."""
        self.next_id += 1
        name = name or f'עמדה ב-{km:.0f} ק"מ'
        _insert_station(
            self.db_path, str(self.next_id), name,
            _corridor_lat_at_km(km), CORRIDOR_LNG, max_power_kw=power_kw,
        )
        return name

    async def _plan_corridor(self, total_km: float, **kwargs) -> dict:
        dest_lat = _corridor_lat_at_km(total_km)
        return await plan_trip(
            CORRIDOR_ORIGIN_LAT, CORRIDOR_LNG, dest_lat, CORRIDOR_LNG, self.db_path,
            **NO_ROUTING, **kwargs,
        )

    async def test_no_stops_for_short_trip(self):
        # תל אביב -> ירושלים, מרחק קצר בהרבה מהטווח הזמין
        plan = await plan_trip(
            32.0853, 34.7818, 31.7683, 35.2137, self.db_path, **NO_ROUTING,
            real_range_km=350.0, battery_percent=80.0, safety_margin_percent=10.0,
        )
        self.assertEqual(plan["num_stops"], 0)
        self.assertEqual(plan["stops"], [])
        self.assertEqual(plan["missing_segments"], [])
        self.assertGreater(plan["total_distance_km"], 0)
        self.assertGreater(plan["duration_hours"], 0)

    async def test_road_distance_exceeds_straight_line_distance(self):
        plan = await plan_trip(31.0, 34.0, 32.0, 34.0, self.db_path, **NO_ROUTING)
        self.assertAlmostEqual(
            plan["total_distance_km"], plan["straight_line_km"] * TRIP_ROAD_DISTANCE_FACTOR
        )
        self.assertGreater(plan["total_distance_km"], plan["straight_line_km"])

    async def test_low_battery_long_trip_needs_only_two_stops(self):
        """הבאג שדווח: יציאה לדרך ארוכה עם סוללה כמעט ריקה.

        רק הרגל הראשונה קצרה (40 ק"מ); אחרי הטעינה הראשונה הרכב ממשיך עם טווח מלא,
        ולכן צריך שתי עצירות בלבד - ולא עצירה כל ~20 ק"מ לאורך כל הדרך.
        """
        self._station_at_km(35.0, name="עצירה ראשונה")
        self._station_at_km(370.0, name="עצירה שנייה")
        # עמדות מפתות באמצע: אסור שהמתכנן יעצור בהן, הן בתוך טווח הרגל.
        for decoy_km in (100.0, 150.0, 200.0, 250.0):
            self._station_at_km(decoy_km, name=f"פיתיון {decoy_km:.0f}")

        plan = await self._plan_corridor(
            520.0, real_range_km=400.0, battery_percent=20.0, safety_margin_percent=10.0,
        )

        self.assertEqual(plan["num_stops"], 2)
        self.assertEqual([s["station"]["name"] for s in plan["stops"]],
                         ["עצירה ראשונה", "עצירה שנייה"])
        self.assertAlmostEqual(plan["available_range_km"], 40.0)
        self.assertAlmostEqual(plan["recharged_range_km"], 360.0)

    async def test_every_leg_is_within_the_range_available_for_it(self):
        """כל רגל חייבת להיות קצרה מהטווח שעמד לרשות הנהג כשיצא אליה."""
        for km in range(20, 1200, 20):
            self._station_at_km(float(km))

        plan = await self._plan_corridor(
            1200.0, real_range_km=400.0, battery_percent=20.0, safety_margin_percent=10.0,
        )

        self.assertGreaterEqual(len(plan["stops"]), 2)
        ranges = [plan["available_range_km"]] + [plan["recharged_range_km"]] * len(plan["stops"])
        legs = [s["leg_distance_km"] for s in plan["stops"]]
        legs.append(plan["total_distance_km"] - plan["stops"][-1]["distance_from_origin_km"])
        for leg_km, range_km in zip(legs, ranges):
            self.assertLessEqual(leg_km, range_km + 0.01)

    async def test_does_not_reuse_the_same_station_twice(self):
        for km in range(20, 1200, 20):
            self._station_at_km(float(km))

        plan = await self._plan_corridor(
            1200.0, real_range_km=400.0, battery_percent=20.0, safety_margin_percent=10.0,
        )

        ids = [s["station"]["id"] for s in plan["stops"]]
        self.assertEqual(len(ids), len(set(ids)))

    async def test_stops_carry_battery_arrival_and_departure(self):
        self._station_at_km(35.0)
        self._station_at_km(370.0)

        plan = await self._plan_corridor(
            520.0, real_range_km=400.0, battery_percent=20.0, safety_margin_percent=10.0,
        )

        first, second = plan["stops"]
        # 20% פחות 35 ק"מ מתוך טווח 400 ק"מ = 20% - 8.75% ≈ 11%
        self.assertAlmostEqual(first["battery_arrival_percent"], 20.0 - 35.0 / 400.0 * 100.0, places=1)
        self.assertEqual(first["battery_departure_percent"], 100.0)
        # יוצאים מהעצירה הראשונה ב-100% ונוסעים את אורך הרגל השנייה
        expected_second = 100.0 - second["leg_distance_km"] / 400.0 * 100.0
        self.assertAlmostEqual(second["battery_arrival_percent"], expected_second, places=1)
        # אחוז הסוללה ביעד נגזר מהעצירה האחרונה
        remaining_km = plan["total_distance_km"] - second["distance_from_origin_km"]
        self.assertAlmostEqual(
            plan["arrival_battery_percent"], 100.0 - remaining_km / 400.0 * 100.0, places=1
        )

    async def test_recharge_target_below_full_shortens_later_legs(self):
        for km in range(20, 900, 20):
            self._station_at_km(float(km))

        plan_full = await self._plan_corridor(
            900.0, real_range_km=400.0, battery_percent=100.0, safety_margin_percent=10.0,
            recharge_target_percent=100.0,
        )
        plan_partial = await self._plan_corridor(
            900.0, real_range_km=400.0, battery_percent=100.0, safety_margin_percent=10.0,
            recharge_target_percent=80.0,
        )

        self.assertAlmostEqual(plan_partial["recharged_range_km"], 280.0)
        self.assertGreaterEqual(plan_partial["num_stops"], plan_full["num_stops"])
        self.assertTrue(all(s["battery_departure_percent"] == 80.0 for s in plan_partial["stops"]))

    async def test_stop_is_placed_at_its_real_distance_along_the_route(self):
        self._station_at_km(300.0, name="עמדה מדודה")
        plan = await self._plan_corridor(
            600.0, real_range_km=400.0, battery_percent=100.0, safety_margin_percent=10.0,
        )
        stop = plan["stops"][0]
        self.assertEqual(stop["station"]["name"], "עמדה מדודה")
        self.assertAlmostEqual(stop["distance_from_origin_km"], 300.0, delta=1.0)
        self.assertLess(stop["off_route_km"], 1.0)

    async def test_ignores_station_far_off_the_route(self):
        # אותו מרחק לאורך המסלול, אבל 60 ק"מ הצידה - סטייה, לא עצירה בדרך
        _insert_station(
            self.db_path, "far", "עמדה רחוקה מהדרך",
            _corridor_lat_at_km(300.0), CORRIDOR_LNG + 0.65, max_power_kw=180.0,
        )
        plan = await self._plan_corridor(
            600.0, real_range_km=400.0, battery_percent=100.0, safety_margin_percent=10.0,
        )
        self.assertEqual(plan["stops"], [])
        self.assertEqual(len(plan["missing_segments"]), 1)

    async def test_falls_back_to_earlier_station_when_window_is_empty(self):
        # העמדה היחידה נמצאת לפני החלון המועדף (60%-95% מהטווח) אך בתוך הטווח
        self._station_at_km(150.0, name="עמדה מוקדמת")
        plan = await self._plan_corridor(
            600.0, real_range_km=400.0, battery_percent=100.0, safety_margin_percent=10.0,
        )
        self.assertEqual(len(plan["stops"]), 1)
        self.assertEqual(plan["stops"][0]["station"]["name"], "עמדה מוקדמת")

    async def test_reports_missing_segment_when_no_station_found(self):
        plan = await self._plan_corridor(
            750.0, real_range_km=350.0, battery_percent=80.0, safety_margin_percent=10.0,
        )
        self.assertGreaterEqual(plan["num_stops"], 1)
        self.assertEqual(plan["stops"], [])
        self.assertGreaterEqual(len(plan["missing_segments"]), 1)
        self.assertEqual(plan["missing_segments"][0]["segment_index"], 1)

    async def test_larger_real_range_reduces_stops(self):
        for km in range(20, 800, 20):
            self._station_at_km(float(km))

        plan_small_range = await self._plan_corridor(
            800.0, real_range_km=150.0, battery_percent=80.0, safety_margin_percent=10.0,
        )
        plan_large_range = await self._plan_corridor(
            800.0, real_range_km=500.0, battery_percent=80.0, safety_margin_percent=10.0,
        )
        self.assertGreater(plan_small_range["num_stops"], plan_large_range["num_stops"])

    async def test_battery_below_safety_margin_raises_clear_error(self):
        with self.assertRaises(TripRangeError) as ctx:
            await self._plan_corridor(
                500.0, real_range_km=400.0, battery_percent=5.0, safety_margin_percent=10.0,
            )
        self.assertIn("מרווח הביטחון", str(ctx.exception))

    async def test_car_params_reflected_in_plan(self):
        plan = await plan_trip(
            32.0853, 34.7818, 31.7683, 35.2137, self.db_path, **NO_ROUTING,
            real_range_km=300.0, battery_percent=70.0, safety_margin_percent=15.0,
            consumption_kwh_per_100km=20.0, min_power_kw=100.0,
        )
        self.assertEqual(plan["car_params"]["real_range_km"], 300.0)
        self.assertEqual(plan["car_params"]["battery_percent"], 70.0)
        self.assertEqual(plan["car_params"]["safety_margin_percent"], 15.0)
        self.assertEqual(plan["car_params"]["consumption_kwh_per_100km"], 20.0)
        self.assertEqual(plan["car_params"]["min_power_kw"], 100.0)
        self.assertEqual(plan["car_params"]["recharge_target_percent"], 100.0)
        self.assertAlmostEqual(plan["available_range_km"], calculate_available_range_km(300.0, 70.0, 15.0))


class TestRoute(unittest.TestCase):
    def test_straight_line_route_length_uses_road_factor(self):
        route = build_straight_line_route(31.0, 35.0, 32.0, 35.0)
        self.assertEqual(route["source"], "straight_line")
        self.assertAlmostEqual(
            route["total_km"], haversine_km(31.0, 35.0, 32.0, 35.0) * TRIP_ROAD_DISTANCE_FACTOR
        )
        self.assertAlmostEqual(route["cumulative_km"][-1], route["total_km"])

    def test_point_at_km_walks_along_the_route(self):
        route = build_straight_line_route(31.0, 35.0, 32.0, 35.0)
        start = point_at_km(route, 0.0)
        middle = point_at_km(route, route["total_km"] / 2)
        end = point_at_km(route, route["total_km"])
        self.assertAlmostEqual(start[0], 31.0)
        self.assertAlmostEqual(middle[0], 31.5)
        self.assertAlmostEqual(end[0], 32.0)

    def test_point_at_km_clamps_out_of_range_values(self):
        route = build_straight_line_route(31.0, 35.0, 32.0, 35.0)
        self.assertAlmostEqual(point_at_km(route, -50.0)[0], 31.0)
        self.assertAlmostEqual(point_at_km(route, 10_000.0)[0], 32.0)

    def test_project_on_route_returns_along_and_off_distances(self):
        route = build_straight_line_route(31.0, 35.0, 32.0, 35.0)
        along_km, off_km = project_on_route(route, 31.5, 35.0)
        self.assertAlmostEqual(along_km, route["total_km"] / 2, delta=1.0)
        self.assertAlmostEqual(off_km, 0.0, delta=0.5)

    def test_project_on_route_measures_sideways_distance(self):
        route = build_straight_line_route(31.0, 35.0, 32.0, 35.0)
        _, off_km = project_on_route(route, 31.5, 35.1)
        self.assertAlmostEqual(off_km, 9.5, delta=1.0)


class TestRouting(unittest.IsolatedAsyncioTestCase):
    async def test_uses_osrm_route_when_available(self):
        osrm_route = {
            "coords": [(31.0, 35.0), (31.5, 35.2), (32.0, 35.0)],
            "cumulative_km": [0.0, 60.0, 130.0],
            "total_km": 130.0,
            "source": "osrm",
            "duration_hours": 1.75,
        }
        with patch.object(trip_planner, "fetch_road_route", AsyncMock(return_value=osrm_route)):
            route = await build_route(31.0, 35.0, 32.0, 35.0, use_routing=True)
        self.assertIs(route, osrm_route)

    async def test_falls_back_to_straight_line_when_routing_unavailable(self):
        with patch.object(trip_planner, "fetch_road_route", AsyncMock(return_value=None)):
            route = await build_route(31.0, 35.0, 32.0, 35.0, use_routing=True)
        self.assertEqual(route["source"], "straight_line")

    async def test_routing_is_skipped_when_disabled(self):
        fetch = AsyncMock(return_value=None)
        with patch.object(trip_planner, "fetch_road_route", fetch):
            route = await build_route(31.0, 35.0, 32.0, 35.0, use_routing=False)
        fetch.assert_not_awaited()
        self.assertEqual(route["source"], "straight_line")

    def test_parses_osrm_payload_into_route(self):
        payload = {
            "code": "Ok",
            "routes": [{
                "distance": 130_000.0,
                "duration": 6300.0,
                # OSRM מחזיר [lng, lat] - חייב להתהפך
                "geometry": {"coordinates": [[35.0, 31.0], [35.2, 31.5], [35.0, 32.0]]},
            }],
        }
        route = trip_planner._parse_osrm_payload(payload)
        self.assertEqual(route["source"], "osrm")
        self.assertAlmostEqual(route["total_km"], 130.0)
        self.assertAlmostEqual(route["duration_hours"], 1.75)
        self.assertEqual(route["coords"][0], (31.0, 35.0))
        self.assertAlmostEqual(route["cumulative_km"][-1], 130.0)

    def test_rejects_unusable_osrm_payloads(self):
        self.assertIsNone(trip_planner._parse_osrm_payload({"code": "NoRoute", "routes": []}))
        self.assertIsNone(trip_planner._parse_osrm_payload({"code": "Ok", "routes": []}))
        self.assertIsNone(trip_planner._parse_osrm_payload(
            {"code": "Ok", "routes": [{"distance": 0.0, "geometry": {"coordinates": []}}]}
        ))


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
        # בלי ניתוב אמיתי הפלט אומר במפורש שהמרחק הוא הערכה מקו אווירי
        self.assertIn("מקו אווירי", text)

    def test_format_notes_real_road_routing(self):
        plan = {
            "total_distance_km": 488.0,
            "straight_line_km": 412.0,
            "duration_hours": 6.9,
            "num_stops": 0,
            "route_source": "osrm",
            "available_range_km": 245.0,
            "car_params": {
                "real_range_km": 350.0, "battery_percent": 80.0,
                "safety_margin_percent": 10.0, "consumption_kwh_per_100km": 18.0,
                "min_power_kw": None,
            },
            "stops": [],
            "missing_segments": [],
        }
        text = format_trip_plan(plan, "אילת", "גולן")
        self.assertIn("ניתוב אמיתי בכבישים", text)
        self.assertNotIn("מקו אווירי", text)

    def test_format_with_stops(self):
        plan = {
            "total_distance_km": 600.0,
            "straight_line_km": 480.0,
            "duration_hours": 600.0 / 90.0,
            "num_stops": 1,
            "available_range_km": 245.0,
            "recharged_range_km": 360.0,
            "arrival_battery_percent": 22.0,
            "route_source": "osrm",
            "car_params": {
                "real_range_km": 350.0, "battery_percent": 80.0,
                "safety_margin_percent": 10.0, "consumption_kwh_per_100km": 18.0,
                "recharge_target_percent": 100.0, "min_power_kw": 150.0,
            },
            "stops": [
                {
                    "segment_index": 1,
                    "distance_from_origin_km": 320.0,
                    "leg_distance_km": 320.0,
                    "off_route_km": 1.2,
                    "battery_arrival_percent": 8.6,
                    "battery_departure_percent": 100.0,
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
        # מידע הסוללה בעצירה - מה שהמשתמש ביקש לראות
        self.assertIn("מגיע עם 9%", text)
        self.assertIn("טען ל-100%", text)
        self.assertIn("צפי הגעה ליעד עם כ-22%", text)
        self.assertIn('טווח אחרי טעינה ל-100%: 360 ק"מ', text)

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
