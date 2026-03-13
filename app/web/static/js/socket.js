/* ============================================================
   socket.js — Socket.IO client, dispatches events to Map
   ============================================================ */

'use strict';

const SocketClient = (() => {
  let _socket = null;
  let _config  = null;

  function init(cfg) {
    _config = cfg;

    _socket = io({ transports: ['websocket', 'polling'] });

    _socket.on('connect', () => {
      console.log('[socket] connected');
      _setStatus('ok');
    });

    _socket.on('disconnect', () => {
      console.log('[socket] disconnected');
      _setStatus('error');
    });

    _socket.on('connect_error', () => {
      _setStatus('warn');
    });

    _socket.on('aircraft_update', (data) => {
      if (!data || !Array.isArray(data.aircraft)) return;

      // Update count badge
      const badge = document.getElementById('aircraft-count');
      if (badge) badge.textContent = `${data.count ?? data.aircraft.length} aircraft`;

      // Timestamp
      if (data.timestamp) {
        const d = new Date(data.timestamp * 1000);
        const el = document.getElementById('last-update');
        if (el) el.textContent = 'Updated ' + d.toLocaleTimeString();
      }

      // Forward to map
      if (_config) {
        Map.update(data.aircraft, _config);
      }
    });

    _socket.on('status_update', (data) => {
      if (!data) return;
      const dot = document.getElementById('status-dot');
      if (!dot) return;

      if (data.error) {
        _setStatus('warn');
        dot.title = 'Error: ' + data.error;
      } else if (data.last_update) {
        _setStatus('ok');
        dot.title = `Source: ${data.source} · ${data.aircraft_count} aircraft`;
      }
    });
  }

  function updateConfig(cfg) {
    _config = cfg;
  }

  function requestUpdate() {
    if (_socket && _socket.connected) {
      _socket.emit('request_update');
    }
  }

  function _setStatus(level) {
    const dot = document.getElementById('status-dot');
    if (!dot) return;
    dot.className = `status-dot status-${level}`;
  }

  return { init, updateConfig, requestUpdate };
})();
