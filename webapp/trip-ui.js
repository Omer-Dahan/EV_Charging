// Trip planner UI. Fully independent of the Telegram bot: it only talks to
// Nominatim (geocoding) and OSRM (routing), both free public services, and
// reuses the existing map instance + station list via window.EVMap.
(function () {
  "use strict";

  var EVMap = window.EVMap;
  var TripLogic = window.TripLogic;
  if (!EVMap || !TripLogic) {
    console.error("trip-ui.js: EVMap or TripLogic not available");
    return;
  }

  var map = EVMap.map;
  var icon = EVMap.icon;
  var escapeHtml = EVMap.escapeHtml;
  var connectorsText = EVMap.connectorsText;
  var priceText = EVMap.priceText;

  var VEHICLE_KEY = "ev-trip-vehicle-v1";
  var TRIPS_KEY = "ev-trip-saved-v1";
  var DEFAULT_VEHICLE = { rangeKm: 400, consumptionKwh100km: 18, safetyMarginPercent: 10 };
  var DEFAULT_TRIP_BATTERY_PERCENT = 80; // display-only starting point; never persisted, asked on every trip
  var MAX_SAVED_TRIPS = 5;

  var $ = function (id) { return document.getElementById(id); };

  var tabMap = $("tab-map"), tabTrip = $("tab-trip");
  var toolbar = $("toolbar"), tripPanel = $("trip-panel"), listPanel = $("list-panel");
  var originInput = $("trip-origin-input"), destInput = $("trip-dest-input");
  var originSuggest = $("trip-origin-suggest"), destSuggest = $("trip-dest-suggest");
  var swapBtn = $("trip-swap-btn");
  var pickBanner = $("map-pick-banner"), pickText = $("map-pick-text"), pickCancel = $("map-pick-cancel");
  var settingsToggle = $("trip-settings-toggle"), settingsPanel = $("trip-settings");
  var rangeInput = $("trip-range"), consumptionInput = $("trip-consumption"), marginInput = $("trip-margin");
  var batterySlider = $("trip-battery-slider"), batteryValueEl = $("trip-battery-value");
  var calcBtn = $("trip-calc-btn"), savedBtn = $("trip-saved-btn"), fitBtn = $("trip-fit-btn");
  var statusEl = $("trip-status");
  var summaryEl = $("trip-summary"), summaryStatsEl = $("trip-summary-stats");
  var stopsListEl = $("trip-stops-list");
  var savedPanel = $("saved-trips-panel"), savedClose = $("saved-trips-close"), savedList = $("saved-trips-list"), savedEmpty = $("saved-trips-empty");

  var tripState = { origin: null, destination: null };
  var pickTarget = null;

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  // ---------- vehicle settings ----------

  function loadVehicle() {
    var stored = {};
    try { stored = JSON.parse(localStorage.getItem(VEHICLE_KEY)) || {}; } catch (e) { stored = {}; }
    // Migration: battery percent used to be a saved vehicle setting, but it
    // changes every trip, so any previously stored value is dropped here.
    if (Object.prototype.hasOwnProperty.call(stored, "batteryPercent")) {
      delete stored.batteryPercent;
      try { localStorage.setItem(VEHICLE_KEY, JSON.stringify(stored)); } catch (e) { /* ignore */ }
    }
    var v = Object.assign({}, DEFAULT_VEHICLE, stored);
    rangeInput.value = v.rangeKm;
    consumptionInput.value = v.consumptionKwh100km;
    marginInput.value = v.safetyMarginPercent;
  }

  function readVehicleInputs() {
    var v = {
      rangeKm: clamp(parseFloat(rangeInput.value) || DEFAULT_VEHICLE.rangeKm, 50, 1000),
      consumptionKwh100km: clamp(parseFloat(consumptionInput.value) || DEFAULT_VEHICLE.consumptionKwh100km, 5, 40),
      safetyMarginPercent: clamp(parseFloat(marginInput.value) || DEFAULT_VEHICLE.safetyMarginPercent, 0, 50),
    };
    try { localStorage.setItem(VEHICLE_KEY, JSON.stringify(v)); } catch (e) { /* storage unavailable, ignore */ }
    return v;
  }

  function setBatteryDisplay(percent) {
    batteryValueEl.textContent = Math.round(percent) + "%";
    batterySlider.style.setProperty("--fill", percent + "%");
  }

  function readBatteryPercent() {
    var percent = clamp(parseFloat(batterySlider.value) || DEFAULT_TRIP_BATTERY_PERCENT, 1, 100);
    setBatteryDisplay(percent);
    return percent;
  }

  function clamp(n, min, max) { return Math.max(min, Math.min(max, n)); }

  loadVehicle();
  [rangeInput, consumptionInput, marginInput].forEach(function (input) {
    input.addEventListener("change", readVehicleInputs);
  });

  batterySlider.value = DEFAULT_TRIP_BATTERY_PERCENT;
  setBatteryDisplay(DEFAULT_TRIP_BATTERY_PERCENT);
  batterySlider.addEventListener("input", readBatteryPercent);

  settingsToggle.addEventListener("click", function () {
    var expanded = settingsToggle.getAttribute("aria-expanded") === "true";
    settingsToggle.setAttribute("aria-expanded", String(!expanded));
    settingsPanel.classList.toggle("hidden", expanded);
  });

  // ---------- tab switching ----------

  function showMapTab() {
    tabMap.classList.add("is-active"); tabMap.setAttribute("aria-selected", "true");
    tabTrip.classList.remove("is-active"); tabTrip.setAttribute("aria-selected", "false");
    toolbar.classList.remove("hidden");
    tripPanel.classList.add("hidden");
    cancelPick();
    savedPanel.classList.add("hidden");
    setTimeout(function () { map.invalidateSize(); }, 300);
  }

  function showTripTab() {
    tabTrip.classList.add("is-active"); tabTrip.setAttribute("aria-selected", "true");
    tabMap.classList.remove("is-active"); tabMap.setAttribute("aria-selected", "false");
    toolbar.classList.add("hidden");
    listPanel.classList.add("hidden");
    tripPanel.classList.remove("hidden");
    setTimeout(function () { map.invalidateSize(); }, 300);
  }

  tabMap.addEventListener("click", showMapTab);
  tabTrip.addEventListener("click", showTripTab);

  // ---------- geocoding (Nominatim) ----------

  function debounce(fn, wait) {
    var timer;
    return function () {
      var args = arguments, ctx = this;
      clearTimeout(timer);
      timer = setTimeout(function () { fn.apply(ctx, args); }, wait);
    };
  }

  function searchPlaces(query, signal) {
    var url = "https://nominatim.openstreetmap.org/search?format=json&limit=6&countrycodes=il&accept-language=he&q=" + encodeURIComponent(query);
    return fetch(url, { signal: signal }).then(function (res) {
      if (!res.ok) throw new Error("geocode request failed");
      return res.json();
    });
  }

  function reverseGeocode(lat, lng) {
    var url = "https://nominatim.openstreetmap.org/reverse?format=json&accept-language=he&lat=" + lat + "&lon=" + lng + "&zoom=16";
    return fetch(url).then(function (res) {
      if (!res.ok) throw new Error("reverse geocode failed");
      return res.json();
    }).then(function (data) { return data.display_name || null; });
  }

  function setupLocationField(inputEl, suggestEl, onSelect) {
    inputEl.setAttribute("role", "combobox");
    inputEl.setAttribute("aria-autocomplete", "list");
    inputEl.setAttribute("aria-expanded", "false");
    inputEl.setAttribute("aria-owns", suggestEl.id);
    var controller = null;
    var results = [];
    var highlighted = -1;

    function setSuggestVisible(visible) {
      suggestEl.classList.toggle("hidden", !visible);
      inputEl.setAttribute("aria-expanded", String(visible));
      if (!visible) inputEl.removeAttribute("aria-activedescendant");
    }

    function renderResults() {
      suggestEl.innerHTML = "";
      if (!results.length) {
        setSuggestVisible(false);
        return;
      }
      results.forEach(function (r, i) {
        var opt = document.createElement("div");
        var optId = inputEl.id + "-opt-" + i;
        opt.id = optId;
        opt.className = "trip-suggest-option" + (i === highlighted ? " is-highlighted" : "");
        opt.setAttribute("role", "option");
        opt.setAttribute("aria-selected", i === highlighted ? "true" : "false");
        opt.setAttribute("data-index", String(i));
        opt.innerHTML = icon("map-pin") + "<span>" + escapeHtml(r.display_name) + "</span>";
        opt.addEventListener("click", function () { pick(i); });
        suggestEl.appendChild(opt);
      });
      if (highlighted >= 0) inputEl.setAttribute("aria-activedescendant", inputEl.id + "-opt-" + highlighted);
      else inputEl.removeAttribute("aria-activedescendant");
      setSuggestVisible(true);
    }

    function pick(i) {
      var r = results[i];
      if (!r) return;
      var point = { lat: parseFloat(r.lat), lng: parseFloat(r.lon), label: r.display_name };
      inputEl.value = r.display_name;
      results = [];
      highlighted = -1;
      setSuggestVisible(false);
      onSelect(point);
    }

    var runSearch = debounce(function (query) {
      if (controller) controller.abort();
      controller = new AbortController();
      suggestEl.innerHTML = '<div class="trip-suggest-loading">מחפש&hellip;</div>';
      setSuggestVisible(true);
      searchPlaces(query, controller.signal).then(function (data) {
        results = data || [];
        highlighted = -1;
        if (!results.length) {
          suggestEl.innerHTML = '<div class="trip-suggest-empty">לא נמצאו תוצאות</div>';
          setSuggestVisible(true);
          return;
        }
        renderResults();
      }).catch(function (e) {
        if (e.name === "AbortError") return;
        suggestEl.innerHTML = '<div class="trip-suggest-empty">שגיאה בחיפוש</div>';
      });
    }, 380);

    inputEl.addEventListener("input", function () {
      onSelect(null);
      var query = inputEl.value.trim();
      if (query.length < 2) {
        results = [];
        setSuggestVisible(false);
        return;
      }
      runSearch(query);
    });

    inputEl.addEventListener("keydown", function (e) {
      if (suggestEl.classList.contains("hidden") || !results.length) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        highlighted = Math.min(results.length - 1, highlighted + 1);
        renderResults();
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        highlighted = Math.max(0, highlighted - 1);
        renderResults();
      } else if (e.key === "Enter") {
        e.preventDefault();
        pick(highlighted >= 0 ? highlighted : 0);
      } else if (e.key === "Escape") {
        setSuggestVisible(false);
      }
    });

    document.addEventListener("click", function (e) {
      if (!inputEl.parentElement.contains(e.target)) setSuggestVisible(false);
    });

    return {
      setPoint: function (point) {
        inputEl.value = point ? point.label : "";
      },
    };
  }

  var originField = setupLocationField(originInput, originSuggest, function (point) { tripState.origin = point; });
  var destField = setupLocationField(destInput, destSuggest, function (point) { tripState.destination = point; });

  // ---------- pick-on-map ----------

  function startPick(target) {
    pickTarget = target;
    pickText.textContent = target === "origin" ? "לחצו על המפה לבחירת מוצא" : "לחצו על המפה לבחירת יעד";
    pickBanner.classList.remove("hidden");
    map.getContainer().style.cursor = "crosshair";
    document.querySelectorAll(".trip-pick-btn").forEach(function (b) {
      b.classList.toggle("is-active", b.getAttribute("data-target") === target);
    });
  }

  function cancelPick() {
    pickTarget = null;
    pickBanner.classList.add("hidden");
    map.getContainer().style.cursor = "";
    document.querySelectorAll(".trip-pick-btn").forEach(function (b) { b.classList.remove("is-active"); });
  }

  document.querySelectorAll(".trip-pick-btn").forEach(function (btn) {
    btn.addEventListener("click", function () { startPick(btn.getAttribute("data-target")); });
  });
  pickCancel.addEventListener("click", cancelPick);

  map.on("click", function (e) {
    if (!pickTarget) return;
    var target = pickTarget;
    var point = { lat: e.latlng.lat, lng: e.latlng.lng, label: null };
    cancelPick();
    if (target === "origin") { tripState.origin = point; originField.setPoint({ lat: point.lat, lng: point.lng, label: "מיקום שנבחר במפה" }); }
    else { tripState.destination = point; destField.setPoint({ lat: point.lat, lng: point.lng, label: "מיקום שנבחר במפה" }); }

    reverseGeocode(point.lat, point.lng).then(function (label) {
      if (!label) return;
      point.label = label;
      if (target === "origin") originField.setPoint(point); else destField.setPoint(point);
    }).catch(function () { /* keep the generic label */ });
  });

  // ---------- swap ----------

  swapBtn.addEventListener("click", function () {
    var o = tripState.origin, d = tripState.destination;
    tripState.origin = d; tripState.destination = o;
    originField.setPoint(d); destField.setPoint(o);
  });

  // ---------- status helper ----------

  function setStatus(message, state) {
    if (!message) {
      statusEl.classList.add("hidden");
      statusEl.removeAttribute("data-state");
      return;
    }
    statusEl.textContent = message;
    statusEl.classList.remove("hidden");
    if (state) statusEl.setAttribute("data-state", state); else statusEl.removeAttribute("data-state");
  }

  // ---------- routing ----------

  function fetchOsrmRoute(origin, destination) {
    var url = "https://router.project-osrm.org/route/v1/driving/" +
      origin.lng + "," + origin.lat + ";" + destination.lng + "," + destination.lat +
      "?overview=full&geometries=geojson";
    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, 9000);
    return fetch(url, { signal: controller.signal }).then(function (res) {
      clearTimeout(timer);
      if (!res.ok) throw new Error("OSRM request failed");
      return res.json();
    }).then(function (data) {
      if (data.code !== "Ok" || !data.routes || !data.routes.length) throw new Error("OSRM returned no route");
      var route = data.routes[0];
      return {
        coords: route.geometry.coordinates.map(function (c) { return { lat: c[1], lng: c[0] }; }),
        distanceKm: route.distance / 1000,
        durationMin: route.duration / 60,
        isFallback: false,
      };
    });
  }

  function straightLineRoute(origin, destination) {
    var steps = 60;
    var coords = [];
    for (var i = 0; i <= steps; i++) {
      var t = i / steps;
      coords.push({ lat: origin.lat + (destination.lat - origin.lat) * t, lng: origin.lng + (destination.lng - origin.lng) * t });
    }
    var distanceKm = TripLogic.haversineKm(origin.lat, origin.lng, destination.lat, destination.lng);
    return { coords: coords, distanceKm: distanceKm, durationMin: distanceKm / 80 * 60, isFallback: true };
  }

  function formatDuration(totalMinutes) {
    var m = Math.round(totalMinutes);
    var h = Math.floor(m / 60), mm = m % 60;
    if (h <= 0) return mm + ' דק׳';
    return h + ' שע׳' + (mm ? " " + mm + ' דק׳' : "");
  }

  // ---------- map rendering ----------

  var tripLayer = L.layerGroup().addTo(map);
  var lastResult = null;

  function stopIconHtml(index) {
    return '<div class="trip-marker-stop"><span>' + (index + 1) + "</span></div>";
  }

  function renderTripOnMap(route, plan, origin, destination) {
    tripLayer.clearLayers();

    var latlngs = route.coords.map(function (c) { return [c.lat, c.lng]; });
    L.polyline(latlngs, { color: cssVar("--trip-route-casing"), weight: 8, opacity: 1, lineCap: "round", lineJoin: "round" }).addTo(tripLayer);
    L.polyline(latlngs, { color: cssVar("--trip-route"), weight: 4.5, opacity: 1, lineCap: "round", lineJoin: "round" }).addTo(tripLayer);

    var originIcon = L.divIcon({ className: "", html: '<div class="trip-marker-origin">' + icon("map-pin") + "</div>", iconSize: [22, 22], iconAnchor: [11, 11] });
    var destIcon = L.divIcon({ className: "", html: '<div class="trip-marker-destination">' + icon("map-pin") + "</div>", iconSize: [22, 22], iconAnchor: [11, 11] });
    L.marker([origin.lat, origin.lng], { icon: originIcon }).addTo(tripLayer).bindPopup(escapeHtml(origin.label || "מוצא"));
    L.marker([destination.lat, destination.lng], { icon: destIcon }).addTo(tripLayer).bindPopup(escapeHtml(destination.label || "יעד"));

    plan.stops.forEach(function (stop, i) {
      var s = stop.station;
      var divIcon = L.divIcon({ className: "", html: stopIconHtml(i), iconSize: [28, 28], iconAnchor: [14, 24], popupAnchor: [0, -20] });
      var marker = L.marker([s.lat, s.lng], { icon: divIcon }).addTo(tripLayer);
      marker.bindPopup(buildStopPopupHtml(s, i, stop.distanceFromStartKm), { maxWidth: 260 });
    });
  }

  function buildStopPopupHtml(s, index, distanceFromStartKm) {
    var wazeUrl = "https://waze.com/ul?ll=" + s.lat + "," + s.lng + "&navigate=yes";
    var gmapUrl = "https://www.google.com/maps/dir/?api=1&destination=" + s.lat + "," + s.lng;
    var html = '<div class="popup-header"><div class="popup-icon">' + icon("zap") + "</div>" +
      '<div class="popup-name">' + (index + 1) + ". " + escapeHtml(s.n || "עמדת טעינה") + "</div></div>";
    if (s.p) html += '<div class="popup-line">' + icon("building-2") + "<span>" + escapeHtml(s.p) + "</span></div>";
    html += '<div class="popup-line">' + icon("plug") + "<span>" + connectorsText(s.cn) + "</span></div>";
    html += '<div class="popup-line">' + icon("banknote") + "<span>" + priceText(s.pr) + "</span></div>";
    html += '<div class="popup-after-distance">אחרי ' + Math.round(distanceFromStartKm).toLocaleString("he-IL") + ' ק"מ מהמוצא</div>';
    html += '<div class="popup-actions">' +
      '<a class="primary" href="' + wazeUrl + '" target="_blank" rel="noopener">' + icon("car") + "<span>Waze</span></a>" +
      '<a class="secondary" href="' + gmapUrl + '" target="_blank" rel="noopener">' + icon("map") + "<span>Google Maps</span></a>" +
      "</div>";
    return html;
  }

  function renderSummary(route, plan, vehicle) {
    var legBoundaries = [0].concat(plan.stops.map(function (s) { return s.distanceFromStartKm; })).concat([plan.totalDistanceKm]);
    var chargingMinutes = 0;
    plan.stops.forEach(function (stop, i) {
      var nextLegKm = legBoundaries[i + 2] - legBoundaries[i + 1];
      chargingMinutes += TripLogic.estimateStopChargingMinutes(nextLegKm, vehicle.consumptionKwh100km, stop.station.mp);
    });
    var energyKwh = TripLogic.energyForDistanceKwh(plan.totalDistanceKm, vehicle.consumptionKwh100km);

    var stats = [
      { value: Math.round(plan.totalDistanceKm).toLocaleString("he-IL") + ' ק"מ', label: "מרחק" },
      { value: formatDuration(route.durationMin), label: "זמן נהיגה" },
      { value: String(plan.stops.length), label: "עצירות טעינה" },
      { value: Math.round(energyKwh).toLocaleString("he-IL") + ' קוט"ש', label: "אנרגיה" },
    ];
    summaryStatsEl.innerHTML = stats.map(function (s) {
      return '<div class="trip-stat"><div class="trip-stat-value">' + s.value + '</div><div class="trip-stat-label">' + s.label + "</div></div>";
    }).join("");

    var extra = summaryEl.querySelector(".trip-summary-extra");
    if (!extra) {
      extra = document.createElement("div");
      extra.className = "trip-summary-extra";
      extra.style.cssText = "font-size:12px;color:var(--text-secondary);margin:-4px 0 10px;";
      summaryEl.insertBefore(extra, summaryEl.querySelector("#trip-fit-btn"));
    }
    var totalWithCharging = route.durationMin + chargingMinutes;
    extra.textContent = plan.stops.length
      ? "כולל זמן טעינה משוער: כ-" + formatDuration(chargingMinutes) + " · סה\"כ עם נסיעה: כ-" + formatDuration(totalWithCharging)
      : "אין צורך בעצירות טעינה בטווח הנוכחי";

    var warningsHost = summaryEl.querySelector(".trip-warnings");
    if (warningsHost) warningsHost.remove();
    if (plan.warnings.length || route.isFallback) {
      warningsHost = document.createElement("div");
      warningsHost.className = "trip-warnings";
      if (route.isFallback) {
        warningsHost.appendChild(makeWarning('לא הצלחנו לחשב מסלול לפי כבישים בפועל (OSRM לא זמין) — מוצג קו ישר בקירוב.'));
      }
      plan.warnings.forEach(function () {
        warningsHost.appendChild(makeWarning("לא נמצאה עמדת טעינה מתאימה בקטע מסוים של המסלול — ייתכן שתידרש עצירה נוספת שלא סומנה."));
      });
      summaryEl.insertBefore(warningsHost, summaryEl.querySelector("#trip-fit-btn"));
    }

    summaryEl.classList.remove("hidden");
  }

  function makeWarning(text) {
    var div = document.createElement("div");
    div.className = "trip-warning";
    div.innerHTML = icon("shield-check") + "<span>" + escapeHtml(text) + "</span>";
    return div;
  }

  function renderStopsList(plan) {
    stopsListEl.innerHTML = "";
    plan.stops.forEach(function (stop, i) {
      var s = stop.station;
      var div = document.createElement("div");
      div.className = "trip-stop-item";
      div.innerHTML =
        '<div class="trip-stop-badge">' + (i + 1) + "</div>" +
        '<div class="trip-stop-text">' +
        '<div class="trip-stop-name">' + escapeHtml(s.n || "עמדת טעינה") + "</div>" +
        '<div class="trip-stop-meta">אחרי ' + Math.round(stop.distanceFromStartKm).toLocaleString("he-IL") + ' ק"מ · ' + (s.mp || "?") + "kW · " + escapeHtml(s.p || "") + "</div>" +
        "</div>";
      div.addEventListener("click", function () {
        map.setView([s.lat, s.lng], 14);
        tripLayer.eachLayer(function (layer) {
          if (layer.getLatLng && layer.getLatLng().lat === s.lat && layer.getLatLng().lng === s.lng) layer.openPopup();
        });
      });
      stopsListEl.appendChild(div);
    });
  }

  // ---------- calculate ----------

  calcBtn.addEventListener("click", function () {
    if (!tripState.origin || !tripState.destination) {
      setStatus("בחרו מוצא ויעד — מרשימת ההצעות או בלחיצה על המפה.", "error");
      return;
    }

    var vehicle = readVehicleInputs();
    vehicle.batteryPercent = readBatteryPercent();
    calcBtn.disabled = true;
    setStatus("מחשב מסלול ועצירות טעינה&hellip;");
    summaryEl.classList.add("hidden");
    stopsListEl.innerHTML = "";

    fetchOsrmRoute(tripState.origin, tripState.destination)
      .catch(function () { return straightLineRoute(tripState.origin, tripState.destination); })
      .then(function (route) {
        var stations = EVMap.getStations();
        var plan = TripLogic.planTripStops(route.coords, stations, vehicle, { searchRadiiKm: [5, 10, 15], preferMinPowerKw: 50 });
        renderTripOnMap(route, plan, tripState.origin, tripState.destination);
        renderSummary(route, plan, vehicle);
        renderStopsList(plan);
        setStatus(null);
        saveTripToHistory(tripState.origin, tripState.destination, vehicle, plan, route);
        lastResult = { route: route, plan: plan };
      })
      .catch(function (e) {
        console.error(e);
        setStatus("אירעה שגיאה בחישוב המסלול. נסו שוב.", "error");
      })
      .finally(function () {
        calcBtn.disabled = false;
      });
  });

  fitBtn.addEventListener("click", function () {
    var bounds = tripLayer.getBounds();
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [40, 40] });
  });

  // ---------- saved trips ----------

  function loadSavedTrips() {
    try { return JSON.parse(localStorage.getItem(TRIPS_KEY)) || []; } catch (e) { return []; }
  }

  function saveTripToHistory(origin, destination, vehicle, plan, route) {
    var trips = loadSavedTrips();
    trips.unshift({
      id: Date.now(),
      origin: origin, destination: destination, vehicle: vehicle,
      summary: { totalDistanceKm: plan.totalDistanceKm, durationMin: route.durationMin, stopsCount: plan.stops.length },
    });
    trips = trips.slice(0, MAX_SAVED_TRIPS);
    try { localStorage.setItem(TRIPS_KEY, JSON.stringify(trips)); } catch (e) { /* storage unavailable, ignore */ }
  }

  function shortLabel(point) {
    if (!point.label) return point.lat.toFixed(3) + ", " + point.lng.toFixed(3);
    return point.label.split(",")[0];
  }

  function renderSavedTrips() {
    var trips = loadSavedTrips();
    savedList.innerHTML = "";
    savedEmpty.classList.toggle("hidden", trips.length > 0);
    trips.forEach(function (trip) {
      var item = document.createElement("div");
      item.className = "saved-trip-item";

      var openBtn = document.createElement("button");
      openBtn.type = "button";
      openBtn.className = "saved-trip-text";
      openBtn.innerHTML =
        '<div class="saved-trip-route">' + escapeHtml(shortLabel(trip.origin)) + " ← " + escapeHtml(shortLabel(trip.destination)) + "</div>" +
        '<div class="saved-trip-meta">' + Math.round(trip.summary.totalDistanceKm).toLocaleString("he-IL") + ' ק"מ · ' + trip.summary.stopsCount + " עצירות</div>";
      openBtn.addEventListener("click", function () { loadTrip(trip); });

      var deleteBtn = document.createElement("button");
      deleteBtn.type = "button";
      deleteBtn.className = "saved-trip-delete";
      deleteBtn.setAttribute("aria-label", "מחק תוכנית");
      deleteBtn.innerHTML = icon("x");
      deleteBtn.addEventListener("click", function () { deleteSavedTrip(trip.id); });

      item.appendChild(openBtn);
      item.appendChild(deleteBtn);
      savedList.appendChild(item);
    });
  }

  function deleteSavedTrip(id) {
    var trips = loadSavedTrips().filter(function (t) { return t.id !== id; });
    try { localStorage.setItem(TRIPS_KEY, JSON.stringify(trips)); } catch (e) { /* ignore */ }
    renderSavedTrips();
  }

  function loadTrip(trip) {
    tripState.origin = trip.origin;
    tripState.destination = trip.destination;
    originField.setPoint(trip.origin);
    destField.setPoint(trip.destination);
    rangeInput.value = trip.vehicle.rangeKm;
    consumptionInput.value = trip.vehicle.consumptionKwh100km;
    marginInput.value = trip.vehicle.safetyMarginPercent;
    readVehicleInputs();
    batterySlider.value = trip.vehicle.batteryPercent;
    readBatteryPercent();
    savedPanel.classList.add("hidden");
    calcBtn.click();
  }

  savedBtn.addEventListener("click", function () {
    renderSavedTrips();
    savedPanel.classList.remove("hidden");
  });
  savedClose.addEventListener("click", function () { savedPanel.classList.add("hidden"); });

  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    if (!savedPanel.classList.contains("hidden")) savedPanel.classList.add("hidden");
    else if (pickTarget) cancelPick();
  });
})();
