/* ============================================================
   map.js — Leaflet map, aircraft markers, trails
   ============================================================ */

'use strict';

const Map = (() => {
  let _map = null;
  let _config = null;

  // icao -> { marker, trail, data }
  const _aircraft = {};

  const TILE_URL_DARK  = '/tiles/{z}/{x}/{y}.png';
  const TILE_URL_LIGHT = '/tiles/{z}/{x}/{y}.png';  // proxy handles theme

  const TILE_ATTRIB_DARK  = '&copy; <a href="https://carto.com/">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>';
  const TILE_ATTRIB_LIGHT = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';

  let _tileLayer = null;
  let _centerMarker = null;
  let _rangeCircle = null;

  // ------------------------------------------------------------------
  // Colour helpers
  // ------------------------------------------------------------------
  function altColor(alt_ft) {
    if (alt_ft === null || alt_ft === undefined) return '#9E9E9E';
    if (alt_ft === 0)       return '#607D8B';   // ground
    if (alt_ft < 5000)      return '#4CAF50';   // low
    if (alt_ft < 15000)     return '#FFC107';   // medium-low
    if (alt_ft < 25000)     return '#FF9800';   // medium
    return '#F44336';                           // high
  }

  function vrSymbol(vr) {
    if (vr === null || vr === undefined) return '';
    if (vr >  100) return '▲';
    if (vr < -100) return '▼';
    return '—';
  }

  // ------------------------------------------------------------------
  // Aircraft SVG icon — rotated to heading
  // ------------------------------------------------------------------
  function buildIcon(heading, color) {
    const h = (heading !== null && heading !== undefined) ? heading : 0;
    const svg = `<svg xmlns="http://www.w3.org/2000/svg"
         width="32" height="32" viewBox="-16 -16 32 32">
      <g transform="rotate(${h})">
        <!-- fuselage -->
        <polygon points="0,-13 3,4 0,2 -3,4"
          fill="${color}" stroke="rgba(0,0,0,0.55)" stroke-width="1.2"/>
        <!-- wings -->
        <polygon points="0,0 10,6 8,8 0,3 -8,8 -10,6"
          fill="${color}" stroke="rgba(0,0,0,0.55)" stroke-width="1"/>
        <!-- tail -->
        <polygon points="0,9 4,13 -4,13"
          fill="${color}" stroke="rgba(0,0,0,0.55)" stroke-width="1"/>
      </g>
    </svg>`;
    return L.divIcon({
      html: svg,
      className: 'aircraft-icon',
      iconSize: [32, 32],
      iconAnchor: [16, 16],
      popupAnchor: [0, -18],
    });
  }

  // ------------------------------------------------------------------
  // Label tooltip content
  // ------------------------------------------------------------------
  function buildLabelText(ac, labelFields) {
    const parts = [];
    if (labelFields.includes('callsign') && ac.callsign)
      parts.push(ac.callsign);
    if (labelFields.includes('altitude') && ac.altitude_ft !== null && ac.altitude_ft !== undefined)
      parts.push((Math.round(ac.altitude_ft / 100) * 100).toLocaleString() + 'ft');
    if (labelFields.includes('speed') && ac.speed_kts !== null && ac.speed_kts !== undefined)
      parts.push(Math.round(ac.speed_kts) + 'kt');
    return parts.join(' · ') || (ac.callsign || ac.icao);
  }

  // ------------------------------------------------------------------
  // Popup content
  // ------------------------------------------------------------------
  function buildPopup(ac) {
    const fmt = (v, unit = '') =>
      v !== null && v !== undefined ? v + unit : 'N/A';
    const fmtAlt = (v) =>
      v !== null && v !== undefined ? v.toLocaleString() + ' ft' : 'N/A';
    const fmtSpd = (v) =>
      v !== null && v !== undefined ? Math.round(v) + ' kts' : 'N/A';
    const fmtHdg = (v) =>
      v !== null && v !== undefined ? Math.round(v) + '°' : 'N/A';
    const fmtVr = (v) =>
      v !== null && v !== undefined
        ? vrSymbol(v) + ' ' + Math.abs(Math.round(v)).toLocaleString() + ' fpm'
        : 'N/A';

    const rows = [
      ['ICAO',       ac.icao],
      ['Altitude',   fmtAlt(ac.altitude_ft)],
      ['Speed',      fmtSpd(ac.speed_kts)],
      ['Heading',    fmtHdg(ac.heading_deg)],
      ['V/Rate',     fmtVr(ac.vertical_rate_fpm)],
      ['Squawk',     fmt(ac.squawk)],
    ];

    const rowsHtml = rows.map(([k, v]) =>
      `<div class="popup-row"><span class="popup-key">${k}</span><span class="popup-val">${v}</span></div>`
    ).join('');

    return `<div class="popup-callsign">${ac.callsign || ac.icao}</div>${rowsHtml}`;
  }

  // ------------------------------------------------------------------
  // Initialise map
  // ------------------------------------------------------------------
  function init(cfg) {
    _config = cfg;

    _map = L.map('map', {
      zoomControl: true,
      attributionControl: true,
    }).setView([cfg.location.latitude, cfg.location.longitude], cfg.display.zoom_level);

    _applyTileLayer(cfg.display.theme);
    _applyRangeOverlay(cfg);
  }

  // ------------------------------------------------------------------
  // Swap tile layer when theme changes
  // ------------------------------------------------------------------
  function _applyTileLayer(theme) {
    if (_tileLayer) {
      _map.removeLayer(_tileLayer);
    }
    const attrib = theme === 'dark' ? TILE_ATTRIB_DARK : TILE_ATTRIB_LIGHT;
    _tileLayer = L.tileLayer(TILE_URL_DARK, {
      maxZoom: 19,
      attribution: attrib,
    }).addTo(_map);
  }

  // ------------------------------------------------------------------
  // Center marker + range circle overlay
  // ------------------------------------------------------------------
  function _applyRangeOverlay(cfg) {
    if (_centerMarker) { _map.removeLayer(_centerMarker); _centerMarker = null; }
    if (_rangeCircle)  { _map.removeLayer(_rangeCircle);  _rangeCircle  = null; }

    const lat = cfg.location.latitude;
    const lon = cfg.location.longitude;
    const r   = cfg.location.radius_km * 1000; // metres

    _rangeCircle = L.circle([lat, lon], {
      radius: r,
      color: '#7ec8e3',
      weight: 1,
      opacity: 0.35,
      fillColor: '#7ec8e3',
      fillOpacity: 0.04,
      dashArray: '6 4',
    }).addTo(_map);

    _centerMarker = L.circleMarker([lat, lon], {
      radius: 5,
      color: '#7ec8e3',
      weight: 2,
      fillColor: '#7ec8e3',
      fillOpacity: 0.8,
    }).addTo(_map).bindTooltip('Home', { permanent: false });
  }

  // ------------------------------------------------------------------
  // Update all aircraft from data array
  // ------------------------------------------------------------------
  function update(aircraftList, cfg) {
    if (!_map) return;
    _config = cfg;

    const showTrails  = cfg.display.show_trails;
    const showLabels  = cfg.display.show_labels;
    const labelFields = cfg.display.label_fields || ['callsign', 'altitude', 'speed'];
    const seen        = new Set();

    for (const ac of aircraftList) {
      const icao = ac.icao;
      if (!icao) continue;
      seen.add(icao);
      _upsertAircraft(ac, showTrails, showLabels, labelFields);
    }

    // Remove aircraft no longer in the list
    for (const icao of Object.keys(_aircraft)) {
      if (!seen.has(icao)) {
        _removeAircraft(icao);
      }
    }
  }

  function _upsertAircraft(ac, showTrails, showLabels, labelFields) {
    const icao  = ac.icao;
    const lat   = ac.latitude;
    const lon   = ac.longitude;
    const color = altColor(ac.altitude_ft);

    if (!lat || !lon) return;

    if (_aircraft[icao]) {
      // Update existing
      const entry = _aircraft[icao];
      entry.marker.setLatLng([lat, lon]);
      entry.marker.setIcon(buildIcon(ac.heading_deg, color));

      if (showLabels) {
        entry.marker.setTooltipContent(buildLabelText(ac, labelFields));
      }
      if (entry.marker.isPopupOpen()) {
        entry.marker.setPopupContent(buildPopup(ac));
      }

      // Update trail
      if (showTrails && ac.trail && ac.trail.length > 1) {
        if (entry.trail) {
          entry.trail.setLatLngs(ac.trail);
        } else {
          entry.trail = _buildTrail(ac.trail, color);
        }
      } else if (!showTrails && entry.trail) {
        _map.removeLayer(entry.trail);
        entry.trail = null;
      }

      entry.data = ac;
    } else {
      // New aircraft
      const marker = L.marker([lat, lon], { icon: buildIcon(ac.heading_deg, color) })
        .addTo(_map)
        .bindPopup(buildPopup(ac), { maxWidth: 260 });

      if (showLabels) {
        marker.bindTooltip(buildLabelText(ac, labelFields), {
          permanent: true,
          direction: 'right',
          className: 'aircraft-label',
          offset: [14, 0],
        });
      }

      const trail = (showTrails && ac.trail && ac.trail.length > 1)
        ? _buildTrail(ac.trail, color)
        : null;

      _aircraft[icao] = { marker, trail, data: ac };
    }
  }

  function _buildTrail(positions, color) {
    return L.polyline(positions, {
      color: color,
      weight: 1.5,
      opacity: 0.55,
      smoothFactor: 1,
    }).addTo(_map);
  }

  function _removeAircraft(icao) {
    const entry = _aircraft[icao];
    if (!entry) return;
    _map.removeLayer(entry.marker);
    if (entry.trail) _map.removeLayer(entry.trail);
    delete _aircraft[icao];
  }

  // ------------------------------------------------------------------
  // Re-centre map on home coordinates
  // ------------------------------------------------------------------
  function recenter(cfg) {
    if (!_map) return;
    _config = cfg;
    _map.setView([cfg.location.latitude, cfg.location.longitude], cfg.display.zoom_level);
    _applyRangeOverlay(cfg);
  }

  // ------------------------------------------------------------------
  // Apply theme change
  // ------------------------------------------------------------------
  function applyTheme(theme) {
    _applyTileLayer(theme);
  }

  // ------------------------------------------------------------------
  // Apply ceiling projection CSS transforms
  // ------------------------------------------------------------------
  function applyProjectionTransform(flipV, rot180) {
    const mapEl = document.getElementById('map');
    let t = '';
    if (flipV)  t += 'scaleY(-1) ';
    if (rot180) t += 'rotate(180deg) ';
    mapEl.style.transform = t.trim();
  }

  // ------------------------------------------------------------------
  // Expose
  // ------------------------------------------------------------------
  return { init, update, recenter, applyTheme, applyProjectionTransform };
})();
