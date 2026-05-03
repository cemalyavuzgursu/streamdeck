/* global React */
const { useState, useEffect, useRef, useMemo, useCallback, createContext, useContext } = React;

// ───────── Constants ─────────
const ACTION_NONE = 'none';
const ACTION_SHORTCUT = 'shortcut';
const ACTION_MEDIA = 'media';
const ACTION_APP = 'app_launch';
const ACTION_MACRO = 'macro';
const ACTION_PROFILE_SWITCH = 'profile_switch';

const ACTION_LABELS = {
  [ACTION_NONE]: 'Yok',
  [ACTION_SHORTCUT]: 'Klavye Kısayolu',
  [ACTION_MEDIA]: 'Medya Kontrolü',
  [ACTION_APP]: 'Uygulama Aç',
  [ACTION_MACRO]: 'Makro',
  [ACTION_PROFILE_SWITCH]: 'Profil Değiştir',
};
const ACTION_GLYPHS = {
  [ACTION_NONE]: '○',
  [ACTION_SHORTCUT]: '⌘',
  [ACTION_MEDIA]: '♪',
  [ACTION_APP]: '▤',
  [ACTION_MACRO]: '≡',
  [ACTION_PROFILE_SWITCH]: '⇄',
};
const ACTION_SHORT = {
  [ACTION_NONE]: 'empty',
  [ACTION_SHORTCUT]: 'KEY',
  [ACTION_MEDIA]: 'MEDIA',
  [ACTION_APP]: 'APP',
  [ACTION_MACRO]: 'MACRO',
  [ACTION_PROFILE_SWITCH]: 'PROFILE',
};

const MEDIA_ACTIONS = {
  volume_up: 'Ses Artır (+)',
  volume_down: 'Ses Azalt (−)',
  mute: 'Sessiz / Aç',
  play_pause: 'Oynat / Duraklat',
  next_track: 'Sonraki Parça',
  prev_track: 'Önceki Parça',
  stop: 'Durdur',
};

const DISPLAY_CLOCK = 'clock';
const DISPLAY_PROFILE = 'profile_name';
const DISPLAY_VOLUME = 'volume';
const DISPLAY_CUSTOM = 'custom_text';
const DISPLAY_CRYPTO = 'crypto';
const DISPLAY_CURRENCY = 'currency';
const DISPLAY_STOCK = 'stock';
const DISPLAY_MODES = {
  [DISPLAY_CLOCK]: 'Saat',
  [DISPLAY_PROFILE]: 'Aktif Profil',
  [DISPLAY_VOLUME]: 'Ses Seviyesi',
  [DISPLAY_CUSTOM]: 'Özel Metin',
  [DISPLAY_CRYPTO]: 'Kripto',
  [DISPLAY_CURRENCY]: 'Döviz',
  [DISPLAY_STOCK]: 'Hisse',
};

const STORE_KEY = 'macropad-state-v1';

// ───────── Defaults ─────────
const uid = () => Math.random().toString(36).slice(2, 10);

function newButton() { return { action_type: ACTION_NONE, action_data: {}, label: '' }; }
function newEncoder() { return { cw: newButton(), ccw: newButton(), push: newButton() }; }
function newModule(opts = {}) {
  const buttonCount = opts.button_count ?? 4;
  const encoderCount = opts.encoder_count ?? 0;
  return {
    module_id: opts.module_id || uid(),
    module_type: opts.module_type || 'slave',
    name: opts.name || 'Yeni Modül',
    button_count: buttonCount,
    encoder_count: encoderCount,
    has_display: opts.has_display ?? false,
    buttons: Array.from({ length: buttonCount }, newButton),
    encoders: Array.from({ length: encoderCount }, newEncoder),
    display_mode: DISPLAY_CLOCK,
    display_custom_text: '',
    display_symbols: [],
    display_rotate_seconds: 5,
    display_invert: false,
  };
}
function newProfile(name = 'Yeni Profil', modules = []) {
  return {
    id: uid(),
    name,
    modules,
    triggers: { foreground_apps: [], time_windows: [] },
  };
}

function defaultState() {
  const main = newModule({ name: 'Ana Modül', module_type: 'main', button_count: 4, encoder_count: 1, has_display: true });
  main.buttons[0] = { action_type: ACTION_APP, action_data: { path: 'C:\\\\Users\\\\me\\\\Spotify.exe', args: '' }, label: 'Spotify' };
  main.buttons[1] = { action_type: ACTION_SHORTCUT, action_data: { keys: 'ctrl+shift+m' }, label: 'Mute Mic' };
  main.buttons[2] = { action_type: ACTION_MEDIA, action_data: { action: 'play_pause' }, label: 'Play' };
  main.buttons[3] = { action_type: ACTION_PROFILE_SWITCH, action_data: {}, label: 'Gaming' };
  main.encoders[0].cw = { action_type: ACTION_MEDIA, action_data: { action: 'volume_up' }, label: 'Vol +' };
  main.encoders[0].ccw = { action_type: ACTION_MEDIA, action_data: { action: 'volume_down' }, label: 'Vol −' };
  main.encoders[0].push = { action_type: ACTION_MEDIA, action_data: { action: 'mute' }, label: 'Mute' };

  const right = newModule({ name: 'Sağ Modül', module_type: 'slave', button_count: 8, encoder_count: 0 });
  right.buttons[0] = { action_type: ACTION_SHORTCUT, action_data: { keys: 'ctrl+c' }, label: 'Copy' };
  right.buttons[1] = { action_type: ACTION_SHORTCUT, action_data: { keys: 'ctrl+v' }, label: 'Paste' };
  right.buttons[2] = { action_type: ACTION_SHORTCUT, action_data: { keys: 'ctrl+z' }, label: 'Undo' };
  right.buttons[3] = { action_type: ACTION_SHORTCUT, action_data: { keys: 'ctrl+shift+z' }, label: 'Redo' };

  const def = newProfile('Varsayılan', [main, right]);
  const gaming = newProfile('Gaming', [newModule({ name: 'Ana Modül', module_type: 'main', button_count: 4, encoder_count: 1, has_display: true })]);
  const work = newProfile('Work', [newModule({ name: 'Ana Modül', module_type: 'main', button_count: 4, encoder_count: 1, has_display: true })]);

  return {
    profiles: [def, gaming, work],
    activeProfileId: def.id,
    selectedPort: 'COM3',
    connected: false,
    selection: null, // { moduleId, kind: 'button'|'encoder'|'display', index, sub? }
  };
}

// ───────── Store ─────────
const StoreCtx = createContext(null);
function useStore() { return useContext(StoreCtx); }

// Backfill fields older saved state may be missing. Without this,
// an undefined display_mode falls out of JSON.stringify entirely and
// the firmware sees the field as absent — its default takes over and
// the user's mode selection never reaches the device.
function normaliseModule(m) {
  if (!m) return m;
  if (m.display_mode == null) m.display_mode = DISPLAY_CLOCK;
  if (m.display_custom_text == null) m.display_custom_text = '';
  // Migrate single legacy display_symbol → array form.
  if (!Array.isArray(m.display_symbols)) {
    m.display_symbols = m.display_symbol ? [m.display_symbol] : [];
  }
  if (m.display_rotate_seconds == null) m.display_rotate_seconds = 5;
  if (m.display_invert == null) m.display_invert = false;
  if (!Array.isArray(m.buttons)) m.buttons = [];
  if (!Array.isArray(m.encoders)) m.encoders = [];
  return m;
}

function normaliseProfile(p) {
  if (!p) return p;
  if (!p.triggers || typeof p.triggers !== 'object') {
    p.triggers = { foreground_apps: [], time_windows: [] };
  } else {
    if (!Array.isArray(p.triggers.foreground_apps)) p.triggers.foreground_apps = [];
    if (!Array.isArray(p.triggers.time_windows)) p.triggers.time_windows = [];
  }
  return p;
}

function StoreProvider({ children }) {
  const [state, setState] = useState(() => {
    try {
      const raw = localStorage.getItem(STORE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && Array.isArray(parsed.profiles) && parsed.profiles.length) {
          parsed.profiles.forEach((p) => {
            normaliseProfile(p);
            (p.modules || []).forEach(normaliseModule);
          });
          parsed.connected = false;
          parsed.selection = null;
          return parsed;
        }
      }
    } catch {}
    return defaultState();
  });

  const [toast, setToast] = useState(null);
  const toastTimer = useRef();
  const showToast = useCallback((msg) => {
    setToast(msg);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 2200);
  }, []);

  useEffect(() => {
    const { connected, selection, ...persist } = state;
    try { localStorage.setItem(STORE_KEY, JSON.stringify(persist)); } catch {}
  }, [state]);

  // ── helpers
  const update = useCallback((fn) => setState((s) => fn(s) ?? s), []);

  const updateActiveProfile = useCallback((mut) => {
    setState((s) => {
      const profiles = s.profiles.map((p) => {
        if (p.id !== s.activeProfileId) return p;
        const draft = JSON.parse(JSON.stringify(p));
        mut(draft);
        return draft;
      });
      return { ...s, profiles };
    });
  }, []);

  const activeProfile = useMemo(
    () => state.profiles.find((p) => p.id === state.activeProfileId) || state.profiles[0],
    [state.profiles, state.activeProfileId]
  );

  const value = {
    state, setState, update, updateActiveProfile,
    activeProfile,
    showToast, toast,
  };
  return <StoreCtx.Provider value={value}>{children}</StoreCtx.Provider>;
}

window.MP = {
  useStore, StoreProvider,
  ACTION_NONE, ACTION_SHORTCUT, ACTION_MEDIA, ACTION_APP, ACTION_MACRO, ACTION_PROFILE_SWITCH,
  ACTION_LABELS, ACTION_GLYPHS, ACTION_SHORT,
  MEDIA_ACTIONS,
  DISPLAY_CLOCK, DISPLAY_PROFILE, DISPLAY_VOLUME, DISPLAY_CUSTOM,
  DISPLAY_CRYPTO, DISPLAY_CURRENCY, DISPLAY_STOCK, DISPLAY_MODES,
  uid, newButton, newEncoder, newModule, newProfile,
};
