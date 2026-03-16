/* ============================================================
   main.js — App init, mode switching, keyboard shortcuts
   ============================================================ */

'use strict';

// Namespace for cross-module callbacks — defined first so config_panel.js
// can safely call Main.onConfigSaved() even before the IIFE resolves.
const Main = {
  onConfigSaved: () => {},
};

// Expose global callbacks referenced from HTML onclick attributes
let toggleConfig, enterPresentationMode, exitPresentationMode,
    saveConfig, recenterMap, startTileCache, onSourceChange;

(async () => {
  // ----------------------------------------------------------------
  // Boot
  // ----------------------------------------------------------------
  const cfg = await ConfigPanel.loadAndPopulate();
  if (!cfg) {
    console.error('[main] Failed to load config on startup');
    return;
  }

  // Apply body theme class
  _applyThemeClass(cfg.display.theme);

  // Init map
  AircraftMap.init(cfg);
  AircraftMap.applyProjectionTransform(
    cfg.display.ceiling_flip_vertical,
    cfg.display.ceiling_rotate_180
  );

  // Init socket
  SocketClient.init(cfg);

  // ----------------------------------------------------------------
  // Config panel toggle
  // ----------------------------------------------------------------
  let _configOpen = false;

  toggleConfig = function () {
    _configOpen = !_configOpen;
    const panel = document.getElementById('config-panel');
    if (panel) panel.classList.toggle('hidden', !_configOpen);
  };

  // ----------------------------------------------------------------
  // Presentation mode
  // ----------------------------------------------------------------
  let _presenting = false;

  enterPresentationMode = function () {
    _presenting = true;
    document.body.classList.add('presentation-mode');

    const hint = document.getElementById('present-hint');
    if (hint) {
      hint.classList.remove('hidden');
      // Remove after animation
      hint.addEventListener('animationend', () => hint.classList.add('hidden'), { once: true });
    }

    // Request fullscreen
    const el = document.documentElement;
    if (el.requestFullscreen) el.requestFullscreen().catch(() => {});
    else if (el.webkitRequestFullscreen) el.webkitRequestFullscreen();
  };

  exitPresentationMode = function () {
    _presenting = false;
    document.body.classList.remove('presentation-mode');

    const hint = document.getElementById('present-hint');
    if (hint) hint.classList.add('hidden');

    if (document.exitFullscreen && document.fullscreenElement) {
      document.exitFullscreen().catch(() => {});
    } else if (document.webkitExitFullscreen) {
      document.webkitExitFullscreen();
    }
  };

  // ----------------------------------------------------------------
  // Keyboard shortcuts
  // ----------------------------------------------------------------
  document.addEventListener('keydown', (e) => {
    // Ignore when typing in input fields
    const tag = document.activeElement?.tagName;
    if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;

    switch (e.key) {
      case 'p':
      case 'P':
        _presenting ? exitPresentationMode() : enterPresentationMode();
        break;
      case 'Escape':
        if (_presenting) exitPresentationMode();
        break;
      case 'c':
      case 'C':
        toggleConfig();
        break;
      case 'r':
      case 'R':
        recenterMap();
        break;
    }
  });

  // Also exit presentation if Escape is used via Fullscreen API
  document.addEventListener('fullscreenchange', () => {
    if (!document.fullscreenElement && _presenting) {
      exitPresentationMode();
    }
  });

  // ----------------------------------------------------------------
  // Delegated actions (called by config_panel.js and HTML buttons)
  // ----------------------------------------------------------------
  saveConfig = ConfigPanel.saveConfig;
  startTileCache = ConfigPanel.startTileCache;
  onSourceChange = ConfigPanel.onSourceChange;

  recenterMap = function () {
    const c = ConfigPanel.getConfig();
    if (c) AircraftMap.recenter(c);
  };

  // ----------------------------------------------------------------
  // Called by ConfigPanel after a successful save
  // ----------------------------------------------------------------
  Main.onConfigSaved = function (newCfg) {
    SocketClient.updateConfig(newCfg);
    AircraftMap.recenter(newCfg);
    AircraftMap.applyTheme(newCfg.display.theme);
    AircraftMap.applyProjectionTransform(
      newCfg.display.ceiling_flip_vertical,
      newCfg.display.ceiling_rotate_180
    );
    _applyThemeClass(newCfg.display.theme);
    SocketClient.requestUpdate();
  };

  // ----------------------------------------------------------------
  // Helpers
  // ----------------------------------------------------------------
  function _applyThemeClass(theme) {
    document.body.classList.toggle('theme-light', theme === 'light');
    document.body.classList.toggle('theme-dark',  theme === 'dark');
  }
})();

