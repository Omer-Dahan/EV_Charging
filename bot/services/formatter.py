import json
from typing import Optional

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
