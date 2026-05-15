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
const DISPLAY_MARKET = 'market';
const LEGACY_MARKET_MODES = new Set(['crypto', 'currency', 'stock']);
const DISPLAY_MODES = {
  [DISPLAY_CLOCK]: 'Saat',
  [DISPLAY_PROFILE]: 'Aktif Profil',
  [DISPLAY_VOLUME]: 'Ses Seviyesi',
  [DISPLAY_CUSTOM]: 'Özel Metin',
  [DISPLAY_MARKET]: 'Piyasalar',
};

const MARKET_TYPE_LABELS = {
  crypto: 'Kripto',
  currency: 'Döviz',
  stock: 'Hisse',
  commodity: 'Emtia',
};

const SYMBOL_CATALOG = {
  crypto: [
    ['BTC', 'Bitcoin'], ['ETH', 'Ethereum'], ['BNB', 'BNB'],
    ['SOL', 'Solana'], ['XRP', 'XRP'], ['ADA', 'Cardano'],
    ['DOGE', 'Dogecoin'], ['LTC', 'Litecoin'], ['MATIC', 'Polygon'],
    ['AVAX', 'Avalanche'], ['DOT', 'Polkadot'], ['LINK', 'Chainlink'],
    ['TRX', 'TRON'], ['BCH', 'Bitcoin Cash'], ['USDT', 'Tether'],
    ['USDC', 'USD Coin'], ['SHIB', 'Shiba Inu'], ['NEAR', 'NEAR Protocol'],
    ['OP', 'Optimism'], ['ARB', 'Arbitrum'], ['PEPE', 'Pepe'],
  ],
  currency: [
    ['USD-TRY', 'Dolar / Türk Lirası'], ['EUR-TRY', 'Euro / Türk Lirası'],
    ['GBP-TRY', 'Sterlin / Türk Lirası'], ['CHF-TRY', 'İsviçre Frangı / Türk Lirası'],
    ['USD-EUR', 'Dolar / Euro'], ['EUR-USD', 'Euro / Dolar'],
    ['GBP-USD', 'Sterlin / Dolar'], ['USD-JPY', 'Dolar / Yen'],
    ['EUR-GBP', 'Euro / Sterlin'], ['USD-CHF', 'Dolar / Frank'],
    ['USD-CAD', 'Dolar / Kanada Doları'], ['AUD-USD', 'Avustralya Doları / Dolar'],
    ['NZD-USD', 'Yeni Zelanda Doları / Dolar'], ['USD-CNY', 'Dolar / Yuan'],
    ['USD-INR', 'Dolar / Rupi'], ['USD-RUB', 'Dolar / Ruble'],
  ],
  stock: [
    ['AAPL', 'Apple'], ['MSFT', 'Microsoft'], ['GOOGL', 'Alphabet (Google)'],
    ['AMZN', 'Amazon'], ['NVDA', 'NVIDIA'], ['META', 'Meta'],
    ['TSLA', 'Tesla'], ['NFLX', 'Netflix'], ['AMD', 'AMD'],
    ['INTC', 'Intel'], ['BABA', 'Alibaba'], ['PLTR', 'Palantir'],
    ['THYAO.IS', 'Türk Hava Yolları (BIST)'], ['GARAN.IS', 'Garanti Bankası (BIST)'],
    ['AKBNK.IS', 'Akbank (BIST)'], ['KCHOL.IS', 'Koç Holding (BIST)'],
    ['ASELS.IS', 'Aselsan (BIST)'], ['ISCTR.IS', 'İş Bankası (BIST)'],
    ['EREGL.IS', 'Ereğli Demir Çelik (BIST)'], ['SISE.IS', 'Şişe Cam (BIST)'],
    ['TUPRS.IS', 'Tüpraş (BIST)'], ['PETKM.IS', 'Petkim (BIST)'],
    ['SAHOL.IS', 'Sabancı Holding (BIST)'], ['FROTO.IS', 'Ford Otosan (BIST)'],
    ['BIMAS.IS', 'BİM (BIST)'],
  ],
  commodity: [
    ['GC=F', 'Altın (USD/ons)'], ['SI=F', 'Gümüş (USD/ons)'],
    ['PL=F', 'Platin (USD/ons)'], ['PA=F', 'Paladyum (USD/ons)'],
    ['HG=F', 'Bakır (USD/lb)'], ['CL=F', 'Ham Petrol WTI (USD/varil)'],
    ['BZ=F', 'Brent Petrol (USD/varil)'], ['NG=F', 'Doğalgaz (USD/MMBtu)'],
    ['XAUTRY=X', 'Altın / TL (ons)'], ['XAUUSD=X', 'Altın / USD (ons)'],
    ['XAGUSD=X', 'Gümüş / USD (ons)'], ['^GSPC', 'S&P 500'],
    ['^DJI', 'Dow Jones'], ['^IXIC', 'Nasdaq'], ['XU100.IS', 'BIST 100'],
  ],
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
  // Fresh installs start empty — modules are discovered from the
  // physical hardware on first connect, and assignments live on per
  // profile from there. Showing fake "Spotify / Mute Mic / Play"
  // seed buttons before a device exists confuses the user about
  // what's real.
  const def = newProfile('Varsayılan', []);
  const gaming = newProfile('Gaming', []);
  const work = newProfile('Work', []);

  return {
    profiles: [def, gaming, work],
    activeProfileId: def.id,
    selectedPort: '',
    connected: false,
    selection: null, // { moduleId, kind: 'button'|'encoder'|'display', index, sub? }
    firmwareAlert: null, // { connected: string, required: string }
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

  // Migrate legacy modes (crypto/currency/stock) and string-list
  // symbols into the unified market mode where each symbol carries
  // its own type. Keep this idempotent — already-typed entries pass
  // through untouched.
  const legacyMode = LEGACY_MARKET_MODES.has(m.display_mode) ? m.display_mode : null;
  let raw = m.display_symbols;
  if (!Array.isArray(raw)) raw = m.display_symbol ? [m.display_symbol] : [];
  m.display_symbols = raw
    .map((it) => {
      if (it && typeof it === 'object') {
        const sym = String(it.symbol || '').trim();
        const type = String(it.type || legacyMode || 'stock').toLowerCase();
        return sym ? { symbol: sym, type } : null;
      }
      const sym = String(it || '').trim();
      return sym ? { symbol: sym, type: legacyMode || 'stock' } : null;
    })
    .filter(Boolean);
  if (legacyMode) m.display_mode = DISPLAY_MARKET;

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
    const { connected, selection, firmwareAlert, ...persist } = state;
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
  DISPLAY_MARKET, MARKET_TYPE_LABELS, DISPLAY_MODES,
  SYMBOL_CATALOG,
  uid, newButton, newEncoder, newModule, newProfile,
};
