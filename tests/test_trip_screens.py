"""בדיקות למסכי זרימת הנסיעה (bot/handlers/trip_screens.py).

כל מסך בזרימה הוא פונקציה טהורה שמחזירה (טקסט, כפתורים), ולכן אפשר לבדוק כאן בלי
טלגרם את מה שהמשתמש ביקש: כל מסך מציג כפתורי המשך, בלי מקלדת תשובה ובלי מבוי סתום.
"""
import unittest

from telethon.tl.types import KeyboardButtonCallback, KeyboardButtonUrl

from bot.handlers import trip_screens as screens
from bot.keyboards.inline import trip_settings_main_keyboard

SAMPLE_PLAN = {
    "total_distance_km": 330.0,
    "straight_line_km": 264.0,
    "duration_hours": 3.6,
    "num_stops": 1,
    "available_range_km": 245.0,
    "recharged_range_km": 315.0,
    "arrival_battery_percent": 65.0,
    "route_source": "osrm",
    "origin": {"lat": 32.0853, "lng": 34.7818},
    "destination": {"lat": 29.557, "lng": 34.952},
    "car_params": {
        "real_range_km": 350.0, "battery_percent": 80.0,
        "safety_margin_percent": 10.0, "consumption_kwh_per_100km": 18.0,
        "min_power_kw": None,
    },
    "stops": [
        {
            "segment_index": 1,
            "distance_from_origin_km": 208.0,
            "leg_distance_km": 208.0,
            "off_route_km": 2.0,
            "battery_arrival_percent": 21.0,
            "battery_departure_percent": 100.0,
            "station": {
                "id": 1, "name": "מתחם אלון בירוחם", "lat": 31.0, "lng": 35.0,
                "max_power": 150.0, "provider_name": "EVI", "max_per_kwh": 1.8,
            },
            "relaxation": {"providers": False, "price": False, "power_kw": 150.0},
        }
    ],
    "missing_segments": [],
}

SAMPLE_CANDIDATES = [
    {"lat": 32.08, "lng": 34.78, "name": "תל אביב-יפו"},
    {"lat": 32.09, "lng": 34.80, "name": "תל אביב, הצפון הישן"},
]

SAMPLE_SAVED_PLANS = [
    {"id": 7, "created_at": "2026-09-01 08:00:00", "destination_name": "אילת", "total_distance_km": 330.0},
    {"id": 8, "created_at": "2026-09-05 10:00:00", "destination_name": "חיפה", "total_distance_km": 95.0},
]

# (שם המסך, הפונקציה, ארגומנטים) - כולל את כל המסכים שהזרימה יכולה להגיע אליהם.
ALL_SCREENS = [
    ("ask_destination", screens.render_ask_destination, ()),
    ("ask_origin_private", screens.render_ask_origin, ("אילת", True)),
    ("ask_origin_group", screens.render_ask_origin, ("אילת", False)),
    ("ask_battery", screens.render_ask_battery, (None,)),
    ("ask_battery_with_error", screens.render_ask_battery, ("❌ שגיאה",)),
    ("geocode_choice", screens.render_geocode_choice, ("תל אביב", SAMPLE_CANDIDATES)),
    ("planning", screens.render_planning, ()),
    ("missing_city", screens.render_missing_city, ()),
    ("no_geocode_results", screens.render_no_geocode_results, ("בלה בלה",)),
    ("outside_israel", screens.render_outside_israel, ()),
    ("low_battery", screens.render_low_battery, (10.0, 80.0)),
    ("expired", screens.render_expired, ()),
    ("generic_error", screens.render_generic_error, ()),
    ("plan_not_found", screens.render_plan_not_found, ()),
    ("no_plans", screens.render_no_plans, ()),
    ("plans_list", screens.render_plans_list, (SAMPLE_SAVED_PLANS,)),
    ("plan", screens.render_plan, (SAMPLE_PLAN, "תל אביב", "אילת", 7)),
    ("plan_details", screens.render_plan_details, (SAMPLE_PLAN, "תל אביב", "אילת", 7)),
]

# מסכים שאינם שלב בזרימה אלא סופה - שם אין "ביטול", יש התחלה מחדש.
TERMINAL_SCREENS = {"plan", "plan_details", "plans_list", "no_plans", "expired", "plan_not_found"}


def _flatten(buttons) -> list:
    return [btn for row in buttons for btn in row]


class TestEveryScreenIsButtonDriven(unittest.TestCase):
    def test_screens_return_text_and_buttons(self):
        for name, render, args in ALL_SCREENS:
            with self.subTest(screen=name):
                text, buttons = render(*args)
                self.assertTrue(text.strip(), "מסך בלי טקסט")
                self.assertTrue(buttons, "מסך בלי כפתורים - המשתמש נתקע")

    def test_no_reply_keyboard_buttons_anywhere(self):
        """מקלדת תשובה (בקשת מיקום) היא מה שאילץ הודעה חדשה באמצע הזרימה."""
        for name, render, args in ALL_SCREENS:
            with self.subTest(screen=name):
                for btn in _flatten(render(*args)[1]):
                    self.assertIsInstance(btn, (KeyboardButtonCallback, KeyboardButtonUrl))

    def test_every_screen_has_a_trip_callback(self):
        for name, render, args in ALL_SCREENS:
            with self.subTest(screen=name):
                data = [b.data for b in _flatten(render(*args)[1]) if isinstance(b, KeyboardButtonCallback)]
                self.assertTrue(
                    any(d.startswith((b"trip:", b"tripbatt:", b"tripgeo:")) for d in data),
                    f"למסך {name} אין דרך לחזור לזרימה",
                )

    def test_mid_flow_screens_offer_cancel(self):
        for name, render, args in ALL_SCREENS:
            if name in TERMINAL_SCREENS:
                continue
            with self.subTest(screen=name):
                data = [b.data for b in _flatten(render(*args)[1]) if isinstance(b, KeyboardButtonCallback)]
                self.assertIn(b"trip:cancel", data)


class TestDestinationScreen(unittest.TestCase):
    def test_cancel_is_a_button_not_a_typed_word(self):
        text, buttons = screens.render_ask_destination()
        self.assertNotIn("ביטול", text)
        self.assertIn(b"trip:cancel", [b.data for b in _flatten(buttons)])


class TestOriginScreen(unittest.TestCase):
    def test_gps_button_only_offered_in_private_chat(self):
        _, private_buttons = screens.render_ask_origin("אילת", True)
        self.assertIn(b"trip:gps", [b.data for b in _flatten(private_buttons)])

        _, group_buttons = screens.render_ask_origin("אילת", False)
        self.assertNotIn(b"trip:gps", [b.data for b in _flatten(group_buttons)])


class TestBatteryScreen(unittest.TestCase):
    def test_error_line_keeps_the_full_keyboard(self):
        text, buttons = screens.render_ask_battery("❌ יש להזין מספר בין 1 ל-100")
        self.assertIn("❌ יש להזין מספר בין 1 ל-100", text)
        data = [b.data for b in _flatten(buttons)]
        for percent in (20, 50, 80, 100):
            self.assertIn(f"tripbatt:set:{percent}".encode(), data)

    def test_no_default_button_is_ever_offered(self):
        """האחוז משתנה בכל נסיעה - המסך תמיד שואל מחדש, בלי הצעת ברירת מחדל."""
        _, buttons = screens.render_ask_battery(None)
        self.assertNotIn(b"tripbatt:default", [b.data for b in _flatten(buttons)])


class TestSettingsReturnPath(unittest.TestCase):
    def test_back_button_returns_to_the_flow_when_one_is_open(self):
        in_flow = [b.data for row in trip_settings_main_keyboard(in_trip_flow=True) for b in row]
        self.assertIn(b"trip:resume", in_flow)

        standalone = [b.data for row in trip_settings_main_keyboard(in_trip_flow=False) for b in row]
        self.assertIn(b"settings:main", standalone)
        self.assertNotIn(b"trip:resume", standalone)

    def test_battery_percent_is_not_a_saved_setting(self):
        """האחוז משתנה בכל נסיעה - אין הגדרה קבועה בשבילו, רק שאלה בכל תכנון."""
        buttons = trip_settings_main_keyboard()
        texts = [b.text for row in buttons for b in row]
        datas = [b.data for row in buttons for b in row]
        self.assertFalse(any("סוללה" in text for text in texts))
        self.assertNotIn(b"settings:trip:battery", datas)


class TestPlanScreen(unittest.TestCase):
    def test_summary_is_short_and_lists_every_stop(self):
        text, buttons = screens.render_plan(SAMPLE_PLAN, "תל אביב", "אילת", 7)
        self.assertIn("🔋 מגיע עם 21% · טען ל-100%", text)
        self.assertIn("להגיע ליעד עם כ-65%", text)
        self.assertIn("מתחם אלון בירוחם", text)
        self.assertIn("אילת", text)
        # התקציר נועד להיקרא במבט אחד לצד המפה, לא להיות מגילה.
        self.assertLess(len(text), 900)

        data = [b.data for b in _flatten(buttons) if isinstance(b, KeyboardButtonCallback)]
        self.assertIn(b"trip:details:7", data)

    def test_waze_link_per_stop(self):
        _, buttons = screens.render_plan(SAMPLE_PLAN, "תל אביב", "אילת", None)
        urls = [b.url for b in _flatten(buttons) if isinstance(b, KeyboardButtonUrl)]
        self.assertEqual(len(urls), 1)
        self.assertIn("31.0,35.0", urls[0])

    def test_details_screen_carries_the_full_plan_text(self):
        text, _ = screens.render_plan_details(SAMPLE_PLAN, "תל אביב", "אילת", 7)
        self.assertIn("פרמטרי הרכב", text)


if __name__ == "__main__":
    unittest.main()
