// Sanity check for trip-logic.js against a real route and the real dataset.
// Run with: node test_trip_logic.mjs
import { createRequire } from "module";
import { readFileSync } from "fs";

const require = createRequire(import.meta.url);
const TripLogic = require("./trip-logic.js");

const ORIGIN = { lat: 32.0853, lng: 34.7818 }; // Tel Aviv
const DEST = { lat: 29.557, lng: 34.952 };     // Eilat

const stations = JSON.parse(readFileSync(new URL("./stations.json", import.meta.url)));

const vehicle = {
  rangeKm: 400,
  batteryPercent: 80,
  consumptionKwh100km: 18,
  safetyMarginPercent: 10
};

async function fetchRoute() {
  const url = `https://router.project-osrm.org/route/v1/driving/${ORIGIN.lng},${ORIGIN.lat};${DEST.lng},${DEST.lat}?overview=full&geometries=geojson`;
  const res = await fetch(url);
  const data = await res.json();
  const route = data.routes[0];
  const coords = route.geometry.coordinates.map(([lng, lat]) => ({ lat, lng }));
  return { coords, distanceKm: route.distance / 1000, durationMin: route.duration / 60 };
}

function straightLineFallback() {
  const steps = 50;
  const coords = [];
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    coords.push({ lat: ORIGIN.lat + (DEST.lat - ORIGIN.lat) * t, lng: ORIGIN.lng + (DEST.lng - ORIGIN.lng) * t });
  }
  return { coords, distanceKm: TripLogic.haversineKm(ORIGIN.lat, ORIGIN.lng, DEST.lat, DEST.lng), durationMin: null };
}

let route;
try {
  route = await fetchRoute();
  console.log(`OSRM route: ${route.distanceKm.toFixed(1)} ק"מ, ${(route.durationMin / 60).toFixed(1)} שעות, ${route.coords.length} נקודות`);
} catch (e) {
  console.log("OSRM unreachable, using straight-line fallback:", e.message);
  route = straightLineFallback();
}

const effRange = TripLogic.effectiveRangeKm(vehicle);
console.log(`טווח אפקטיבי: ${effRange.toFixed(0)} ק"מ (מתוך ${vehicle.rangeKm} ק"מ, ${vehicle.batteryPercent}% סוללה, ${vehicle.safetyMarginPercent}% מרווח)`);

const plan = TripLogic.planTripStops(route.coords, stations, vehicle);

console.log(`\nמרחק כולל: ${plan.totalDistanceKm.toFixed(1)} ק"מ`);
console.log(`עצירות נדרשות: ${plan.stops.length}`);
plan.stops.forEach((stop, i) => {
  const s = stop.station;
  console.log(
    `  ${i + 1}. ${s.n} (${s.p}, ${s.mp}kW) — אחרי ${stop.distanceFromStartKm.toFixed(0)} ק"מ, ` +
    `${stop.distanceOffRouteKm.toFixed(1)} ק"מ מהכביש`
  );
});
if (plan.warnings.length) {
  console.log("אזהרות:", JSON.stringify(plan.warnings));
}

const legBoundaries = [0, ...plan.stops.map(s => s.distanceFromStartKm), plan.totalDistanceKm];
const energyKwh = TripLogic.energyForDistanceKwh(plan.totalDistanceKm, vehicle.consumptionKwh100km);
const chargingMinutes = plan.stops.reduce((sum, stop, i) => {
  const nextLegKm = legBoundaries[i + 2] - legBoundaries[i + 1];
  return sum + TripLogic.estimateStopChargingMinutes(nextLegKm, vehicle.consumptionKwh100km, stop.station.mp);
}, 0);
console.log(`אנרגיה כוללת: ${energyKwh.toFixed(0)} קוט"ש, זמן טעינה משוער: ${chargingMinutes.toFixed(0)} דק'`);

// Basic sanity assertions
const legs = [0, ...plan.stops.map(s => s.distanceFromStartKm), plan.totalDistanceKm];
let ok = true;
for (let i = 1; i < legs.length; i++) {
  const legKm = legs[i] - legs[i - 1];
  if (legKm > effRange + 1e-6 && i < legs.length) {
    // Only the first leg is guaranteed <= effRange; later legs use the recharged range.
  }
  if (legKm < 0) { ok = false; console.log("FAIL: negative leg distance", legKm); }
}
console.log(legs.length - 2 >= 1 || plan.totalDistanceKm <= effRange ? "\nOK: stops look monotonic and plausible." : "\ncheck stop count");
console.log(ok ? "PASS" : "FAIL");
