/* ============================================================
   config_panel.js — Load / save configuration form
   ============================================================ */

'use strict';

const ConfigPanel = (() => {
  let _config = null;
  let _cachePoller = null;

  // ------------------------------------------------------------------
  // Load config from API and populate form
  // ------------------------------------------------------------------
  async function loadAndPopulate() {
    try {
      const resp = await fetch('/api/config');
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      _config = await resp.json();
      _populate(_config);
      return _config;
    } catch (e) {
      console.error('[config] load failed', e);
      return null;
    }
  }

  function _populate(cfg) {
    _set('cfg-lat',       cfg.location.latitude);
    _set('cfg-lon',       cfg.location.longitude);
    _set('cfg-radius',    cfg.location.radius_km);

    _set('cfg-source',    cfg.data_source.type);
    _set('cfg-d1090-host', cfg.data_source.dump1090_host);
    _set('cfg-d1090-port', cfg.data_source.dump1090_port);
    _set('cfg-osky-client-id',     cfg.data_source.opensky_client_id);
    _set('cfg-osky-client-secret', cfg.data_source.opensky_client_secret);
    _set('cfg-osky-user', cfg.data_source.opensky_username);
    _set('cfg-osky-pass', cfg.data_source.opensky_password);
    _set('cfg-poll',      cfg.data_source.poll_interval_seconds);

    _set('cfg-theme',     cfg.display.theme);
    _chk('cfg-trails',    cfg.display.show_trails);
    _set('cfg-trail-len', cfg.display.trail_length);
    _chk('cfg-labels',    cfg.display.show_labels);
    _set('cfg-zoom',      cfg.display.zoom_level);
    _setZoomLabel(cfg.display.zoom_level);

    _chk('cfg-flip-v',    cfg.display.ceiling_flip_vertical);
    _chk('cfg-rot-180',   cfg.display.ceiling_rotate_180);

    _set('cfg-min-alt',   cfg.filters.min_altitude_ft);
    _set('cfg-max-alt',   cfg.filters.max_altitude_ft);
    _chk('cfg-ground',    cfg.filters.show_ground_vehicles);

    onSourceChange();
  }

  function _set(id, val) {
    const el = document.getElementById(id);
    if (el) el.value = val ?? '';
  }

  function _chk(id, val) {
    const el = document.getElementById(id);
    if (el) el.checked = !!val;
  }

  function _setZoomLabel(val) {
    const lbl = document.getElementById('cfg-zoom-val');
    if (lbl) lbl.textContent = val;
  }

  // ------------------------------------------------------------------
  // Show/hide source-specific sub-settings
  // ------------------------------------------------------------------
  function onSourceChange() {
    const src = document.getElementById('cfg-source')?.value;
    const d1090 = document.getElementById('dump1090-settings');
    const osky  = document.getElementById('opensky-settings');
    if (d1090) d1090.classList.toggle('hidden', src !== 'dump1090');
    if (osky)  osky.classList.toggle('hidden',  src !== 'opensky');
  }

  // ------------------------------------------------------------------
  // Collect form values into a config update object
  // ------------------------------------------------------------------
  function _collect() {
    return {
      location: {
        latitude:  parseFloat(document.getElementById('cfg-lat')?.value),
        longitude: parseFloat(document.getElementById('cfg-lon')?.value),
        radius_km: parseFloat(document.getElementById('cfg-radius')?.value),
      },
      data_source: {
        type:                    document.getElementById('cfg-source')?.value,
        dump1090_host:           document.getElementById('cfg-d1090-host')?.value,
        dump1090_port:           parseInt(document.getElementById('cfg-d1090-port')?.value, 10),
        opensky_client_id:       document.getElementById('cfg-osky-client-id')?.value,
        opensky_client_secret:   document.getElementById('cfg-osky-client-secret')?.value,
        opensky_username:        document.getElementById('cfg-osky-user')?.value,
        opensky_password:        document.getElementById('cfg-osky-pass')?.value,
        poll_interval_seconds:   parseInt(document.getElementById('cfg-poll')?.value, 10),
      },
      display: {
        theme:                  document.getElementById('cfg-theme')?.value,
        show_trails:            document.getElementById('cfg-trails')?.checked,
        trail_length:           parseInt(document.getElementById('cfg-trail-len')?.value, 10),
        show_labels:            document.getElementById('cfg-labels')?.checked,
        zoom_level:             parseInt(document.getElementById('cfg-zoom')?.value, 10),
        ceiling_flip_vertical:  document.getElementById('cfg-flip-v')?.checked,
        ceiling_rotate_180:     document.getElementById('cfg-rot-180')?.checked,
      },
      filters: {
        min_altitude_ft:        parseInt(document.getElementById('cfg-min-alt')?.value, 10),
        max_altitude_ft:        parseInt(document.getElementById('cfg-max-alt')?.value, 10),
        show_ground_vehicles:   document.getElementById('cfg-ground')?.checked,
      },
    };
  }

  // ------------------------------------------------------------------
  // Save config to API
  // ------------------------------------------------------------------
  async function saveConfig() {
    const updates = _collect();
    _showMsg('Saving…', null);

    try {
      const resp = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      _config = await resp.json();

      _showMsg('Settings saved.', 'success');
      setTimeout(() => _hideMsg(), 3000);

      // Propagate to map and socket
      Main.onConfigSaved(_config);

      return _config;
    } catch (e) {
      console.error('[config] save failed', e);
      _showMsg('Save failed: ' + e.message, 'error');
      return null;
    }
  }

  // ------------------------------------------------------------------
  // Tile pre-cache
  // ------------------------------------------------------------------
  async function startTileCache() {
    try {
      const resp = await fetch('/api/cache-tiles', { method: 'POST' });
      const data = await resp.json();

      if (resp.status === 409) {
        _showMsg('Tile caching already in progress.', null);
        return;
      }

      _showMsg('Tile caching started…', null);
      _showCacheProgress();
      _cachePoller = setInterval(_pollCacheStatus, 1500);
    } catch (e) {
      _showMsg('Failed to start tile caching: ' + e.message, 'error');
    }
  }

  async function _pollCacheStatus() {
    try {
      const resp = await fetch('/api/cache-tiles/status');
      const data = await resp.json();

      const pct = data.total > 0
        ? Math.round((data.fetched / data.total) * 100)
        : 0;

      document.getElementById('cache-pct').textContent = pct + '%';
      document.getElementById('progress-bar').style.width = pct + '%';

      if (data.status === 'done') {
        clearInterval(_cachePoller);
        _cachePoller = null;
        _showMsg(`Tile cache complete (${data.fetched} tiles).`, 'success');
        _hideCacheProgress();
      } else if (data.status === 'error') {
        clearInterval(_cachePoller);
        _cachePoller = null;
        _showMsg('Tile caching error: ' + data.error, 'error');
        _hideCacheProgress();
      }
    } catch (e) {
      console.warn('[cache] status poll failed', e);
    }
  }

  function _showCacheProgress() {
    const el = document.getElementById('cache-progress');
    if (el) el.classList.remove('hidden');
  }

  function _hideCacheProgress() {
    const el = document.getElementById('cache-progress');
    if (el) el.classList.add('hidden');
  }

  // ------------------------------------------------------------------
  // Message display
  // ------------------------------------------------------------------
  function _showMsg(text, type) {
    const el = document.getElementById('config-msg');
    if (!el) return;
    el.textContent = text;
    el.className = 'config-msg' + (type ? ' ' + type : '');
  }

  function _hideMsg() {
    const el = document.getElementById('config-msg');
    if (el) el.className = 'config-msg hidden';
  }

  // ------------------------------------------------------------------
  // Zoom range input live label
  // ------------------------------------------------------------------
  function onZoomChange() {
    const val = document.getElementById('cfg-zoom')?.value;
    _setZoomLabel(val);
  }

  function getConfig() { return _config; }

  return {
    loadAndPopulate,
    saveConfig,
    startTileCache,
    onSourceChange,
    onZoomChange,
    getConfig,
  };
})();

// Wire up zoom range live label
document.addEventListener('DOMContentLoaded', () => {
  const zoom = document.getElementById('cfg-zoom');
  if (zoom) zoom.addEventListener('input', ConfigPanel.onZoomChange);
});
