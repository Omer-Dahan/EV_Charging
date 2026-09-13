// Pure trip-planning logic: route distance, effective range, and charging-stop
// selection. No DOM/fetch here so it can run identically in the browser and
// under plain Node for testing (see test_trip_logic.mjs).
(function (root) {
  "use strict";

  function haversineKm(lat1, lon1, lat2, lon2) {
    var R = 6371;
    var dLat = (lat2 - lat1) * Math.PI / 180;
    var dLon = (lon2 - lon1) * Math.PI / 180;
    var a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
      Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }

  // Cumulative distance (km) at each point of a [{lat,lng}, ...] route.
  function routeCumulativeDistances(coords) {
    var cumulative = [0];
    for (var i = 1; i < coords.length; i++) {
      var d = haversineKm(coords[i - 1].lat, coords[i - 1].lng, coords[i].lat, coords[i].lng);
      cumulative.push(cumulative[i - 1] + d);
    }
    return cumulative;
  }

  // Flatten lat/lng to local km-scale x/y around a reference latitude, so
  // point-to-segment distance can be plain 2D geometry over short spans.
  function toLocalXY(lat, lng, refLat) {
    var kmPerDegLat = 110.574;
    var kmPerDegLng = 111.320 * Math.cos(refLat * Math.PI / 180);
    return { x: lng * kmPerDegLng, y: lat * kmPerDegLat };
  }

  function pointToSegmentKm(p, a, b) {
    var refLat = a.lat;
    var P = toLocalXY(p.lat, p.lng, refLat);
    var A = toLocalXY(a.lat, a.lng, refLat);
    var B = toLocalXY(b.lat, b.lng, refLat);
    var dx = B.x - A.x, dy = B.y - A.y;
    var lengthSq = dx * dx + dy * dy;
    var t = lengthSq === 0 ? 0 : ((P.x - A.x) * dx + (P.y - A.y) * dy) / lengthSq;
    t = Math.max(0, Math.min(1, t));
    var cx = A.x + t * dx, cy = A.y + t * dy;
    var ddx = P.x - cx, ddy = P.y - cy;
    return Math.sqrt(ddx * ddx + ddy * ddy);
  }

  // Spatial grid so a route with hundreds of points doesn't scan all stations
  // for every point. Buckets are degree-sized (fine enough for the radii we
  // search at, ~5-15km) rather than true km cells, which keeps this simple.
  function buildStationGrid(stations, cellKm) {
    cellKm = cellKm || 10;
    var cellDeg = cellKm / 111;
    var cells = new Map();
    for (var i = 0; i < stations.length; i++) {
      var s = stations[i];
      var key = cellKeyFor(s.lat, s.lng, cellDeg);
      var bucket = cells.get(key);
      if (!bucket) { bucket = []; cells.set(key, bucket); }
      bucket.push(i);
    }
    return { cellDeg: cellDeg, cells: cells };
  }

  function cellKeyFor(lat, lng, cellDeg) {
    return Math.floor(lng / cellDeg) + "_" + Math.floor(lat / cellDeg);
  }

  function candidateIndexesNear(grid, lat, lng, radiusKm) {
    var cellDeg = grid.cellDeg;
    var cellSpan = Math.max(1, Math.ceil((radiusKm / 111) / cellDeg));
    var gx0 = Math.floor(lng / cellDeg);
    var gy0 = Math.floor(lat / cellDeg);
    var out = [];
    for (var dx = -cellSpan; dx <= cellSpan; dx++) {
      for (var dy = -cellSpan; dy <= cellSpan; dy++) {
        var bucket = grid.cells.get((gx0 + dx) + "_" + (gy0 + dy));
        if (bucket) out.push.apply(out, bucket);
      }
    }
    return out;
  }

  function findSegmentIndexAtKm(cumulative, km) {
    for (var i = 0; i < cumulative.length; i++) {
      if (cumulative[i] >= km) return Math.max(0, i - 1);
    }
    return Math.max(0, cumulative.length - 2);
  }

  // Best charger whose route projection falls within [windowStartKm, windowEndKm],
  // trying progressively wider radii. Prefers fast chargers, then closest to the road.
  function findBestChargerInWindow(routeCoords, cumulative, windowStartKm, windowEndKm, stations, grid, radiiKm, preferMinPowerKw, usedStationIds) {
    var segStart = findSegmentIndexAtKm(cumulative, windowStartKm);
    var segEnd = Math.min(routeCoords.length - 1, Math.max(segStart + 1, findSegmentIndexAtKm(cumulative, windowEndKm) + 1));

    for (var r = 0; r < radiiKm.length; r++) {
      var radiusKm = radiiKm[r];
      var best = null;

      for (var i = segStart; i < segEnd; i++) {
        var a = routeCoords[i], b = routeCoords[i + 1];
        if (!b) continue;
        var midLat = (a.lat + b.lat) / 2, midLng = (a.lng + b.lng) / 2;
        var idxs = candidateIndexesNear(grid, midLat, midLng, radiusKm);
        for (var k = 0; k < idxs.length; k++) {
          var s = stations[idxs[k]];
          if (usedStationIds[s.id]) continue;
          var distOff = pointToSegmentKm(s, a, b);
          if (distOff > radiusKm) continue;
          var isFast = (s.mp || 0) >= preferMinPowerKw;
          var better = !best ||
            (isFast && !best.isFast) ||
            (isFast === best.isFast && distOff < best.distanceOffRouteKm);
          if (better) {
            best = { station: s, distanceOffRouteKm: distOff, distanceAlongRouteKm: cumulative[i], isFast: isFast };
          }
        }
      }

      if (best) return best;
    }
    return null;
  }

  function effectiveRangeKm(vehicle) {
    return vehicle.rangeKm * (vehicle.batteryPercent / 100) * (1 - vehicle.safetyMarginPercent / 100);
  }

  function fullEffectiveRangeKm(vehicle) {
    return vehicle.rangeKm * (1 - vehicle.safetyMarginPercent / 100);
  }

  function energyForDistanceKwh(distanceKm, consumptionKwh100km) {
    return distanceKm / 100 * consumptionKwh100km;
  }

  // Rough dwell time at a stop: how long to add enough energy for the leg
  // that follows it. Real charging curves taper well before 100%, so this
  // is deliberately a conservative average-power estimate, not a simulation.
  function estimateStopChargingMinutes(nextLegKm, consumptionKwh100km, chargerPowerKw) {
    var kwhNeeded = energyForDistanceKwh(nextLegKm, consumptionKwh100km);
    var effectivePowerKw = Math.max(1, chargerPowerKw || 50) * 0.88;
    var minutes = kwhNeeded / effectivePowerKw * 60;
    return Math.max(10, minutes);
  }

  // Main entry point. routeCoords: [{lat,lng}, ...] following the road.
  // vehicle: {rangeKm, batteryPercent, consumptionKwh100km, safetyMarginPercent}
  function planTripStops(routeCoords, stations, vehicle, options) {
    options = options || {};
    var radiiKm = options.searchRadiiKm || [5, 10, 15];
    var preferMinPowerKw = options.preferMinPowerKw || 50;

    var cumulative = routeCumulativeDistances(routeCoords);
    var totalDistanceKm = cumulative[cumulative.length - 1];
    var startRangeKm = effectiveRangeKm(vehicle);
    var rechargedRangeKm = fullEffectiveRangeKm(vehicle);

    var result = { stops: [], warnings: [], totalDistanceKm: totalDistanceKm, effectiveRangeKm: startRangeKm };

    if (totalDistanceKm <= startRangeKm) return result;

    var grid = buildStationGrid(stations, 10);
    var usedStationIds = {};
    var legStartKm = 0;
    var rangeForLeg = startRangeKm;

    while (totalDistanceKm - legStartKm > rangeForLeg) {
      var windowStartKm = legStartKm + rangeForLeg * 0.6;
      var windowEndKm = Math.min(legStartKm + rangeForLeg * 0.95, totalDistanceKm);

      var best = findBestChargerInWindow(
        routeCoords, cumulative, windowStartKm, windowEndKm,
        stations, grid, radiiKm, preferMinPowerKw, usedStationIds
      );

      if (!best) {
        result.warnings.push({ type: "no-station-found", fromKm: windowStartKm, toKm: windowEndKm });
        break;
      }

      usedStationIds[best.station.id] = true;
      result.stops.push({
        station: best.station,
        distanceFromStartKm: best.distanceAlongRouteKm,
        distanceOffRouteKm: best.distanceOffRouteKm
      });

      legStartKm = best.distanceAlongRouteKm;
      rangeForLeg = rechargedRangeKm;
    }

    return result;
  }

  var TripLogic = {
    haversineKm: haversineKm,
    routeCumulativeDistances: routeCumulativeDistances,
    pointToSegmentKm: pointToSegmentKm,
    buildStationGrid: buildStationGrid,
    candidateIndexesNear: candidateIndexesNear,
    effectiveRangeKm: effectiveRangeKm,
    fullEffectiveRangeKm: fullEffectiveRangeKm,
    energyForDistanceKwh: energyForDistanceKwh,
    estimateStopChargingMinutes: estimateStopChargingMinutes,
    planTripStops: planTripStops
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = TripLogic;
  } else {
    root.TripLogic = TripLogic;
  }
})(typeof window !== "undefined" ? window : this);
