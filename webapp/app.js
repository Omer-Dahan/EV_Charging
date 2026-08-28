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

  // Lucide icon paths (lucide.dev), inlined to avoid a runtime dependency
  // for content injected into Leaflet popups / list items.
  var ICON_PATHS = {
    zap: '<path d="M15.914 4a1.5 1.5 0 00-2.474-1.561l-9 9A1.5 1.5 0 005.5 14h4.002a.5.5 0 01.471.666L8.086 20a1.5 1.5 0 002.475 1.56l9-9A1.5 1.5 0 0018.5 10h-3.997a.5.5 0 01-.472-.667z"/>',
    "map-pin": '<path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/>',
    "building-2": '<path d="M10 12h4"/><path d="M10 8h4"/><path d="M14 21v-3a2 2 0 0 0-4 0v3"/><path d="M6 10H4a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-2"/><path d="M6 21V5a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v16"/>',
    plug: '<path d="M12 22v-5"/><path d="M15 8V2"/><path d="M17 8a1 1 0 0 1 1 1v4a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V9a1 1 0 0 1 1-1z"/><path d="M9 8V2"/>',
    banknote: '<rect width="20" height="12" x="2" y="6" rx="2"/><circle cx="12" cy="12" r="2"/><path d="M6 12h.01M18 12h.01"/>',
    "shield-check": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
    car: '<path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2"/><circle cx="7" cy="17" r="2"/><path d="M9 17h6"/><circle cx="17" cy="17" r="2"/>',
    map: '<path d="M14.106 5.553a2 2 0 0 0 1.788 0l3.659-1.83A1 1 0 0 1 21 4.619v12.764a1 1 0 0 1-.553.894l-4.553 2.277a2 2 0 0 1-1.788 0l-4.212-2.106a2 2 0 0 0-1.788 0l-3.659 1.83A1 1 0 0 1 3 19.381V6.618a1 1 0 0 1 .553-.894l4.553-2.277a2 2 0 0 1 1.788 0z"/><path d="M15 5.764v15"/><path d="M9 3.236v15"/>',
    check: '<path d="M20 6 9 17l-5-5"/>',
  };

  function icon(name, cls) {
    var body = ICON_PATHS[name] || "";
    return '<svg class="icon' + (cls ? " " + cls : "") + '" viewBox="0 0 24 24" fill="none" ' +
      'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      body + "</svg>";
  }

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
      html: '<div class="user-marker"></div>',
      iconSize: [16, 16],
      iconAnchor: [8, 8],
    });
    L.marker([userLat, userLng], { icon: userIcon, zIndexOffset: 1000 })
      .addTo(map)
      .bindPopup("המיקום שלך");
  }

  var stationIcon = L.divIcon({
    className: "",
    html: '<div class="station-marker">' + icon("zap") + "</div>",
    iconSize: [26, 26],
    iconAnchor: [13, 13],
    popupAnchor: [0, -12],
  });

  var CONNECTOR_LABEL = {
    CCS2: "CCS2 (DC)",
    Type2: "Type 2 (AC)",
    CHAdeMO: "CHAdeMO",
    Other: "אחר",
  };

  var allStations = [];
  var markerById = {};
  var activeSpeed = "ALL";
  var activeProvider = "ALL";

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
    }).join(" · ");
  }

  function priceText(pr) {
    return (pr === null || pr === undefined) ? "לא צוין" : ('עד ' + pr.toFixed(2) + ' ₪ לקוט"ש');
  }

  function popupHtml(s) {
    var addr = [s.a, s.c].filter(Boolean).join(", ");
    var wazeUrl = "https://waze.com/ul?ll=" + s.lat + "," + s.lng + "&navigate=yes";
    var gmapUrl = "https://www.google.com/maps/dir/?api=1&destination=" + s.lat + "," + s.lng;

    var html = '<div class="popup-header">' +
      '<div class="popup-icon">' + icon("zap") + "</div>" +
      '<div class="popup-name">' + escapeHtml(s.n || "עמדת טעינה") + "</div>" +
      "</div>";

    if (addr) html += '<div class="popup-line">' + icon("map-pin") + "<span>" + escapeHtml(addr) + "</span></div>";
    if (s.p) html += '<div class="popup-line">' + icon("building-2") + "<span>" + escapeHtml(s.p) + "</span></div>";
    html += '<div class="popup-line">' + icon("plug") + "<span>" + connectorsText(s.cn) + "</span></div>";
    html += '<div class="popup-line">' + icon("banknote") + "<span>" + priceText(s.pr) + "</span></div>";
    if (s.g) html += '<div class="popup-verified">' + icon("shield-check") + "<span>מאומתת במאגר משרד האנרגיה</span></div>";

    html += '<div class="popup-actions">' +
      '<a class="primary" href="' + wazeUrl + '" target="_blank" rel="noopener">' + icon("car") + "<span>Waze</span></a>" +
      '<a class="secondary" href="' + gmapUrl + '" target="_blank" rel="noopener">' + icon("map") + "<span>Google Maps</span></a>" +
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

    clusterGroup.clearLayers();
    var matched = [];
    var layers = [];
    for (var i = 0; i < allStations.length; i++) {
      var s = allStations[i];
      if (!passesFilters(s, query, activeSpeed, activeProvider)) continue;
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
        '<div class="li-badge">' + icon("zap") + "</div>" +
        '<div class="li-text">' +
        '<div class="li-name">' + escapeHtml(s.n || "עמדת טעינה") + "</div>" +
        '<div class="li-meta">' + distText + escapeHtml(s.c || "") + " · " + escapeHtml(s.p || "") + "</div>" +
        "</div>";
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

  var ALL_PROVIDERS_LABEL = "כל המפעילים";

  function buildProviderOption(value, label) {
    var div = document.createElement("div");
    div.className = "provider-option";
    if (value === activeProvider) div.classList.add("is-selected");
    div.setAttribute("role", "option");
    div.setAttribute("aria-selected", value === activeProvider ? "true" : "false");
    div.setAttribute("data-value", value);
    div.innerHTML =
      '<span class="provider-option-check">' + icon("check") + "</span>" +
      '<span class="provider-option-label">' + escapeHtml(label) + "</span>";
    div.addEventListener("click", function () {
      selectProvider(value, label);
    });
    return div;
  }

  function populateProviders(stations) {
    var providers = Array.from(new Set(stations.map(function (s) { return s.p; }).filter(Boolean))).sort(function (a, b) {
      return a.localeCompare(b, "he");
    });
    var optionsEl = document.getElementById("provider-options");
    optionsEl.innerHTML = "";
    optionsEl.appendChild(buildProviderOption("ALL", ALL_PROVIDERS_LABEL));
    providers.forEach(function (p) {
      optionsEl.appendChild(buildProviderOption(p, p));
    });
  }

  function selectProvider(value, label) {
    activeProvider = value;
    document.getElementById("provider-btn-label").textContent = label;
    document.querySelectorAll(".provider-option").forEach(function (opt) {
      var isSelected = opt.getAttribute("data-value") === value;
      opt.classList.toggle("is-selected", isSelected);
      opt.setAttribute("aria-selected", isSelected ? "true" : "false");
    });
    closeProviderDropdown();
    refreshMarkers();
  }

  function filterProviderOptions(query) {
    query = query.trim().toLowerCase();
    var options = document.querySelectorAll(".provider-option");
    var visibleCount = 0;
    options.forEach(function (opt) {
      var label = opt.querySelector(".provider-option-label").textContent.toLowerCase();
      var visible = !query || label.indexOf(query) !== -1;
      opt.classList.toggle("hidden", !visible);
      if (visible) visibleCount++;
    });
    document.getElementById("provider-no-results").classList.toggle("hidden", visibleCount > 0);
  }

  function openProviderDropdown() {
    var dropdown = document.getElementById("provider-dropdown");
    var search = document.getElementById("provider-search");
    dropdown.classList.remove("hidden");
    document.getElementById("provider-btn").setAttribute("aria-expanded", "true");
    search.value = "";
    filterProviderOptions("");
    search.focus();
  }

  function closeProviderDropdown() {
    document.getElementById("provider-dropdown").classList.add("hidden");
    document.getElementById("provider-btn").setAttribute("aria-expanded", "false");
  }

  function isProviderDropdownOpen() {
    return !document.getElementById("provider-dropdown").classList.contains("hidden");
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

  document.getElementById("provider-btn").addEventListener("click", function () {
    if (isProviderDropdownOpen()) {
      closeProviderDropdown();
    } else {
      openProviderDropdown();
    }
  });

  document.getElementById("provider-search").addEventListener("input", function (e) {
    filterProviderOptions(e.target.value);
  });

  document.addEventListener("click", function (e) {
    if (!isProviderDropdownOpen()) return;
    if (!document.getElementById("provider-wrap").contains(e.target)) {
      closeProviderDropdown();
    }
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && isProviderDropdownOpen()) {
      closeProviderDropdown();
      document.getElementById("provider-btn").focus();
    }
  });

  var speedButtons = document.querySelectorAll(".speed-btn");
  speedButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      speedButtons.forEach(function (b) { b.classList.remove("is-active"); });
      btn.classList.add("is-active");
      activeSpeed = btn.getAttribute("data-speed");
      refreshMarkers();
    });
  });

  document.getElementById("list-toggle").addEventListener("click", function () {
    document.getElementById("list-panel").classList.toggle("hidden");
  });
  document.getElementById("list-close").addEventListener("click", function () {
    document.getElementById("list-panel").classList.add("hidden");
  });
})();
