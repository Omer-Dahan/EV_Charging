import json
from typing import Optional

from bot.services.station_search import get_station_max_power

CONNECTOR_DISPLAY = {
    "CCS2_COMBO": "⚡ CCS2 (DC)",
    "TYPE2": "🔌 Type 2 (AC)",
    "CHADEMO": "🇯🇵 CHAdeMO",
    "OTHER": "🔌 שקע אחר",
}


def _connectors_block(connectors_raw) -> str:
    if isinstance(connectors_raw, list):
        connectors = connectors_raw
    elif isinstance(connectors_raw, str):
        try:
            connectors = json.loads(connectors_raw or "[]")
        except (json.JSONDecodeError, TypeError):
            connectors = []
    else:
        connectors = []
    if not connectors:
        return "לא צוין"
    parts = []
    for c in connectors:
        standard = c.get("standard", "OTHER")
        display = CONNECTOR_DISPLAY.get(standard, CONNECTOR_DISPLAY["OTHER"])
        power = c.get("maxPower")
        if power is not None:
            parts.append(f"{display} {int(power)}kW")
        else:
            parts.append(display)
    return " | ".join(parts)


def _price_block(max_per_kwh) -> str:
    if max_per_kwh is not None:
        return f'עד {max_per_kwh:.2f} ₪ לקוט"ש'
    return "לא צוין"


def _status_block(status_summary_json: str) -> str:
    try:
        status_summary = json.loads(status_summary_json or "{}")
    except (json.JSONDecodeError, TypeError):
        status_summary = {}
    if not status_summary:
        return ""
    total = sum(status_summary.values())
    available = status_summary.get("AVAILABLE", 0)
    busy = status_summary.get("BUSY", 0)
    return f'🟢 פנויות: {available} | 🔴 תפוסות: {busy} | סה"כ: {total}'


def _gov_badge(is_gov_official) -> str:
    if is_gov_official == 1:
        return "🏛️ מאומתת במאגר משרד האנרגיה"
    return ""


def format_station_card(
    station: dict,
    distance_km: float,
    idx: int,
    total: int,
    radius_km: int,
    location_name: Optional[str] = None,
) -> str:
    """idx: 1-based index of current station within results."""
    name = station.get("name") or "עמדת טעינה"
    address_parts = [p for p in [station.get("address"), station.get("city")] if p]
    address = ", ".join(address_parts) if address_parts else ""
    provider = station.get("provider_name") or "לא צוין"

    connectors_block = _connectors_block(station.get("connectors"))
    price_block = _price_block(station.get("max_per_kwh"))
    status_block = _status_block(station.get("status_summary"))
    gov_badge = _gov_badge(station.get("is_gov_official"))

    header = f'⚡ עמדה {idx}/{total} | רדיוס {radius_km} ק"מ'
    if location_name:
        header = f"📍 <b>חיפוש סביב:</b> {location_name}\n" + header

    lines = [
        header,
        "",
        f"🏢 <b>{name}</b>",
    ]
    if address:
        lines.append(f"📍 {address}")
    lines.extend([
        f'📏 מרחק: {distance_km:.1f} ק"מ',
        f"🏭 מפעיל: {provider}",
        "",
        f"🔌 מחברים: {connectors_block}",
        "",
        f"💰 מחיר: {price_block}",
    ])
    if status_block:
        lines.append("")
        lines.append(status_block)
    if gov_badge:
        lines.append("")
        lines.append(gov_badge)
    return "\n".join(lines)


def format_trip_plan(plan: dict, origin_name: str, dest_name: str) -> str:
    """מעצב כרטיסיית תוכנית נסיעה (מרחק, זמן, עצירות טעינה) מתוך dict של trip_planner.plan_trip."""
    total_km = plan["total_distance_km"]
    hours = plan["duration_hours"]
    h = int(hours)
    m = round((hours - h) * 60)
    if m == 60:
        h += 1
        m = 0
    num_stops = plan["num_stops"]

    lines = [
        "🚗 <b>תכנון נסיעה</b>",
        f"📍 <b>מ:</b> {origin_name}",
        f"🏁 <b>אל:</b> {dest_name}",
        "",
        f'📏 מרחק (קו אווירי): {total_km:.0f} ק"מ',
        f"⏱️ זמן נסיעה משוער: {h} שע׳ {m} דק׳ (ללא זמני טעינה)",
        f"🔋 עצירות טעינה נדרשות: {num_stops}",
        "",
    ]

    if num_stops == 0:
        lines.append("✅ טווח הסוללה מספיק להגעה ישירה, ללא עצירת טעינה.")
    else:
        for stop in plan["stops"]:
            station = stop["station"]
            idx = stop["segment_index"]
            dist = stop["distance_from_origin_km"]
            name = station.get("name") or "עמדת טעינה"
            provider = station.get("provider_name") or "לא צוין"
            max_power = station.get("max_power")
            if max_power is None:
                max_power = get_station_max_power(station.get("connectors"))
            price_block = _price_block(station.get("max_per_kwh"))
            lines.append(f'🔌 <b>עצירה {idx}</b> — אחרי כ-{dist:.0f} ק"מ:')
            lines.append(f"🏢 {name} ({provider}, {max_power:.0f}kW)")
            lines.append(f"💰 {price_block}")
            lines.append("")

        for missing in plan.get("missing_segments", []):
            lines.append(
                f'⚠️ לא נמצאה עמדת טעינה מתאימה בקטע שאחרי כ-{missing["distance_km"]:.0f} ק"מ מהמוצא.'
            )
        if plan.get("missing_segments"):
            lines.append("")

    lines.append(
        'ℹ️ הנחות: צריכה 18kWh/100 ק"מ, טווח סוללה 400 ק"מ. '
        "המרחק והזמן מבוססים על קו אווירי ולא מסלול כביש בפועל."
    )
    return "\n".join(lines)
