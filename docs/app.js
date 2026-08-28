(function () {
  "use strict";

  var tg = window.Telegram && window.Telegram.WebApp;
  if (tg) {
    try {
      tg.ready();
      tg.expand();
    } catch (e) { /* not running inside Telegram, ignore */ }
  }

  var ISRAEL_CENTER = [31.5, 34.8];
  var DEFAULT_ZOOM = 8;
  var FOCUSED_ZOOM = 13;

  var params = new URLSearchParams(window.location.search);
  var userLat = parseFloat(params.get("lat"));
  var userLng = parseFloat(params.get("lng"));
  var hasUserLocation = !isNaN(userLat) && !isNaN(userLng);

  var map = L.map("map", { zoomControl: true, attributionControl: true }).setView(
    hasUserLocation ? [userLat, userLng] : ISRAEL_CENTER,
    hasUserLocation ? FOCUSED_ZOOM : DEFAULT_ZOOM
  );

  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  var clusterGroup = L.markerClusterGroup({
    disableClusteringAtZoom: 17,
    spiderfyOnMaxZoom: true,
    maxClusterRadius: 55,
  });
  map.addLayer(clusterGroup);

  if (hasUserLocation) {
    var userIcon = L.divIcon({
      className: "",
      html: '<div style="font-size:26px;">🔴</div>',
      iconSize: [26, 26],
      iconAnchor: [13, 13],
    });
    L.marker([userLat, userLng], { icon: userIcon, zIndexOffset: 1000 })
      .addTo(map)
      .bindPopup("📍 המיקום שלך");
  }

  var stationIcon = L.divIcon({
    className: "station-emoji-icon",
    html: "⚡",
    iconSize: [22, 22],
    iconAnchor: [11, 11],
    popupAnchor: [0, -10],
  });

  var CONNECTOR_LABEL = {
    CCS2: "⚡ CCS2 (DC)",
    Type2: "🔌 Type 2 (AC)",
    CHAdeMO: "🇯🇵 CHAdeMO",
    Other: "🔌 אחר",
  };

  var allStations = [];
  var markerById = {};

  function haversineKm(lat1, lon1, lat2, lon2) {
    var R = 6371;
    var dLat = (lat2 - lat1) * Math.PI / 180;
    var dLon = (lon2 - lon1) * Math.PI / 180;
    var a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
      Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }

  function connectorsText(cn) {
    if (!cn || !cn.length) return "לא צוין";
    return cn.map(function (c) {
      var label = CONNECTOR_LABEL[c.t] || CONNECTOR_LABEL.Other;
      return c.kw ? (label + " " + c.kw + "kW") : label;
    }).join(" | ");
  }

  function priceText(pr) {
    return (pr === null || pr === undefined) ? "לא צוין" : ('עד ' + pr.toFixed(2) + ' ₪ לקוט"ש');
  }

  function popupHtml(s) {
    var addr = [s.a, s.c].filter(Boolean).join(", ");
    var wazeUrl = "https://waze.com/ul?ll=" + s.lat + "," + s.lng + "&navigate=yes";
    var gmapUrl = "https://www.google.com/maps/dir/?api=1&destination=" + s.lat + "," + s.lng;
    var html = '<div class="popup-name">🏢 ' + escapeHtml(s.n || "עמדת טעינה") + "</div>";
    if (addr) html += '<div class="popup-line">📍 ' + escapeHtml(addr) + "</div>";
    if (s.p) html += '<div class="popup-line">🏭 מפעיל: ' + escapeHtml(s.p) + "</div>";
    html += '<div class="popup-line">🔌 ' + connectorsText(s.cn) + "</div>";
    html += '<div class="popup-line">💰 ' + priceText(s.pr) + "</div>";
    if (s.g) html += '<div class="popup-gov">🏛️ מאומתת במאגר משרד האנרגיה</div>';
    html += '<div class="popup-actions">' +
      '<a href="' + wazeUrl + '" target="_blank" rel="noopener">🚗 Waze</a>' +
      '<a href="' + gmapUrl + '" target="_blank" rel="noopener">🗺️ Google Maps</a>' +
      "</div>";
    return html;
  }

  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function buildMarker(s) {
    var m = L.marker([s.lat, s.lng], { icon: stationIcon });
    m.bindPopup(popupHtml(s), { maxWidth: 260 });
    return m;
  }

  function passesFilters(s, query, speed, provider) {
    if (provider !== "ALL" && s.p !== provider) return false;
    if (speed !== "ALL") {
      var mp = s.mp || 0;
      if (speed === "SLOW" && !(mp <= 22)) return false;
      if (speed === "FAST" && !(mp >= 50 && mp < 150)) return false;
      if (speed === "ULTRA" && !(mp >= 150)) return false;
    }
    if (query) {
      var hay = ((s.n || "") + " " + (s.c || "") + " " + (s.a || "")).toLowerCase();
      if (hay.indexOf(query) === -1) return false;
    }
    return true;
  }

  function refreshMarkers() {
    var query = document.getElementById("search").value.trim().toLowerCase();
    var speed = document.getElementById("speed-filter").value;
    var provider = document.getElementById("provider-filter").value;

    clusterGroup.clearLayers();
    var matched = [];
    var layers = [];
    for (var i = 0; i < allStations.length; i++) {
      var s = allStations[i];
      if (!passesFilters(s, query, speed, provider)) continue;
      matched.push(s);
      layers.push(markerById[s.id]);
    }
    clusterGroup.addLayers(layers);
    document.getElementById("count").textContent =
      matched.length.toLocaleString("he-IL") + " מתוך " + allStations.length.toLocaleString("he-IL") + " עמדות";

    renderList(matched);
  }

  function renderList(matched) {
    var listEl = document.getElementById("list-items");
    var sorted = matched.slice();
    if (hasUserLocation) {
      sorted.forEach(function (s) {
        s._d = haversineKm(userLat, userLng, s.lat, s.lng);
      });
      sorted.sort(function (a, b) { return a._d - b._d; });
    } else {
      sorted.sort(function (a, b) { return (a.n || "").localeCompare(b.n || "", "he"); });
    }
    sorted = sorted.slice(0, 50);

    listEl.innerHTML = "";
    sorted.forEach(function (s) {
      var div = document.createElement("div");
      div.className = "list-item";
      var distText = hasUserLocation ? (s._d.toFixed(1) + ' ק"מ · ') : "";
      div.innerHTML =
        '<div class="li-name">🏢 ' + escapeHtml(s.n || "עמדת טעינה") + "</div>" +
        '<div class="li-meta">' + distText + escapeHtml(s.c || "") + " · " + escapeHtml(s.p || "") + "</div>";
      div.addEventListener("click", function () {
        map.setView([s.lat, s.lng], FOCUSED_ZOOM);
        var marker = markerById[s.id];
        clusterGroup.zoomToShowLayer(marker, function () {
          marker.openPopup();
        });
        document.getElementById("list-panel").classList.add("hidden");
      });
      listEl.appendChild(div);
    });
  }

  function populateProviders(stations) {
    var providers = Array.from(new Set(stations.map(function (s) { return s.p; }).filter(Boolean))).sort(function (a, b) {
      return a.localeCompare(b, "he");
    });
    var sel = document.getElementById("provider-filter");
    providers.forEach(function (p) {
      var opt = document.createElement("option");
      opt.value = p;
      opt.textContent = p;
      sel.appendChild(opt);
    });
  }

  fetch("stations.json")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      allStations = data;
      data.forEach(function (s) {
        markerById[s.id] = buildMarker(s);
      });
      populateProviders(data);
      refreshMarkers();
    })
    .catch(function (err) {
      document.getElementById("count").textContent = "שגיאה בטעינת הנתונים";
      console.error(err);
    });

  document.getElementById("search").addEventListener("input", refreshMarkers);
  document.getElementById("speed-filter").addEventListener("change", refreshMarkers);
  document.getElementById("provider-filter").addEventListener("change", refreshMarkers);

  document.getElementById("list-toggle").addEventListener("click", function () {
    document.getElementById("list-panel").classList.toggle("hidden");
  });
  document.getElementById("list-close").addEventListener("click", function () {
    document.getElementById("list-panel").classList.add("hidden");
  });
})();
