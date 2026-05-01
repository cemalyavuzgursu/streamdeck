/* global React, MP */
const { useState, useEffect, useRef, useMemo, useCallback } = React;
const {
  useStore,
  ACTION_NONE, ACTION_SHORTCUT, ACTION_MEDIA, ACTION_APP, ACTION_MACRO, ACTION_PROFILE_SWITCH,
  ACTION_LABELS, ACTION_GLYPHS, ACTION_SHORT,
  MEDIA_ACTIONS,
  DISPLAY_CLOCK, DISPLAY_PROFILE, DISPLAY_VOLUME, DISPLAY_CUSTOM, DISPLAY_MODES,
  uid, newButton, newProfile,
} = window.MP;

const bridge = window.MP_BRIDGE;

// ───────── Topbar ─────────
function Topbar({ onOpenFlash }) {
  const { state, setState, showToast, activeProfile } = useStore();
  const [ports, setPorts] = useState([state.selectedPort]);

  const refreshPorts = useCallback(() => {
    if (!bridge) {
      setPorts(['COM3', 'COM4', 'COM5', '/dev/ttyUSB0']);
      return;
    }
    bridge.list_ports((result) => {
      const list = JSON.parse(result || '[]');
      setPorts(list.length ? list : [state.selectedPort]);
      if (list.length && !list.includes(state.selectedPort)) {
        setState((s) => ({ ...s, selectedPort: list[0] }));
      }
    });
  }, [setState, state.selectedPort]);

  useEffect(() => { refreshPorts(); }, [refreshPorts]);

  const toggleConnect = () => {
    if (!bridge) {
      setState((s) => ({ ...s, connected: !s.connected }));
      showToast(state.connected ? 'Bağlantı kesildi' : `Bağlandı: ${state.selectedPort}`);
      return;
    }
    if (state.connected) {
      bridge.disconnect_device(() => {
        setState((s) => ({ ...s, connected: false }));
        showToast('Bağlantı kesildi');
      });
    } else {
      bridge.connect_device(state.selectedPort, (ok) => {
        if (ok) {
          setState((s) => ({ ...s, connected: true }));
          showToast(`Bağlandı: ${state.selectedPort}`);
        } else {
          showToast(`Bağlantı başarısız: ${state.selectedPort}`);
        }
      });
    }
  };

  const sendConfig = () => {
    if (!state.connected) return showToast('Cihaz bağlı değil');
    if (!activeProfile) return;
    if (bridge) {
      bridge.send_config(JSON.stringify(activeProfile), (ok) => {
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
        {state.connected ? `${state.selectedPort} · ESP32-C3` : 'Bağlı değil'}
      </div>

      <div className="port-group">
        <select className="port-select" value={state.selectedPort}
          onChange={(e) => setState((s) => ({ ...s, selectedPort: e.target.value }))}>
          {ports.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <button className="icon-btn" title="Portları Tara" onClick={() => { refreshPorts(); showToast('Portlar tarandı'); }}>↻</button>
      </div>

      <button className={`btn ${state.connected ? '' : 'primary'}`} onClick={toggleConnect}>
        {state.connected ? 'Bağlantıyı Kes' : 'Bağlan'}
      </button>

      <button className="btn ghost" onClick={onOpenFlash} title="Firmware Güncelle">⚡ Flash</button>

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
  const fileInput = useRef();

  const select = (id) => setState((s) => ({ ...s, activeProfileId: id, selection: null }));

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
    </aside>
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
  useEffect(() => { const i = setInterval(() => setTick((t) => t + 1), 1000); return () => clearInterval(i); }, []);
  const now = new Date();
  const time = now.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
  const date = now.toLocaleDateString('tr-TR');

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
            <div className="oled-bar"><div className="oled-bar-fill" style={{ width: '65%' }} /></div>
            <div className="oled-bar-pct">65%</div>
          </>
        )}
        {mode === DISPLAY_CUSTOM && (
          <div className="oled-custom">{customText || '(boş)'}</div>
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

  const cols = Math.min(4, mod.button_count) || 1;
  const keyGridStyle = { gridTemplateColumns: `repeat(${cols}, minmax(80px, 96px))` };

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
        {mod.button_count > 0 && (
          <div className="keys" style={keyGridStyle}>
            {mod.buttons.map((b, i) => (
              <KeyButton key={i} btn={b} idx={i} selected={isKeySel(i)}
                onClick={() => select({ moduleId: mod.module_id, kind: 'button', index: i })} />
            ))}
          </div>
        )}

        {mod.encoder_count > 0 && (
          <div className="encoders-row">
            {mod.encoders.map((e, i) => (
              <Encoder key={i} enc={e} idx={i}
                selection={sel && sel.moduleId === mod.module_id ? sel : null}
                onPick={(sub) => select({ moduleId: mod.module_id, kind: 'encoder', index: i, sub })} />
            ))}
          </div>
        )}

        {mod.has_display && (
          <div className="oled-row">
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

function AppEditor({ cfg, setCfg }) {
  const pickFile = () => {
    if (!bridge) return;
    bridge.pick_executable((path) => {
      if (path) setCfg((c) => { c.action_data.path = path; });
    });
  };
  return (
    <>
      <div className="field">
        <label>Uygulama Yolu</label>
        <div className="row">
          <input className="input mono grow" value={cfg.action_data.path || ''}
            placeholder="C:\\Program Files\\Spotify\\Spotify.exe"
            onChange={(e) => setCfg((c) => { c.action_data.path = e.target.value; })} />
          {bridge && <button className="btn sm" onClick={pickFile} title="Dosya seç">…</button>}
        </div>
      </div>
      <div className="field">
        <label>Argümanlar</label>
        <input className="input mono" value={cfg.action_data.args || ''}
          placeholder="--minimized"
          onChange={(e) => setCfg((c) => { c.action_data.args = e.target.value; })} />
      </div>
    </>
  );
}

function MacroEditor({ cfg, setCfg }) {
  return (
    <div className="field">
      <label>Makro Dizisi</label>
      <textarea className="textarea" value={cfg.action_data.sequence || ''}
        placeholder={'ctrl+c\nwait:200\nctrl+v\ntype:Hello'}
        onChange={(e) => setCfg((c) => { c.action_data.sequence = e.target.value; })} />
      <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 4, fontFamily: 'var(--font-mono)' }}>
        Desteklenen: tuş kombinasyonları, wait:ms, type:metin
      </div>
    </div>
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

function DisplayInspector({ moduleId }) {
  const { updateActiveProfile, activeProfile } = useStore();
  const mod = activeProfile.modules.find((m) => m.module_id === moduleId);
  if (!mod) return null;
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
      <div className="field">
        <label>Modül Adı</label>
        <input className="input" value={mod.name}
          onChange={(e) => updateActiveProfile((p) => {
            const m = p.modules.find((mm) => mm.module_id === moduleId); if (m) m.name = e.target.value;
          })} />
      </div>
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
  const { state, activeProfile } = useStore();
  const totalKeys = activeProfile?.modules.reduce((s, m) => s + m.button_count, 0) || 0;
  const totalEnc = activeProfile?.modules.reduce((s, m) => s + m.encoder_count, 0) || 0;
  return (
    <div className="footer">
      <span>profile <span style={{ color: 'var(--ink)' }}>"{activeProfile?.name}"</span></span>
      <span>{totalKeys} keys · {totalEnc} encoders</span>
      <span className="grow" />
      <span>baud 115200</span>
      <span>{state.connected ? <span className="ok">● connected</span> : '○ offline'}</span>
      <span>{new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })}</span>
    </div>
  );
}

// ───────── Update banner ─────────
function UpdateWatcher() {
  const { showToast } = useStore();
  const [info, setInfo] = useState(null);

  useEffect(() => {
    if (!bridge) return;
    const onAvail = (version, url, notes) => setInfo({ version, url, notes });
    if (bridge.update_available) bridge.update_available.connect(onAvail);
    if (bridge.check_for_updates) bridge.check_for_updates();
    return () => {
      try { if (bridge.update_available) bridge.update_available.disconnect(onAvail); } catch {}
    };
  }, []);

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
    </div>
  );
}

window.MPApp = App;
