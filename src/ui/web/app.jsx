/* global React, MP */
const { useState, useEffect, useRef, useMemo, useCallback } = React;
const {
  useStore,
  ACTION_NONE, ACTION_SHORTCUT, ACTION_MEDIA, ACTION_APP, ACTION_MACRO, ACTION_PROFILE_SWITCH,
  ACTION_LABELS, ACTION_GLYPHS, ACTION_SHORT,
  MEDIA_ACTIONS,
  DISPLAY_CLOCK, DISPLAY_PROFILE, DISPLAY_VOLUME, DISPLAY_CUSTOM,
  DISPLAY_CRYPTO, DISPLAY_CURRENCY, DISPLAY_STOCK, DISPLAY_MODES,
  uid, newButton, newProfile,
} = window.MP;

const SYMBOL_PLACEHOLDERS = {
  [DISPLAY_CRYPTO]: 'BTC',
  [DISPLAY_CURRENCY]: 'USD-TRY',
  [DISPLAY_STOCK]: 'AAPL',
};
const SYMBOL_HINTS = {
  [DISPLAY_CRYPTO]: 'Örn: BTC, ETH, SOL — CoinGecko adları kabul (bitcoin, ethereum)',
  [DISPLAY_CURRENCY]: 'Örn: USD-TRY, EUR-USD, GBP-EUR',
  [DISPLAY_STOCK]: 'Örn: AAPL, MSFT, THYAO.IS (BIST)',
};

const bridge = window.MP_BRIDGE;

// ───────── Topbar ─────────
function Topbar({ onOpenFlash }) {
  const { state, setState, showToast, activeProfile } = useStore();
  const [ports, setPorts] = useState([{ device: state.selectedPort, label: state.selectedPort, is_esp: false }]);

  const refreshPorts = useCallback(() => {
    if (!bridge) {
      setPorts([
        { device: 'COM3', label: 'COM3', is_esp: false },
        { device: 'COM4', label: 'COM4', is_esp: false },
        { device: 'COM5', label: 'COM5 — ESP32-C3', is_esp: true },
      ]);
      return;
    }
    const handler = (result) => {
      const list = JSON.parse(result || '[]');
      const normalised = list.map((p) =>
        typeof p === 'string' ? { device: p, label: p, is_esp: false } : p
      );
      setPorts(normalised.length ? normalised : [{ device: state.selectedPort, label: state.selectedPort, is_esp: false }]);
      // Auto-select the ESP32-C3 if found and current selection isn't one.
      const esp = normalised.find((p) => p.is_esp);
      const currentMatches = normalised.some((p) => p.device === state.selectedPort);
      if (esp && !currentMatches) {
        setState((s) => ({ ...s, selectedPort: esp.device }));
      } else if (normalised.length && !currentMatches) {
        setState((s) => ({ ...s, selectedPort: normalised[0].device }));
      }
    };
    if (bridge.list_ports_detailed) bridge.list_ports_detailed(handler);
    else bridge.list_ports(handler);
  }, [setState, state.selectedPort]);

  useEffect(() => { refreshPorts(); }, [refreshPorts]);

  const sendConfig = () => {
    if (!state.connected) return showToast('Cihaz bağlı değil');
    if (!activeProfile) return;
    const payload = JSON.stringify(activeProfile);
    // Log so we can verify display_mode etc. survived the round-trip
    // through localStorage / discovery merge. Open DevTools → Console.
    console.log('[send_config] payload:', payload);
    const main = (activeProfile.modules || []).find((m) => m.module_type === 'main');
    if (main) {
      console.log('[send_config] main display_mode:', main.display_mode,
                  ' custom:', main.display_custom_text);
    }
    if (bridge) {
      bridge.send_config(payload, (ok) => {
        showToast(ok ? `Konfigürasyon gönderildi → ${activeProfile.name}` : 'Gönderim hatası');
      });
    } else {
      showToast(`Konfigürasyon gönderildi → ${activeProfile.name}`);
    }
  };

  return (
    <div className="topbar">
      <div className="brand">
        <div className="brand-mark"><span /><span /><span /><span /></div>
        <div>
          MacroPad
          <span className="sub">  v1.0</span>
        </div>
      </div>

      <div className="spacer" />

      <div className={`status-pill ${state.connected ? 'live' : ''}`}>
        <span className="dot" />
        {state.connected ? `Bağlı · ${state.selectedPort}` : 'Bağlı değil'}
      </div>

      <div className="port-group">
        <select className="port-select" value={state.selectedPort}
          onChange={(e) => setState((s) => ({ ...s, selectedPort: e.target.value }))}>
          {ports.map((p) => <option key={p.device} value={p.device}>{p.label}</option>)}
        </select>
        <button className="icon-btn" title="Portları Tara" onClick={() => { refreshPorts(); showToast('Portlar tarandı'); }}>↻</button>
      </div>

      <button className="btn ghost" onClick={onOpenFlash} title="Firmware Güncelle">⚡ Flash</button>

      <button className="btn ghost" title="Uygulama güncellemelerini kontrol et"
        onClick={() => {
          if (window.MP_checkForUpdates) {
            window.MP_checkForUpdates();
            showToast('Güncellemeler kontrol ediliyor…');
          } else {
            showToast('Güncelleyici hazır değil');
          }
        }}>↻ Güncelle</button>

      <button className="btn accent" onClick={sendConfig} title="Konfigürasyonu cihaza gönder">
        ↑ Cihaza Gönder
      </button>
    </div>
  );
}

// ───────── Sidebar (profiles) ─────────
function Sidebar({ onAddModule }) {
  const { state, setState, showToast, activeProfile } = useStore();
  const [renamingId, setRenamingId] = useState(null);
  const [renameVal, setRenameVal] = useState('');
  const [triggersFor, setTriggersFor] = useState(null);  // profile id whose triggers we're editing
  const fileInput = useRef();

  const select = (id) => {
    if (bridge && bridge.note_manual_switch) bridge.note_manual_switch();
    setState((s) => ({ ...s, activeProfileId: id, selection: null }));
  };

  const addProfile = () => {
    const p = newProfile(`Profil ${state.profiles.length + 1}`);
    setState((s) => ({ ...s, profiles: [...s.profiles, p], activeProfileId: p.id, selection: null }));
  };

  const duplicate = (id) => {
    const src = state.profiles.find((p) => p.id === id); if (!src) return;
    const copy = JSON.parse(JSON.stringify(src));
    copy.id = uid(); copy.name = src.name + ' (Kopya)';
    setState((s) => ({ ...s, profiles: [...s.profiles, copy], activeProfileId: copy.id }));
    showToast('Profil kopyalandı');
  };

  const remove = (id) => {
    if (state.profiles.length <= 1) return showToast('En az bir profil olmalı');
    if (!confirm('Bu profili silmek istediğinizden emin misiniz?')) return;
    setState((s) => {
      const profiles = s.profiles.filter((p) => p.id !== id);
      const activeProfileId = s.activeProfileId === id ? profiles[0].id : s.activeProfileId;
      return { ...s, profiles, activeProfileId, selection: null };
    });
  };

  const startRename = (p) => { setRenamingId(p.id); setRenameVal(p.name); };
  const commitRename = () => {
    if (!renamingId) return;
    setState((s) => ({
      ...s,
      profiles: s.profiles.map((p) => p.id === renamingId ? { ...p, name: renameVal.trim() || p.name } : p),
    }));
    setRenamingId(null);
  };

  const exportProfile = () => {
    if (!activeProfile) return;
    const blob = new Blob([JSON.stringify(activeProfile, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = `${activeProfile.name}.json`; a.click();
    URL.revokeObjectURL(url);
    showToast('Profil dışa aktarıldı');
  };

  const importProfile = (e) => {
    const f = e.target.files?.[0]; if (!f) return;
    const r = new FileReader();
    r.onload = () => {
      try {
        const data = JSON.parse(r.result);
        data.id = uid();
        setState((s) => ({ ...s, profiles: [...s.profiles, data], activeProfileId: data.id }));
        showToast(`'${data.name}' içe aktarıldı`);
      } catch { showToast('Geçersiz dosya'); }
    };
    r.readAsText(f);
    e.target.value = '';
  };

  return (
    <aside className="sidebar">
      <div className="side-section">
        <h3>Profiller <button className="add" onClick={addProfile} title="Yeni Profil">+</button></h3>
      </div>
      <div className="profile-list">
        {state.profiles.map((p) => {
          const active = p.id === state.activeProfileId;
          const meta = `${p.modules.length}m`;
          return (
            <div key={p.id} className={`profile-item ${active ? 'active' : ''}`} onClick={() => select(p.id)}>
              {renamingId === p.id ? (
                <input
                  className="input" autoFocus
                  value={renameVal}
                  onChange={(e) => setRenameVal(e.target.value)}
                  onBlur={commitRename}
                  onKeyDown={(e) => { if (e.key === 'Enter') commitRename(); if (e.key === 'Escape') setRenamingId(null); }}
                  onClick={(e) => e.stopPropagation()}
                  style={{ padding: '4px 8px', fontSize: 13 }}
                />
              ) : (
                <>
                  <span className="profile-name">{p.name}</span>
                  <span className="profile-meta">{meta}</span>
                  <span className="row-actions" onClick={(e) => e.stopPropagation()}>
                    <button className="icon-btn" title="Otomatik geçiş kuralları" onClick={() => setTriggersFor(p.id)}>⚙</button>
                    <button className="icon-btn" title="Yeniden adlandır" onClick={() => startRename(p)}>✎</button>
                    <button className="icon-btn" title="Kopyala" onClick={() => duplicate(p.id)}>⧉</button>
                    <button className="icon-btn danger" title="Sil" onClick={() => remove(p.id)}>✕</button>
                  </span>
                </>
              )}
            </div>
          );
        })}
      </div>

      <div className="side-foot">
        <button className="btn" onClick={onAddModule}>＋ Modül Ekle</button>
        <div className="row">
          <button className="btn ghost sm grow" onClick={exportProfile}>↓ Dışa</button>
          <button className="btn ghost sm grow" onClick={() => fileInput.current.click()}>↑ İçe</button>
          <input type="file" ref={fileInput} accept=".json" hidden onChange={importProfile} />
        </div>
      </div>
      {triggersFor && (
        <ProfileTriggersModal
          profileId={triggersFor}
          onClose={() => setTriggersFor(null)}
        />
      )}
    </aside>
  );
}

// ───────── Profile triggers modal ─────────
function ProfileTriggersModal({ profileId, onClose }) {
  const { state, setState, showToast } = useStore();
  const profile = state.profiles.find((p) => p.id === profileId);
  if (!profile) return null;

  const triggers = profile.triggers || { foreground_apps: [], time_windows: [] };
  const [appsText, setAppsText] = useState((triggers.foreground_apps || []).join('\n'));
  const [windows, setWindows] = useState(triggers.time_windows || []);

  const save = () => {
    const apps = appsText.split('\n').map((s) => s.trim()).filter(Boolean);
    setState((s) => ({
      ...s,
      profiles: s.profiles.map((p) => p.id === profileId ? {
        ...p,
        triggers: {
          foreground_apps: apps,
          time_windows: windows.filter((w) => w.from && w.to),
        },
      } : p),
    }));
    showToast('Kurallar kaydedildi');
    onClose();
  };

  const addWindow = () => setWindows((w) => [...w, { from: '09:00', to: '17:00' }]);
  const updateWindow = (i, field, val) => setWindows((w) => w.map((x, j) => j === i ? { ...x, [field]: val } : x));
  const removeWindow = (i) => setWindows((w) => w.filter((_, j) => j !== i));

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 520 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div className="ttl">"{profile.name}" — Otomatik Geçiş</div>
          <button className="icon-btn" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          <div className="field">
            <label>Bu uygulamalar açıkken bu profile geç</label>
            <textarea className="textarea" value={appsText}
              placeholder={'spotify.exe\nchrome.exe\nsteam.exe'}
              onChange={(e) => setAppsText(e.target.value)} />
            <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4, fontFamily: 'var(--font-mono)' }}>
              Her satıra bir uygulama adı (örn. spotify.exe). Büyük/küçük harf önemsiz.
            </div>
          </div>

          <div className="field">
            <label>Saat aralıklarında bu profile geç</label>
            {windows.length === 0 && (
              <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 6 }}>
                Henüz saat aralığı eklenmemiş.
              </div>
            )}
            {windows.map((w, i) => (
              <div key={i} className="row" style={{ marginBottom: 6, gap: 8 }}>
                <input className="input mono" type="time" value={w.from || ''}
                  style={{ width: 110 }}
                  onChange={(e) => updateWindow(i, 'from', e.target.value)} />
                <span style={{ color: 'var(--muted)' }}>—</span>
                <input className="input mono" type="time" value={w.to || ''}
                  style={{ width: 110 }}
                  onChange={(e) => updateWindow(i, 'to', e.target.value)} />
                <button className="icon-btn danger" onClick={() => removeWindow(i)}>✕</button>
              </div>
            ))}
            <button className="btn ghost sm" onClick={addWindow}>＋ Aralık Ekle</button>
          </div>
        </div>
        <div className="modal-foot">
          <button className="btn ghost" onClick={onClose}>İptal</button>
          <button className="btn accent" onClick={save}>Kaydet</button>
        </div>
      </div>
    </div>
  );
}

// ───────── Key (button) ─────────
function KeyButton({ btn, idx, selected, onClick }) {
  const assigned = btn.action_type !== ACTION_NONE;
  const label = btn.label || (assigned ? ACTION_LABELS[btn.action_type] : '');
  return (
    <div
      className={`key ${assigned ? 'assigned' : 'empty'} ${selected ? 'selected' : ''}`}
      onClick={onClick}
    >
      <span className="key-num">K{idx + 1}</span>
      <span className="key-glyph">{ACTION_GLYPHS[btn.action_type]}</span>
      {label && <span className="key-label">{label}</span>}
      {assigned && <span className="key-type">{ACTION_SHORT[btn.action_type]}</span>}
    </div>
  );
}

// ───────── Encoder ─────────
function Encoder({ enc, idx, selection, onPick }) {
  const isSel = (sub) => selection && selection.kind === 'encoder' && selection.index === idx && selection.sub === sub;
  const valOf = (b) => b.label || (b.action_type !== ACTION_NONE ? ACTION_LABELS[b.action_type] : '—');
  const cls = (b) => b.action_type !== ACTION_NONE ? 'assigned' : 'empty';
  return (
    <div className="encoder">
      <div className="enc-name">ENC {idx + 1}</div>
      <div className={`enc-knob ${isSel('push') ? 'selected-push' : ''}`} onClick={() => onPick('push')} title="Push" />
      <div className="enc-actions">
        <button className={`enc-btn ${cls(enc.ccw)} ${isSel('ccw') ? 'selected' : ''}`} onClick={() => onPick('ccw')}>
          <span className="label">◄ CCW</span>
          <span className="val">{valOf(enc.ccw)}</span>
        </button>
        <button className={`enc-btn ${cls(enc.push)} ${isSel('push') ? 'selected' : ''}`} onClick={() => onPick('push')}>
          <span className="label">● PUSH</span>
          <span className="val">{valOf(enc.push)}</span>
        </button>
        <button className={`enc-btn ${cls(enc.cw)} ${isSel('cw') ? 'selected' : ''}`} onClick={() => onPick('cw')}>
          <span className="label">CW ►</span>
          <span className="val">{valOf(enc.cw)}</span>
        </button>
      </div>
    </div>
  );
}

// ───────── OLED preview ─────────
function OledPreview({ mode, customText, profileName }) {
  const [, setTick] = useState(0);
  const [volume, setVolume] = useState(-1);
  useEffect(() => { const i = setInterval(() => setTick((t) => t + 1), 1000); return () => clearInterval(i); }, []);
  useEffect(() => {
    if (mode !== DISPLAY_VOLUME || !bridge || !bridge.get_system_volume) return;
    const tick = () => bridge.get_system_volume((v) => setVolume(v));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [mode]);
  const now = new Date();
  const time = now.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
  const date = now.toLocaleDateString('tr-TR');
  const isMarket = mode === DISPLAY_CRYPTO || mode === DISPLAY_CURRENCY || mode === DISPLAY_STOCK;

  return (
    <div className="oled-frame">
      <div className="oled-screen">
        <div className="scan" />
        {mode === DISPLAY_CLOCK && (
          <>
            <div className="oled-clock-time">{time}</div>
            <div className="oled-clock-date">{date}</div>
          </>
        )}
        {mode === DISPLAY_PROFILE && (
          <>
            <div className="oled-label">AKTİF PROFİL</div>
            <div className="oled-big">{profileName || '—'}</div>
          </>
        )}
        {mode === DISPLAY_VOLUME && (
          <>
            <div className="oled-label">SES SEVİYESİ</div>
            <div className="oled-bar">
              <div className="oled-bar-fill" style={{ width: `${Math.max(0, volume)}%` }} />
            </div>
            <div className="oled-bar-pct">{volume < 0 ? '?%' : `${volume}%`}</div>
          </>
        )}
        {mode === DISPLAY_CUSTOM && (
          <div className="oled-custom">{customText || '(boş)'}</div>
        )}
        {isMarket && (
          <>
            <div className="oled-label">
              {mode === DISPLAY_CRYPTO ? 'KRİPTO' : mode === DISPLAY_CURRENCY ? 'DÖVİZ' : 'HİSSE'}
            </div>
            <div className="oled-big" style={{ fontSize: 18, color: '#8aa6c0' }}>
              canlı veri
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ───────── Module card ─────────
function ModuleCard({ mod, idx, total }) {
  const { state, setState, updateActiveProfile, activeProfile } = useStore();
  const sel = state.selection;

  const select = (s) => setState((st) => ({ ...st, selection: s }));

  const moveUp = () => {
    if (idx === 0) return;
    updateActiveProfile((p) => { [p.modules[idx - 1], p.modules[idx]] = [p.modules[idx], p.modules[idx - 1]]; });
  };
  const moveDown = () => {
    if (idx >= total - 1) return;
    updateActiveProfile((p) => { [p.modules[idx + 1], p.modules[idx]] = [p.modules[idx], p.modules[idx + 1]]; });
  };
  const removeModule = () => {
    if (!confirm(`'${mod.name}' modülünü kaldır?`)) return;
    updateActiveProfile((p) => { p.modules.splice(idx, 1); });
    if (sel && sel.moduleId === mod.module_id) setState((st) => ({ ...st, selection: null }));
  };

  // Mirror the physical layout: 6 buttons → 2 rows of 3, 4 → 2x2,
  // 8 → 2x4. For other counts, pick the columns that minimise empty
  // cells in a roughly-square grid.
  const cols = (() => {
    const n = mod.button_count;
    if (n <= 1) return 1;
    if (n === 2) return 2;
    if (n === 3) return 3;
    if (n === 4) return 2;
    if (n <= 6) return 3;
    return 4;
  })();
  const keyGridStyle = { gridTemplateColumns: `repeat(${cols}, minmax(72px, 92px))`, justifyContent: 'center' };

  const isKeySel = (i) => sel && sel.moduleId === mod.module_id && sel.kind === 'button' && sel.index === i;
  const isDispSel = sel && sel.moduleId === mod.module_id && sel.kind === 'display';

  return (
    <div className="module">
      <div className="module-head">
        <div className={`module-icon ${mod.module_type === 'main' ? 'main' : ''}`}>
          {mod.module_type === 'main' ? '◉' : '◇'}
        </div>
        <div>
          <div className="module-title">{mod.name}</div>
          <div className="module-meta">
            <span className="pill">{mod.button_count} btn</span>
            {mod.encoder_count > 0 && <span className="pill">{mod.encoder_count} enc</span>}
            {mod.has_display && <span className="pill">OLED</span>}
            <span style={{ marginLeft: 6 }}>{mod.module_type === 'main' ? 'master' : 'slave'}</span>
          </div>
        </div>
        <div className="grow" />
        <button className="icon-btn" title="Yukarı taşı" onClick={moveUp} disabled={idx === 0}>▲</button>
        <button className="icon-btn" title="Aşağı taşı" onClick={moveDown} disabled={idx >= total - 1}>▼</button>
        <button className="icon-btn danger" title="Kaldır" onClick={removeModule}>✕</button>
      </div>
      <div className="module-body">
        {/* Cihazdaki fiziksel düzeni yansıt: ekran üstte, butonlar altta. */}
        {mod.has_display && (
          <div className="oled-row" style={{ justifyContent: 'center' }}>
            <OledPreview
              mode={mod.display_mode}
              customText={mod.display_custom_text}
              profileName={activeProfile?.name}
            />
            <div className="oled-controls">
              <span className="lbl">128×64 OLED</span>
              <button className={`btn ${isDispSel ? 'primary' : ''}`}
                onClick={() => select({ moduleId: mod.module_id, kind: 'display' })}>
                ⚙ Ekran Ayarları
              </button>
              <span className="lbl" style={{ fontFamily: 'var(--font-mono)' }}>
                mode: {mod.display_mode}
              </span>
            </div>
          </div>
        )}

        {mod.button_count > 0 && (
          <div className="keys" style={keyGridStyle}>
            {mod.buttons.map((b, i) => (
              <KeyButton key={i} btn={b} idx={i} selected={isKeySel(i)}
                onClick={() => select({ moduleId: mod.module_id, kind: 'button', index: i })} />
            ))}
          </div>
        )}

        {mod.encoder_count > 0 && (
          <div className="encoders-row" style={{ justifyContent: 'center' }}>
            {mod.encoders.map((e, i) => (
              <Encoder key={i} enc={e} idx={i}
                selection={sel && sel.moduleId === mod.module_id ? sel : null}
                onPick={(sub) => select({ moduleId: mod.module_id, kind: 'encoder', index: i, sub })} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ───────── Inspector body parts ─────────
function ButtonInspector({ moduleId, index, sub }) {
  const { updateActiveProfile, activeProfile } = useStore();
  const mod = activeProfile.modules.find((m) => m.module_id === moduleId);
  if (!mod) return null;

  const cfg = sub
    ? mod.encoders[index][sub]
    : mod.buttons[index];

  const setCfg = (mut) => {
    updateActiveProfile((p) => {
      const m = p.modules.find((mm) => mm.module_id === moduleId);
      if (!m) return;
      const target = sub ? m.encoders[index][sub] : m.buttons[index];
      mut(target);
    });
  };

  const types = [ACTION_NONE, ACTION_SHORTCUT, ACTION_MEDIA, ACTION_APP, ACTION_MACRO, ACTION_PROFILE_SWITCH];

  return (
    <>
      <div className="field">
        <label>Etiket</label>
        <input className="input" value={cfg.label}
          placeholder="Tuş üstünde görünecek metin"
          onChange={(e) => setCfg((c) => { c.label = e.target.value; })} />
      </div>

      <div className="field">
        <label>Eylem Tipi</label>
        <div className="action-grid">
          {types.map((t) => (
            <button key={t}
              className={`action-card ${cfg.action_type === t ? 'active' : ''}`}
              onClick={() => setCfg((c) => { c.action_type = t; c.action_data = {}; })}>
              <span className="ic">{ACTION_GLYPHS[t]}</span>
              {ACTION_LABELS[t]}
            </button>
          ))}
        </div>
      </div>

      {cfg.action_type === ACTION_SHORTCUT && <ShortcutEditor cfg={cfg} setCfg={setCfg} />}
      {cfg.action_type === ACTION_MEDIA && <MediaEditor cfg={cfg} setCfg={setCfg} />}
      {cfg.action_type === ACTION_APP && <AppEditor cfg={cfg} setCfg={setCfg} />}
      {cfg.action_type === ACTION_MACRO && <MacroEditor cfg={cfg} setCfg={setCfg} />}
      {cfg.action_type === ACTION_PROFILE_SWITCH && <ProfileSwitchEditor cfg={cfg} setCfg={setCfg} />}
    </>
  );
}

function ShortcutEditor({ cfg, setCfg }) {
  const [armed, setArmed] = useState(false);

  useEffect(() => {
    if (!armed) return;
    const handler = (e) => {
      if ([16, 17, 18, 91].includes(e.keyCode)) return;
      e.preventDefault();
      const parts = [];
      if (e.ctrlKey) parts.push('ctrl');
      if (e.altKey) parts.push('alt');
      if (e.shiftKey) parts.push('shift');
      if (e.metaKey) parts.push('win');
      const map = { 27: 'esc', 13: 'enter', 9: 'tab', 8: 'backspace', 32: 'space', 37: 'left', 38: 'up', 39: 'right', 40: 'down', 46: 'delete' };
      let name = map[e.keyCode];
      if (!name && e.key.length === 1) name = e.key.toLowerCase();
      else if (!name && e.key.startsWith('F')) name = e.key.toLowerCase();
      if (name) parts.push(name);
      if (parts.length) setCfg((c) => { c.action_data.keys = parts.join('+'); });
      setArmed(false);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [armed, setCfg]);

  const keys = cfg.action_data.keys || '';
  const parts = keys ? keys.split('+') : [];

  return (
    <>
      <div className="field">
        <label>Kısayol</label>
        <div className={`capture-zone ${armed ? 'armed' : ''}`} onClick={() => setArmed(true)}>
          {armed ? (
            <>Şimdi tuşlara basın…<div className="hint">esc → iptal</div></>
          ) : (
            <>
              {parts.length ? (
                <div className="shortcut-display">
                  {parts.map((p, i) => <span key={i} className="kbd">{p}</span>)}
                </div>
              ) : (
                <>Yakalamak için tıklayın<div className="hint">veya alttaki kutuya yazın</div></>
              )}
            </>
          )}
        </div>
      </div>
      <div className="field">
        <label>Manuel Giriş</label>
        <input className="input mono" value={keys}
          placeholder="ctrl+shift+esc"
          onChange={(e) => setCfg((c) => { c.action_data.keys = e.target.value; })} />
      </div>
    </>
  );
}

function MediaEditor({ cfg, setCfg }) {
  return (
    <div className="field">
      <label>Medya Eylemi</label>
      <select className="select" value={cfg.action_data.action || ''}
        onChange={(e) => setCfg((c) => { c.action_data.action = e.target.value; })}>
        <option value="">— Seçin —</option>
        {Object.entries(MEDIA_ACTIONS).map(([k, v]) => (
          <option key={k} value={k}>{v}</option>
        ))}
      </select>
    </div>
  );
}

function AppPickerModal({ onClose, onPick }) {
  const [apps, setApps] = useState([]);
  const [filter, setFilter] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!bridge || !bridge.list_installed_apps) {
      setLoading(false);
      return;
    }
    bridge.list_installed_apps((js) => {
      try { setApps(JSON.parse(js) || []); }
      catch { setApps([]); }
      setLoading(false);
    });
  }, []);

  const f = filter.trim().toLowerCase();
  const filtered = f
    ? apps.filter((a) => a.name.toLowerCase().includes(f))
    : apps;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 520, maxHeight: '80vh', display: 'flex', flexDirection: 'column' }}
        onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div className="ttl">Yüklü Uygulamalar</div>
          <button className="icon-btn" onClick={onClose}>✕</button>
        </div>
        <div style={{ padding: '12px 20px 8px' }}>
          <input className="input" autoFocus placeholder="Ara…"
            value={filter} onChange={(e) => setFilter(e.target.value)} />
        </div>
        <div style={{ overflowY: 'auto', padding: '0 12px 12px', flex: 1 }}>
          {loading && <div style={{ padding: 20, color: 'var(--muted)' }}>Yükleniyor…</div>}
          {!loading && filtered.length === 0 && (
            <div style={{ padding: 20, color: 'var(--muted)', fontSize: 13 }}>
              Eşleşen uygulama yok.
            </div>
          )}
          {filtered.slice(0, 200).map((a) => (
            <div key={a.path}
              onClick={() => { onPick(a); onClose(); }}
              style={{
                padding: '8px 10px', borderRadius: 6, cursor: 'pointer',
                fontSize: 13, color: 'var(--ink-2)',
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-2)'}
              onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}>
              <div style={{ fontWeight: 500 }}>{a.name}</div>
              <div style={{ fontSize: 10, color: 'var(--muted)', fontFamily: 'var(--font-mono)',
                            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {a.path}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function AppEditor({ cfg, setCfg }) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const pickFile = () => {
    if (!bridge) return;
    bridge.pick_executable((path) => {
      if (path) setCfg((c) => { c.action_data.path = path; });
    });
  };
  return (
    <>
      <div className="field">
        <label>Uygulama</label>
        <div className="row">
          <button className="btn grow" onClick={() => setPickerOpen(true)}
            title="Yüklü uygulamalar arasından seç">
            📋 Listeden Seç
          </button>
          {bridge && (
            <button className="btn sm" onClick={pickFile} title="Manuel dosya seç">…</button>
          )}
        </div>
      </div>
      <div className="field">
        <label>Yol</label>
        <input className="input mono" value={cfg.action_data.path || ''}
          placeholder="C:\\Program Files\\Spotify\\Spotify.exe"
          onChange={(e) => setCfg((c) => { c.action_data.path = e.target.value; })} />
      </div>
      <div className="field">
        <label>Argümanlar (opsiyonel)</label>
        <input className="input mono" value={cfg.action_data.args || ''}
          placeholder="--minimized"
          onChange={(e) => setCfg((c) => { c.action_data.args = e.target.value; })} />
      </div>
      {pickerOpen && (
        <AppPickerModal onClose={() => setPickerOpen(false)}
          onPick={(a) => setCfg((c) => { c.action_data.path = a.path; })} />
      )}
    </>
  );
}

function MacroEditor({ cfg, setCfg }) {
  const [recording, setRecording] = useState(false);
  const lastTimeRef = useRef(0);

  useEffect(() => {
    if (!recording) return;
    lastTimeRef.current = Date.now();
    const handler = (e) => {
      // Stop on Esc with no modifiers
      if (e.keyCode === 27 && !e.ctrlKey && !e.altKey && !e.shiftKey && !e.metaKey) {
        setRecording(false);
        e.preventDefault();
        return;
      }
      // Skip pure modifier presses
      if ([16, 17, 18, 91].includes(e.keyCode)) return;
      e.preventDefault();
      const parts = [];
      if (e.ctrlKey) parts.push('ctrl');
      if (e.altKey) parts.push('alt');
      if (e.shiftKey) parts.push('shift');
      if (e.metaKey) parts.push('win');
      const map = {
        13: 'enter', 9: 'tab', 8: 'backspace', 32: 'space',
        37: 'left', 38: 'up', 39: 'right', 40: 'down',
        46: 'delete', 36: 'home', 35: 'end', 33: 'pageup', 34: 'pagedown',
      };
      let name = map[e.keyCode];
      if (!name && e.key.length === 1) name = e.key.toLowerCase();
      else if (!name && e.key.startsWith('F')) name = e.key.toLowerCase();
      if (!name) return;
      parts.push(name);

      const now = Date.now();
      const gap = now - lastTimeRef.current;
      lastTimeRef.current = now;

      setCfg((c) => {
        let seq = (c.action_data.sequence || '').trimEnd();
        // Insert wait line if there's been a noticeable pause (>250ms)
        if (seq && gap > 250 && gap < 5000) {
          seq += '\nwait:' + Math.round(gap);
        }
        seq += (seq ? '\n' : '') + parts.join('+');
        c.action_data.sequence = seq;
      });
    };
    window.addEventListener('keydown', handler, true);
    return () => window.removeEventListener('keydown', handler, true);
  }, [recording, setCfg]);

  const clear = () => setCfg((c) => { c.action_data.sequence = ''; });

  return (
    <>
      <div className="field">
        <label>Makro Dizisi</label>
        <div className={`capture-zone ${recording ? 'armed' : ''}`}
          style={{ marginBottom: 8 }}
          onClick={() => setRecording((r) => !r)}>
          {recording ? (
            <>● Kayıt yapılıyor — tuş kombinasyonlarına basın
              <div className="hint">esc → bitir</div></>
          ) : (
            <>⏺ Kaydet — tıklayın, sonra tuşlara basın
              <div className="hint">eski içerik korunur, üstüne eklenir</div></>
          )}
        </div>
        <textarea className="textarea" value={cfg.action_data.sequence || ''}
          placeholder={'ctrl+c\nwait:200\nctrl+v\ntype:Hello'}
          onChange={(e) => setCfg((c) => { c.action_data.sequence = e.target.value; })} />
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      marginTop: 4 }}>
          <div style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}>
            Desteklenen: tuş kombinasyonları, wait:ms, type:metin
          </div>
          <button className="btn ghost sm" onClick={clear}>Temizle</button>
        </div>
      </div>
    </>
  );
}

function ProfileSwitchEditor({ cfg, setCfg }) {
  const { state } = useStore();
  return (
    <div className="field">
      <label>Hedef Profil</label>
      <select className="select" value={cfg.action_data.profile_id || ''}
        onChange={(e) => setCfg((c) => { c.action_data.profile_id = e.target.value; })}>
        <option value="">— Seçin —</option>
        {state.profiles.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
    </div>
  );
}

function SymbolPickerModal({ mode, onClose, onPick }) {
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!bridge || !bridge.list_market_symbols) {
      setLoading(false);
      return;
    }
    bridge.list_market_symbols(mode, (js) => {
      try { setItems(JSON.parse(js) || []); }
      catch { setItems([]); }
      setLoading(false);
    });
  }, [mode]);

  const f = filter.trim().toLowerCase();
  const filtered = f
    ? items.filter((it) =>
        it.symbol.toLowerCase().includes(f) || it.name.toLowerCase().includes(f))
    : items;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 480, maxHeight: '80vh', display: 'flex', flexDirection: 'column' }}
        onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div className="ttl">Sembol Seç</div>
          <button className="icon-btn" onClick={onClose}>✕</button>
        </div>
        <div style={{ padding: '12px 20px 8px' }}>
          <input className="input" autoFocus placeholder="Ara…"
            value={filter} onChange={(e) => setFilter(e.target.value)} />
        </div>
        <div style={{ overflowY: 'auto', padding: '0 12px 12px', flex: 1 }}>
          {loading && <div style={{ padding: 20, color: 'var(--muted)' }}>Yükleniyor…</div>}
          {!loading && filtered.length === 0 && (
            <div style={{ padding: 20, color: 'var(--muted)', fontSize: 13 }}>
              Eşleşme yok. Manuel olarak yazabilirsin.
            </div>
          )}
          {filtered.map((it) => (
            <div key={it.symbol}
              onClick={() => { onPick(it.symbol); onClose(); }}
              style={{ padding: '8px 10px', borderRadius: 6, cursor: 'pointer', fontSize: 13 }}
              onMouseEnter={(e) => e.currentTarget.style.background = 'var(--bg-2)'}
              onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}>
              <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, marginRight: 10 }}>{it.symbol}</span>
              <span style={{ color: 'var(--muted)' }}>{it.name}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function DisplayInspector({ moduleId }) {
  const { updateActiveProfile, activeProfile } = useStore();
  const mod = activeProfile.modules.find((m) => m.module_id === moduleId);
  const [pickerOpen, setPickerOpen] = useState(false);
  if (!mod) return null;
  const isMarket = (
    mod.display_mode === DISPLAY_CRYPTO ||
    mod.display_mode === DISPLAY_CURRENCY ||
    mod.display_mode === DISPLAY_STOCK
  );

  const symbols = mod.display_symbols || [];

  const addSymbol = (s) => {
    const sym = (s || '').trim();
    if (!sym) return;
    updateActiveProfile((p) => {
      const m = p.modules.find((mm) => mm.module_id === moduleId);
      if (!m) return;
      if (!Array.isArray(m.display_symbols)) m.display_symbols = [];
      if (!m.display_symbols.includes(sym)) m.display_symbols.push(sym);
    });
  };
  const removeSymbol = (i) => {
    updateActiveProfile((p) => {
      const m = p.modules.find((mm) => mm.module_id === moduleId);
      if (!m || !Array.isArray(m.display_symbols)) return;
      m.display_symbols.splice(i, 1);
    });
  };

  return (
    <>
      <div className="field">
        <label>Gösterim Modu</label>
        <div className="action-grid">
          {Object.entries(DISPLAY_MODES).map(([k, v]) => (
            <button key={k}
              className={`action-card ${mod.display_mode === k ? 'active' : ''}`}
              onClick={() => updateActiveProfile((p) => {
                const m = p.modules.find((mm) => mm.module_id === moduleId); if (m) m.display_mode = k;
              })}>
              <span className="ic">▦</span>{v}
            </button>
          ))}
        </div>
      </div>

      {mod.display_mode === DISPLAY_CUSTOM && (
        <div className="field">
          <label>Özel Metin</label>
          <input className="input" value={mod.display_custom_text || ''}
            onChange={(e) => updateActiveProfile((p) => {
              const m = p.modules.find((mm) => mm.module_id === moduleId); if (m) m.display_custom_text = e.target.value;
            })} />
        </div>
      )}

      {isMarket && (
        <>
          <div className="field">
            <label>Semboller (sırayla döner)</label>
            {symbols.length === 0 && (
              <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 6 }}>
                Henüz sembol eklenmemiş.
              </div>
            )}
            {symbols.map((s, i) => (
              <div key={i} className="row" style={{ marginBottom: 4, gap: 6 }}>
                <input className="input mono grow" value={s}
                  onChange={(e) => updateActiveProfile((p) => {
                    const m = p.modules.find((mm) => mm.module_id === moduleId);
                    if (m) m.display_symbols[i] = e.target.value;
                  })} />
                <button className="icon-btn danger" onClick={() => removeSymbol(i)}>✕</button>
              </div>
            ))}
            <div className="row" style={{ gap: 6, marginTop: 6 }}>
              <button className="btn grow" onClick={() => setPickerOpen(true)}>📋 Listeden Ekle</button>
              <button className="btn ghost sm" onClick={() => addSymbol('')}>＋ Boş satır</button>
            </div>
            <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4, fontFamily: 'var(--font-mono)' }}>
              {SYMBOL_HINTS[mod.display_mode] || ''}
            </div>
          </div>

          {symbols.length > 1 && (
            <div className="field">
              <label>Geçiş aralığı (saniye)</label>
              <input className="input mono" type="number" min={2} max={300}
                value={mod.display_rotate_seconds ?? 5}
                onChange={(e) => updateActiveProfile((p) => {
                  const m = p.modules.find((mm) => mm.module_id === moduleId);
                  if (m) m.display_rotate_seconds = Math.max(2, +e.target.value || 5);
                })} />
            </div>
          )}
        </>
      )}

      <div className="field">
        <label className="check" style={{ cursor: 'pointer' }}>
          <input type="checkbox" checked={!!mod.display_invert}
            onChange={(e) => updateActiveProfile((p) => {
              const m = p.modules.find((mm) => mm.module_id === moduleId);
              if (m) m.display_invert = e.target.checked;
            })} />
          <span className="box" /> Renkleri ters çevir (siyah ↔ beyaz)
        </label>
        <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4 }}>
          OLED tek renk olduğu için tam renk seçimi mümkün değil — sadece ters çevrilebilir.
        </div>
      </div>

      <div className="field">
        <label>Modül Adı</label>
        <input className="input" value={mod.name}
          onChange={(e) => updateActiveProfile((p) => {
            const m = p.modules.find((mm) => mm.module_id === moduleId); if (m) m.name = e.target.value;
          })} />
      </div>

      {pickerOpen && (
        <SymbolPickerModal mode={mod.display_mode} onClose={() => setPickerOpen(false)}
          onPick={(s) => addSymbol(s)} />
      )}
    </>
  );
}

// ───────── Inspector ─────────
function Inspector() {
  const { state, activeProfile } = useStore();
  const sel = state.selection;

  if (!sel) {
    return (
      <aside className="inspector">
        <div className="inspector-empty">
          <div>
            <div className="glyph">◰</div>
            Düzenlemek için bir tuş, encoder<br />veya OLED ekran seçin.
          </div>
        </div>
      </aside>
    );
  }

  const mod = activeProfile.modules.find((m) => m.module_id === sel.moduleId);
  if (!mod) return <aside className="inspector"><div className="inspector-empty">Modül bulunamadı</div></aside>;

  let where = '';
  let what = '';
  if (sel.kind === 'button') {
    where = `${activeProfile.name} · ${mod.name}`;
    what = `Tuş K${sel.index + 1}`;
  } else if (sel.kind === 'encoder') {
    where = `${activeProfile.name} · ${mod.name} · Encoder ${sel.index + 1}`;
    const subLabel = { cw: 'Saat Yönü (CW)', ccw: 'Ters Yön (CCW)', push: 'Basma (Push)' };
    what = subLabel[sel.sub];
  } else if (sel.kind === 'display') {
    where = `${activeProfile.name} · ${mod.name}`;
    what = 'OLED Ekran';
  }

  return (
    <aside className="inspector">
      <div className="inspector-head">
        <div className="crumbs">
          <div className="where">{where}</div>
          <div className="what">{what}</div>
        </div>
      </div>
      <div className="inspector-body">
        {sel.kind === 'button' && <ButtonInspector moduleId={sel.moduleId} index={sel.index} />}
        {sel.kind === 'encoder' && (
          <ButtonInspector moduleId={sel.moduleId} index={sel.index} sub={sel.sub} />
        )}
        {sel.kind === 'display' && <DisplayInspector moduleId={sel.moduleId} />}
      </div>
    </aside>
  );
}

// ───────── Modals ─────────
function AddModuleModal({ onClose }) {
  const { updateActiveProfile, showToast } = useStore();
  const [name, setName] = useState('');
  const [btns, setBtns] = useState(4);
  const [encs, setEncs] = useState(0);
  const [oled, setOled] = useState(false);

  const submit = () => {
    const mod = window.MP.newModule({
      name: name.trim() || 'Yeni Modül',
      button_count: btns,
      encoder_count: encs,
      has_display: oled,
    });
    updateActiveProfile((p) => { p.modules.push(mod); });
    showToast('Modül eklendi');
    onClose();
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div className="ttl">Modül Ekle</div>
          <button className="icon-btn" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          <div className="field"><label>İsim</label>
            <input className="input" placeholder="ör. Sağ Modül" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
          </div>
          <div className="row" style={{ gap: 12 }}>
            <div className="field grow"><label>Buton sayısı</label>
              <input className="input mono" type="number" min={0} max={32} value={btns} onChange={(e) => setBtns(+e.target.value)} />
            </div>
            <div className="field grow"><label>Encoder sayısı</label>
              <input className="input mono" type="number" min={0} max={8} value={encs} onChange={(e) => setEncs(+e.target.value)} />
            </div>
          </div>
          <label className="check">
            <input type="checkbox" checked={oled} onChange={(e) => setOled(e.target.checked)} />
            <span className="box" /> OLED ekran var
          </label>
        </div>
        <div className="modal-foot">
          <button className="btn ghost" onClick={onClose}>İptal</button>
          <button className="btn accent" onClick={submit}>Ekle</button>
        </div>
      </div>
    </div>
  );
}

function FlashModal({ onClose }) {
  const { state } = useStore();
  const [logs, setLogs] = useState([]);
  const [progress, setProgress] = useState(0);
  const [running, setRunning] = useState(false);
  const [done, setDone] = useState(false);
  const [success, setSuccess] = useState(true);

  // Subscribe to bridge flash signals
  useEffect(() => {
    if (!bridge) return;
    const onLog = (line) => setLogs((L) => [...L, line]);
    const onProgress = (pct) => setProgress(pct);
    const onDone = (ok, msg) => {
      setRunning(false); setDone(true); setSuccess(ok); setProgress(100);
      if (msg) setLogs((L) => [...L, msg]);
    };
    bridge.flash_log.connect(onLog);
    bridge.flash_progress.connect(onProgress);
    bridge.flash_done.connect(onDone);
    return () => {
      try {
        bridge.flash_log.disconnect(onLog);
        bridge.flash_progress.disconnect(onProgress);
        bridge.flash_done.disconnect(onDone);
      } catch {}
    };
  }, []);

  const startSimulated = (fromGithub) => {
    setRunning(true); setProgress(0); setLogs([]); setDone(false);
    const lines = fromGithub ? [
      'GitHub Releases sorgulanıyor…',
      'Son sürüm bulundu: v1.4.2',
      'Firmware indiriliyor (482 KB)…',
      `Port: ${state.selectedPort} @ 115200`,
      'esptool.py --chip esp32c3 --port ' + state.selectedPort,
      'Connecting......',
      'Chip is ESP32-C3 (revision v0.4)',
      'Erasing flash (this may take a while)...',
      'Writing at 0x00000000... (10 %)',
      'Writing at 0x00010000... (35 %)',
      'Writing at 0x00020000... (65 %)',
      'Writing at 0x00030000... (88 %)',
      'Writing at 0x00040000... (100 %)',
      'Hash of data verified.',
      'Hard resetting via RTS pin...',
    ] : [
      'Yerel firmware seçildi',
      `Port: ${state.selectedPort}`,
      'Connecting......',
      'Writing... (50 %)',
      'Writing... (100 %)',
      'Hash of data verified.',
      'Done.',
    ];
    let i = 0;
    const id = setInterval(() => {
      if (i >= lines.length) {
        clearInterval(id);
        setRunning(false); setDone(true); setSuccess(true); setProgress(100);
        return;
      }
      setLogs((L) => [...L, lines[i]]);
      setProgress(Math.round(((i + 1) / lines.length) * 100));
      i++;
    }, 350);
  };

  const startGithub = () => {
    if (!bridge) return startSimulated(true);
    setRunning(true); setProgress(0); setLogs([]); setDone(false);
    bridge.flash_github(state.selectedPort);
  };

  const startLocal = () => {
    if (!bridge) return startSimulated(false);
    bridge.pick_firmware_file((path) => {
      if (!path) return;
      setRunning(true); setProgress(0); setLogs([]); setDone(false);
      bridge.flash_local(state.selectedPort, path);
    });
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 540 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div className="ttl">⚡ Firmware Güncelle</div>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--muted)' }}>
            {state.selectedPort}
          </span>
          <button className="icon-btn" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          <div className="row" style={{ gap: 8, marginBottom: 12 }}>
            <button className="btn accent grow" disabled={running} onClick={startGithub}>
              🌐 GitHub'dan İndir & Flash
            </button>
            <button className="btn grow" disabled={running} onClick={startLocal}>
              📁 Yerel .bin Seç
            </button>
          </div>
          <div className="progress-track"><div className="progress-fill" style={{ width: progress + '%' }} /></div>
          <div className="console">
            {logs.map((l, i) => (
              <div key={i} className={l.includes('verified') || l.includes('Done') || l.includes('başarı') ? 'ok' : ''}>$ {l}</div>
            ))}
            {running && <div>▌</div>}
            {done && (
              success
                ? <div className="ok">{'\n'}✓ Firmware başarıyla yüklendi.</div>
                : <div className="err">{'\n'}✗ Firmware yüklenemedi.</div>
            )}
          </div>
        </div>
        <div className="modal-foot">
          <button className="btn ghost" onClick={onClose}>{done ? 'Kapat' : 'İptal'}</button>
        </div>
      </div>
    </div>
  );
}

// ───────── Canvas ─────────
function Canvas({ onAddModule }) {
  const { activeProfile } = useStore();
  if (!activeProfile) return null;

  return (
    <main className="canvas">
      <div className="canvas-head">
        <div>
          <h1>{activeProfile.name}</h1>
          <div className="sub">{activeProfile.modules.length} modül · {activeProfile.modules.reduce((s, m) => s + m.button_count, 0)} tuş</div>
        </div>
        <button className="btn" onClick={onAddModule}>＋ Modül</button>
      </div>

      {activeProfile.modules.length === 0 ? (
        <div className="empty-state">
          <h2>Bu profil boş</h2>
          <p>Bir modül ekleyerek başlayın veya bağlı cihazdan otomatik algılayın.</p>
          <button className="btn accent" onClick={onAddModule}>＋ Modül Ekle</button>
        </div>
      ) : (
        <div className="modules-stack">
          {activeProfile.modules.map((m, i) => (
            <ModuleCard key={m.module_id} mod={m} idx={i} total={activeProfile.modules.length} />
          ))}
        </div>
      )}
    </main>
  );
}

// ───────── Footer ─────────
function Footer() {
  const { state, activeProfile, showToast } = useStore();
  const totalKeys = activeProfile?.modules.reduce((s, m) => s + m.button_count, 0) || 0;
  const totalEnc = activeProfile?.modules.reduce((s, m) => s + m.encoder_count, 0) || 0;
  const [autostart, setAutostart] = useState(false);

  useEffect(() => {
    if (!bridge || !bridge.autostart_enabled) return;
    bridge.autostart_enabled((on) => setAutostart(!!on));
  }, []);

  const toggleAutostart = (e) => {
    const want = e.target.checked;
    if (!bridge || !bridge.autostart_set) return;
    bridge.autostart_set(want, (ok) => {
      if (ok) {
        setAutostart(want);
        showToast(want ? 'Başlangıçta açılacak' : 'Başlangıçta kapalı');
      } else {
        showToast('Yalnızca .exe sürümünde çalışır');
      }
    });
  };

  return (
    <div className="footer">
      <span>profile <span style={{ color: 'var(--ink)' }}>"{activeProfile?.name}"</span></span>
      <span>{totalKeys} keys · {totalEnc} encoders</span>
      <label style={{ display: 'flex', alignItems: 'center', gap: 5, cursor: 'pointer' }}
        title="Windows başlarken arka planda otomatik aç">
        <input type="checkbox" checked={autostart} onChange={toggleAutostart}
          style={{ margin: 0, cursor: 'pointer' }} />
        autostart
      </label>
      <span className="grow" />
      <span>baud 115200</span>
      <span>{state.connected ? <span className="ok">● connected</span> : '○ offline'}</span>
      <span>{new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })}</span>
    </div>
  );
}

// ───────── Connection state mirror ─────────
// Bridge owns the actual serial state (auto-connect, retry, etc.);
// this component just mirrors it into React state so the status pill
// and "Cihaza Gönder" button can react.
function ConnectionWatcher() {
  const { setState } = useStore();

  useEffect(() => {
    if (!bridge) return;

    const onChange = (connected, port) => {
      setState((s) => ({
        ...s,
        connected: !!connected,
        selectedPort: port || s.selectedPort,
      }));
    };

    if (bridge.device_connection_changed) {
      bridge.device_connection_changed.connect(onChange);
    }

    // Poll snapshot — signals can race with React mount, and a
    // periodic re-check here costs almost nothing and guarantees
    // the topbar matches reality even if a signal got dropped.
    const poll = () => {
      if (bridge.get_connection_state) {
        bridge.get_connection_state((js) => {
          try {
            const s = JSON.parse(js);
            if (s) onChange(!!s.connected, s.port || '');
          } catch {}
        });
      }
    };
    poll();
    const id = setInterval(poll, 3000);

    return () => {
      clearInterval(id);
      try { bridge.device_connection_changed && bridge.device_connection_changed.disconnect(onChange); } catch {}
    };
  }, [setState]);

  return null;
}

// ───────── Active profile cache + remote button events ─────────
// ESP32-C3 can't act as a USB-HID device, so the firmware just sends
// raw button_event JSON over CDC. The Python bridge looks up the
// configured action in the active profile and executes it locally.
// We need to keep the bridge's lookup table in sync with whatever the
// user is editing — this component handles both halves of that.
function ActionRouter() {
  const { state, setState, activeProfile, showToast } = useStore();

  // Keep the bridge's cached profile in sync with the active one so
  // button presses dispatch immediately. Also auto-push the display
  // payload to the device — debounced 250ms so rapid edits in the
  // inspector don't spam serial. This makes "Cihaza Gönder" optional;
  // the OLED follows whatever the active profile is set to.
  useEffect(() => {
    if (!bridge || !activeProfile) return;
    const payload = JSON.stringify(activeProfile);
    if (bridge.cache_profile) bridge.cache_profile(payload);
    if (!bridge.send_config) return;
    const t = setTimeout(() => {
      bridge.send_config(payload, () => {});
    }, 250);
    return () => clearTimeout(t);
  }, [activeProfile]);

  // Push the full profile list to the bridge so it can match
  // foreground-app / time triggers without polling React.
  useEffect(() => {
    if (!bridge || !bridge.cache_profiles) return;
    bridge.cache_profiles(JSON.stringify(state.profiles));
  }, [state.profiles]);

  // profile_switch_requested fires when a physical button is mapped to
  // ACTION_PROFILE_SWITCH and gets pressed.
  useEffect(() => {
    if (!bridge || !bridge.profile_switch_requested) return;
    const onSwitch = (targetId) => {
      setState((s) => {
        if (!s.profiles.find((p) => p.id === targetId)) return s;
        return { ...s, activeProfileId: targetId, selection: null };
      });
    };
    bridge.profile_switch_requested.connect(onSwitch);
    return () => {
      try { bridge.profile_switch_requested.disconnect(onSwitch); } catch {}
    };
  }, [setState]);

  // Light feedback so the user knows a press actually did something.
  useEffect(() => {
    if (!bridge || !bridge.action_executed) return;
    const onExec = (type, status) => {
      console.log('[action]', type, status);
    };
    bridge.action_executed.connect(onExec);
    return () => {
      try { bridge.action_executed.disconnect(onExec); } catch {}
    };
  }, []);

  return null;
}

// ───────── Module discovery watcher ─────────
// Listens for modules reported by the firmware and merges them into the
// active profile, preserving any existing button/encoder assignments that
// match by module_id. Modules in the profile that aren't in the discovery
// (e.g. unplugged slaves) are kept so offline-configured profiles aren't
// destroyed when the user connects different hardware.
function DiscoveryWatcher() {
  const { setState, showToast } = useStore();

  useEffect(() => {
    if (!bridge || !bridge.modules_discovered) return;

    const onDiscovered = (jsonStr) => {
      let discovered;
      try { discovered = JSON.parse(jsonStr || '[]'); }
      catch { return; }
      if (!Array.isArray(discovered) || !discovered.length) return;

      setState((s) => {
        const profiles = s.profiles.map((p) => {
          if (p.id !== s.activeProfileId) return p;

          const byId = new Map(p.modules.map((m) => [m.module_id, m]));
          const seen = new Set();

          const merged = discovered.map((d) => {
            seen.add(d.module_id);
            const old = byId.get(d.module_id);
            const fresh = window.MP.newModule({
              module_id: d.module_id,
              module_type: d.module_type || 'slave',
              name: (old && old.name) || d.name || (d.module_type === 'main' ? 'Ana Modül' : 'Modül'),
              button_count: d.button_count || 0,
              encoder_count: d.encoder_count || 0,
              has_display: !!d.has_display,
            });
            if (!old) return fresh;

            const bN = Math.min((old.buttons || []).length, fresh.buttons.length);
            for (let i = 0; i < bN; i++) fresh.buttons[i] = old.buttons[i];
            const eN = Math.min((old.encoders || []).length, fresh.encoders.length);
            for (let i = 0; i < eN; i++) fresh.encoders[i] = old.encoders[i];
            // Only carry old values forward if they're actually set —
            // assigning `undefined` would clobber the fresh defaults
            // and JSON.stringify would then drop the field entirely,
            // which is exactly what made the firmware see mode=
            // (default profile_name) no matter what the user picked.
            if (old.display_mode) fresh.display_mode = old.display_mode;
            if (old.display_custom_text != null) {
              fresh.display_custom_text = old.display_custom_text;
            }
            return fresh;
          });

          // Drop modules whose IDs the firmware didn't report. There's
          // only ever one main module on a device, so any pre-existing
          // 'main' that didn't match the discovered one is a stale
          // default from before the user connected real hardware —
          // remove it unconditionally (otherwise the user ends up with
          // two "Ana Modül" cards and edits the wrong one).
          // Slave modules without a matching ID may be intentionally
          // configured offline, so we keep those if they have any
          // assigned actions.
          const discoveredHasMain = discovered.some((d) => d.module_type === 'main');
          const surviving = p.modules.filter((m) => {
            if (seen.has(m.module_id)) return false;
            if (discoveredHasMain && m.module_type === 'main') return false;
            const hasButtonAction = (m.buttons || []).some(
              (b) => b && (b.action_type !== 'none' || b.label)
            );
            const hasEncoderAction = (m.encoders || []).some(
              (e) => e && (
                (e.cw && e.cw.action_type !== 'none') ||
                (e.ccw && e.ccw.action_type !== 'none') ||
                (e.push && e.push.action_type !== 'none')
              )
            );
            return hasButtonAction || hasEncoderAction;
          });
          return { ...p, modules: [...merged, ...surviving] };
        });
        return { ...s, profiles };
      });

      showToast(`${discovered.length} modül algılandı`);
    };

    bridge.modules_discovered.connect(onDiscovered);
    return () => {
      try { bridge.modules_discovered.disconnect(onDiscovered); } catch {}
    };
  }, [setState, showToast]);

  return null;
}

// ───────── Update banner ─────────
window.MP_checkForUpdates = null;  // exposed so the topbar can re-trigger manually

function UpdateWatcher() {
  const { showToast } = useStore();
  const [info, setInfo] = useState(null);
  const manualRef = useRef(false);

  useEffect(() => {
    if (!bridge) return;
    const onAvail = (version, url, notes) => {
      console.log('[updater] available:', version, url);
      setInfo({ version, url, notes });
    };
    const onNone = () => {
      console.log('[updater] no update');
      if (manualRef.current) showToast('Güncel sürümü kullanıyorsunuz');
      manualRef.current = false;
    };
    const onErr = (msg) => {
      console.warn('[updater] error:', msg);
      showToast(`Güncelleme kontrolü başarısız: ${msg.slice(0, 60)}`);
      manualRef.current = false;
    };

    if (bridge.update_available) bridge.update_available.connect(onAvail);
    if (bridge.update_none) bridge.update_none.connect(onNone);
    if (bridge.update_error) bridge.update_error.connect(onErr);

    // Expose a manual trigger so the topbar button can ask for a re-check.
    window.MP_checkForUpdates = () => {
      manualRef.current = true;
      if (bridge.check_for_updates) bridge.check_for_updates();
    };

    // Delay the auto-check by a beat so QWebChannel signal connections
    // are fully wired up on the Python side before the request fires.
    const t = setTimeout(() => {
      if (bridge.check_for_updates) bridge.check_for_updates();
    }, 1500);

    return () => {
      clearTimeout(t);
      try {
        if (bridge.update_available) bridge.update_available.disconnect(onAvail);
        if (bridge.update_none) bridge.update_none.disconnect(onNone);
        if (bridge.update_error) bridge.update_error.disconnect(onErr);
      } catch {}
      window.MP_checkForUpdates = null;
    };
  }, [showToast]);

  if (!info) return null;
  const apply = () => {
    bridge.apply_update(info.url);
    showToast('Güncelleme indiriliyor…');
  };
  return (
    <div className="toast" style={{ bottom: 80 }}>
      ⬆ Yeni sürüm v{info.version} mevcut
      <button className="btn sm accent" style={{ marginLeft: 10 }} onClick={apply}>Şimdi Güncelle</button>
      <button className="btn sm ghost" style={{ marginLeft: 4 }} onClick={() => setInfo(null)}>Sonra</button>
    </div>
  );
}

// ───────── App ─────────
function App() {
  const { toast } = useStore();
  const [showAddModule, setShowAddModule] = useState(false);
  const [showFlash, setShowFlash] = useState(false);

  return (
    <div className="app">
      <Topbar onOpenFlash={() => setShowFlash(true)} />
      <div className="body">
        <Sidebar onAddModule={() => setShowAddModule(true)} />
        <Canvas onAddModule={() => setShowAddModule(true)} />
        <Inspector />
      </div>
      <Footer />
      {showAddModule && <AddModuleModal onClose={() => setShowAddModule(false)} />}
      {showFlash && <FlashModal onClose={() => setShowFlash(false)} />}
      {toast && <div className="toast">{toast}</div>}
      <UpdateWatcher />
      <DiscoveryWatcher />
      <ActionRouter />
      <ConnectionWatcher />
    </div>
  );
}

window.MPApp = App;
