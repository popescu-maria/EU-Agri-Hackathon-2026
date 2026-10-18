const PHASE_NAME = {germination: 'Sprouting', vegetative: 'Leaf growth', flowering: 'Flowering', grain_fill: 'Grain filling', mature: 'Ready to harvest'};
const NEXT_NAME = {emergence: 'Sprouts come up', flowering: 'Starts flowering', grain_fill: 'Grain starts filling'};
const NOTE_ICON = {ok: '✅', info: 'ℹ️', warning: '⚠️'};
const OM_WORD = {low: 'Low', medium: 'Medium', high: 'High'};

const cropLabel = id => { const v = vById(id); return v ? `${CROP_NAMES[v.crop_code] || v.crop_code} (${v.name})` : vName(id); };
const cropIcon = id => CROP_ICON[vById(id)?.crop_code] || '🌱';
const iso = d => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const todayIso = () => iso(new Date());
const addDays = (s, n) => { const d = day(s); d.setDate(d.getDate() + n); return iso(d); };
const fmtDay = s => day(s).toLocaleDateString('en-GB', {weekday: 'short', day: 'numeric', month: 'short'});
const fmtDate = s => day(s).toLocaleDateString('en-GB', {day: 'numeric', month: 'long'});
const fmtMD = md => md ? fmtDate(`2000-${md}`) : '–';
function nextMD(md) {
  if (!md) return null;
  const t = todayIso(), y = +t.slice(0, 4);
  return `${y}-${md}` >= t ? `${y}-${md}` : `${y + 1}-${md}`;
}

function harvestDate(c) {
  const mine = S.crops.find(x => x.id === c.crop_id), v = vById(c.variety_id);
  const dates = [c.info?.expected_maturity];
  if (mine?.sowing_date && v?.days_to_maturity) dates.push(addDays(mine.sowing_date, v.days_to_maturity));
  return dates.filter(Boolean).sort()[0] || null;
}

/* ---------------- Advice ---------------- */
const progressBar = pct => `<div style="height:.8rem;background:var(--line);border-radius:.4rem;overflow:hidden;margin:.3rem 0"><div style="height:100%;width:${pct}%;background:var(--green)"></div></div>`;

function cropSummaryLine(c) {
  if (c.status === 'planned') {
    const s = c.sowing || {};
    if (s.wait) return `${s.wait.kind === 'flood' ? 'Heavy rain coming' : 'Frost coming'} · sow ${s.wait.sow_from ? dayLabel(s.wait.sow_from) : 'later'}`;
    if (s.state === 'open') return s.best_days?.length ? 'Good time to sow' : 'Sowing time, poor weather';
    return s.state === 'not_yet' ? `Sowing starts in ${s.days} days` : 'Sowing time is over';
  }
  const h = harvestDate(c);
  if (h && h <= todayIso()) return 'Should be ready to harvest';
  return `${PHASE_NAME[c.info?.phase] || ''} · ${c.info?.progress_pct ?? 0}% grown`;
}

function cropDetails(c) {
  const mine = S.crops.find(x => x.id === c.crop_id), v = vById(c.variety_id);
  const rows = [];
  if (c.status === 'planned') {
    const s = c.sowing || {};
    rows.push(`<p class="body" style="margin:.2rem 0 .6rem">${esc(s.message || '')}</p>`);
    if (v?.sowing_window) rows.push(kv('Sowing time', `${fmtMD(v.sowing_window[0])} – ${fmtMD(v.sowing_window[1])}`));
    if (s.wait?.sow_from) rows.push(kv('Sow on', `<span class="good">${dayLabel(s.wait.sow_from)}, ${fmtDate(s.wait.sow_from)}</span>`));
    else if (s.state === 'open' && s.best_days?.length) rows.push(kv('Good days', s.best_days.map(d => esc(dayLabel(d))).join(', ')));
  } else {
    const i = c.info || {}, h = harvestDate(c), ready = h && h <= todayIso();
    if (mine?.sowing_date) rows.push(kv('Planted', `${MONTHS[+mine.sowing_date.slice(5, 7) - 1]} ${mine.sowing_date.slice(0, 4)}`));
    rows.push(kv('Stage', ready ? 'Ready to harvest' : esc(PHASE_NAME[i.phase] || '–')));
    if (!ready) rows.push(`<div class="kv" style="display:block"><b>Grown</b> ${i.progress_pct ?? 0}%${progressBar(i.progress_pct || 0)}</div>`);
    if (!ready && i.next_milestone_date && NEXT_NAME[i.next_milestone] && (!h || i.next_milestone_date < h))
      rows.push(kv('Next', `${NEXT_NAME[i.next_milestone]} · about ${fmtDate(i.next_milestone_date)}`));
    rows.push(kv('Harvest', ready ? '<span class="watch">Now – check the field</span>' : h ? `About ${fmtDate(h)}` : '–'));
  }
  const notes = (c.soil_notes || []).map(n => `<div class="row" style="align-items:flex-start;gap:.5rem;padding:.35rem 0">${emo(NOTE_ICON[n.level] || 'ℹ️')}<span class="body">${esc(n.text)}</span></div>`).join('');
  return rows.join('') + (notes ? `<div class="sec" style="margin:1rem 0 .3rem">Your soil and this crop</div>${notes}` : '');
}

const SUB_WORD = {winter: 'Winter type, sown in autumn', spring: 'Spring type, sown in spring', durum: 'Durum wheat (for pasta)', grain: 'Grown for grain'};

function cropFacts(c) {
  const v = vById(c.variety_id);
  if (!v) return '';
  return [
    v.subtype && SUB_WORD[v.subtype] ? kv('Type', SUB_WORD[v.subtype]) : '',
    v.maturity_group ? kv('Ripens', `${MATURITY[v.maturity_group] || v.maturity_group}${v.fao_number ? ` (FAO ${esc(v.fao_number)})` : ''}`) : '',
    v.days_to_maturity ? kv('Season', `About ${Math.round(v.days_to_maturity / 30)} months from sowing to harvest`) : ''
  ].join('');
}

function cropWarnings(c) {
  if (!c.alerts?.length) return `<p class="note" style="margin:.2rem 0 0">${emo('✅')} No warnings this week</p>`;
  return `<div style="display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.3rem">${c.alerts.map(a =>
    `<span class="tag t-${(SEV[a.level] || SEV.info)[0]}">${emo(KIND_ICON[a.kind] || '⚠️')} ${esc(a.title)} · ${esc(dayLabel(a.date))}</span>`).join('')}</div>`;
}

SCREENS.advice = () => {
  const A = UI.analysis;
  if (!A) return `<div class="scroll"><h1 style="margin-bottom:1rem">My crops</h1>${UI.loadErr ? errorCard() : loadingCard('Checking your crops…')}</div>${nav('advice')}`;
  const cards = A.crops.map(c => acc('crop-' + c.crop_id,
    `<span style="font-size:2rem;line-height:1;align-self:flex-start">${emo(cropIcon(c.variety_id))}</span>
     <span class="grow"><span class="sumt" style="display:block">${esc(cropLabel(c.variety_id))}</span><span class="sums">${esc(cropSummaryLine(c))}</span>${cropWarnings(c)}</span>`,
    cropDetails(c) + `<div class="sec" style="margin:1rem 0 .3rem">About this variety</div>` + cropFacts(c))).join('');
  return `
  <div class="scroll">
    <h1 style="margin-bottom:.4rem">My crops</h1>
    <p class="note" style="margin-bottom:.8rem">How each crop is doing. Tap a crop for details. Warnings are on the Home screen.</p>
    ${cards}
    <button class="big line" style="margin-top:1rem" onclick="go('crops')">Add or remove crops</button>
  </div>${nav('advice')}`;
};

/* ---------------- Calendar ---------------- */
function calendarEvents() {
  const A = UI.analysis, t = todayIso(), ev = [];
  const add = (date, icon, text, cls = '') => ev.push({date, icon, text, cls});
  const groups = {};
  A.alerts.forEach(a => {
    const g = groups[a.date + a.kind] ??= {a, names: []};
    if (a.level === 'urgent') g.a = a;
    const id = S.crops.find(c => c.id === a.crop_id)?.variety_id;
    if (id || a.variety_name) g.names.push(id ? cropLabel(id) : a.variety_name);
  });
  Object.values(groups).forEach(({a, names}) => add(a.date, KIND_ICON[a.kind] || '⚠️', names.length ? `${a.title}: ${names.join(', ')}` : `${a.title} (whole farm)`, a.level === 'urgent' ? 'bad' : 'watch'));
  A.crops.forEach(c => {
    const name = cropLabel(c.variety_id), v = vById(c.variety_id);
    if (c.status === 'planned') {
      const s = c.sowing || {};
      if (s.state === 'open') (s.best_days || []).filter(d => !s.wait || d > s.wait.date).forEach(d => add(d, '🌱', `Good day to sow ${name}`, 'good'));
      if (v?.sowing_window) {
        const [ws, we] = v.sowing_window, y = +t.slice(0, 4);
        if (s.state === 'open') add(`${y}-${we}`, '⏳', `Last day to sow ${name}`);
        else {
          const start = s.state === 'not_yet' ? `${y}-${ws}` : `${y + 1}-${ws}`;
          add(start, '🌱', `Sowing time starts: ${name}`, 'good');
          add(`${start.slice(0, 4)}-${we}`, '⏳', `Last day to sow ${name}`);
        }
      }
    } else {
      const i = c.info || {}, h = harvestDate(c);
      if (h && h <= t) add(t, '🚜', `${name} should be ready to harvest`, 'watch');
      else {
        if (i.next_milestone_date && NEXT_NAME[i.next_milestone] && (!h || i.next_milestone_date < h)) add(i.next_milestone_date, '🌿', `${name}: ${NEXT_NAME[i.next_milestone].toLowerCase()} (about)`);
        if (h) add(h, '🚜', `${name}: ready to harvest (about)`);
      }
    }
  });
  const r = S.region || {};
  if (r.first_autumn_frost) add(nextMD(r.first_autumn_frost), '❄️', 'First frost of autumn usually comes around now');
  if (r.last_spring_frost) add(nextMD(r.last_spring_frost), '🌤️', 'Last frost of spring usually around now');
  const limit = addDays(t, 365);
  return ev.filter(e => e.date >= t && e.date <= limit).sort((a, b) => a.date.localeCompare(b.date));
}

const calRow = e => `<div class="row" style="align-items:flex-start;gap:.6rem;padding:.35rem 0">${emo(e.icon, '1.4rem')}<span class="body grow ${e.cls}" style="font-weight:600">${esc(e.text)}</span></div>`;

SCREENS.calendar = () => {
  const A = UI.analysis;
  if (!A || !UI.weather) return `<div class="scroll"><h1 style="margin-bottom:1rem">Calendar</h1>${UI.loadErr ? errorCard() : loadingCard('Building your calendar…')}</div>${nav('calendar')}`;
  const ev = calendarEvents(), weekEnd = addDays(todayIso(), 6);
  const week = UI.weather.days.map(d => {
    const mine = ev.filter(e => e.date === d.date);
    return `<div class="card" style="margin-top:.5rem;padding:.7rem 1rem">
      <div class="row" style="justify-content:space-between"><b style="color:var(--black);font-size:1.1rem">${dayLabel(d.date)} ${emo(sky(d)[0])}</b><span class="note">${fmtDay(d.date)} · ${t0(d.t_max)} / ${t0(d.t_min)}</span></div>
      ${mine.length ? mine.map(calRow).join('') : `<p class="note" style="margin:.3rem 0 0">Nothing special.</p>`}</div>`;
  }).join('');
  const months = {};
  ev.filter(e => e.date > weekEnd).forEach(e => (months[e.date.slice(0, 7)] ??= []).push(e));
  const later = Object.entries(months).map(([m, list]) => `
    <div class="sec">${day(m + '-01').toLocaleDateString('en-GB', {month: 'long', year: 'numeric'})}</div>
    <div class="card">${list.map(e => `<div class="kv" style="align-items:flex-start"><b style="min-width:4.5rem">${day(e.date).getDate()} ${day(e.date).toLocaleDateString('en-GB', {month: 'short'})}</b><span class="grow">${calRow(e)}</span></div>`).join('')}</div>`).join('');
  return `
  <div class="scroll">
    <h1 style="margin-bottom:.4rem">Calendar</h1>
    <p class="note">What is coming up on your farm. Dates marked “about” are estimates.</p>
    <div class="sec">This week</div>${week}
    ${later || ''}
  </div>${nav('calendar')}`;
};

/* ---------------- My farm ---------------- */
let farmMap = null;
UI.confirmReset = false;

function setDemo(v) { S.demo = v; save(); refreshData(); }
function setLarge(on) { S.large = on; save(); document.documentElement.classList.toggle('large', on); render(); }

SCREENS.farm = () => {
  const s = S.soil, r = S.region || {};
  const soil = s ? [
    kv('Soil type', esc(s.texture_class)),
    kv('pH', `${esc(s.ph)} · ${s.ph < 5.5 ? 'acidic' : s.ph > 7.5 ? 'alkaline' : 'neutral'}`),
    kv('Organic matter', esc(OM_WORD[s.organic_matter] || s.organic_matter || '–')),
    kv('Measured by', s.source === 'soilgrids' ? 'Soil map (SoilGrids)' : 'Average for your region')
  ].join('') : `<p class="body">${UI.soilErr ? 'We couldn’t check your soil.' : '<span class="spin"></span> Checking your soil…'}</p>`;
  const reset = UI.confirmReset
    ? `<div class="card" style="border-color:var(--red)"><p class="body" style="margin-top:0"><b>Start over?</b> This deletes your farm, crops and settings from this phone.</p>
        <div class="stack"><button class="big danger" onclick="UI.confirmReset=false;resetAll()">Yes, start over</button><button class="big line" onclick="UI.confirmReset=false;render()">Cancel</button></div></div>`
    : `<button class="big line" onclick="UI.confirmReset=true;render()">Start over</button>`;
  return `
  <div class="scroll">
    <h1 style="margin-bottom:.4rem">My farm</h1>
    <div class="sec">Location</div>
    <div class="card"><div id="farmmap" class="mapbox" style="height:11rem" aria-label="Map of your farm"></div>
      <p class="note">${S.loc ? `${S.loc.lat.toFixed(4)}, ${S.loc.lon.toFixed(4)}` : ''}</p>
      <button class="big line" onclick="go('locate')">Change location</button></div>
    <div class="sec">Soil</div><div class="card">${soil}</div>
    <div class="sec">Frost in your area</div>
    <div class="card">${kv('Last in spring', `Usually around ${fmtMD(r.last_spring_frost)}`)}${kv('First in autumn', `Usually around ${fmtMD(r.first_autumn_frost)}`)}
      <p class="note" style="margin:.4rem 0 0">From ${r.years_used || 'past'} years of weather in your region${r.id ? ` (${esc(r.id)})` : ''}.</p></div>
    <div class="sec">Text size</div>
    <div class="seg"><button aria-pressed="${!S.large}" onclick="setLarge(false)">Normal</button><button aria-pressed="${!!S.large}" onclick="setLarge(true)">Bigger</button></div>
    <div class="sec">For presentations</div>
    <div class="seg"><button aria-pressed="${!S.demo}" onclick="setDemo(null)">Real weather</button><button aria-pressed="${S.demo === 'flood'}" onclick="setDemo('flood')">Flood demo</button></div>
    <p class="note" style="margin-top:.4rem">Flood demo adds a fake storm to the real forecast: heavy rain and strong wind in 2 days, then a night frost.</p>
    <div class="sec">Reset</div>${reset}
    <p class="note" style="margin-top:1rem"><button class="textbtn" style="font-size:inherit" onclick="openPolicy()">GDPR Privacy Policy</button></p>
  </div>${nav('farm')}`;
};

AFTER.farm = () => {
  needData();
  if (farmMap) { farmMap.remove(); farmMap = null; }
  if (!S.loc || !$('#farmmap')) return;
  farmMap = L.map('farmmap', {zoomControl: false, dragging: false, scrollWheelZoom: false, doubleClickZoom: false, touchZoom: false, keyboard: false}).setView([S.loc.lat, S.loc.lon], 13);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19, attribution: '© OpenStreetMap'}).addTo(farmMap);
  L.marker([S.loc.lat, S.loc.lon]).addTo(farmMap);
};
AFTER.calendar = needData;