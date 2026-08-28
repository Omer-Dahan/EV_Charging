"""
מייצא את מאגר עמדות הטעינה (data/ev_stations.db) לקובץ JSON קומפקטי
עבור ה-WebApp הסטטי (webapp/stations.json).

הרצה:
    python3 webapp/export_stations.py
"""
import json
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "data" / "ev_stations.db"
OUT_PATH = Path(__file__).resolve().parent / "stations.json"

CONNECTOR_SHORT = {
    "CCS2_COMBO": "CCS2",
    "TYPE2": "Type2",
    "CHADEMO": "CHAdeMO",
}


def short_connectors(connectors_raw: str) -> list[dict]:
    try:
        connectors = json.loads(connectors_raw or "[]")
    except (json.JSONDecodeError, TypeError):
        connectors = []

    best_power: dict[str, float] = {}
    for c in connectors:
        if not isinstance(c, dict):
            continue
        standard = c.get("standard", "OTHER")
        label = CONNECTOR_SHORT.get(standard, "Other")
        power = c.get("maxPower") or 0
        try:
            power = float(power)
        except (TypeError, ValueError):
            power = 0.0
        if power > best_power.get(label, -1):
            best_power[label] = power

    return [{"t": label, "kw": int(kw)} for label, kw in best_power.items()]


def max_power(connectors_short: list[dict]) -> float:
    return max((c["kw"] for c in connectors_short), default=0)


def export() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, name, address, city, lat, lng, provider_name,
               max_per_kwh, connectors, is_gov_official
        FROM locations
        WHERE lat IS NOT NULL AND lng IS NOT NULL
        """
    ).fetchall()
    conn.close()

    stations = []
    for row in rows:
        connectors = short_connectors(row["connectors"])
        stations.append({
            "id": row["id"],
            "n": row["name"],
            "a": row["address"],
            "c": row["city"],
            "lat": round(row["lat"], 6),
            "lng": round(row["lng"], 6),
            "p": row["provider_name"] or "",
            "pr": row["max_per_kwh"],
            "mp": max_power(connectors),
            "cn": connectors,
            "g": 1 if row["is_gov_official"] == 1 else 0,
        })

    OUT_PATH.write_text(
        json.dumps(stations, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"exported {len(stations)} stations -> {OUT_PATH}")


if __name__ == "__main__":
    export()
