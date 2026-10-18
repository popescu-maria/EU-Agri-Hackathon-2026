const ICON = {
  home: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"><path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1Z"/></svg>',
  sun: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><circle cx="12" cy="12" r="4.5"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8"/></svg>',
  plant: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21V11"/><path d="M12 11C12 7 9 4.5 4.5 4.5 4.5 9 7.5 11 12 11Z"/><path d="M12 14c0-3.500 2.500-6 7.500-6 0 4-3 6-7.500 6Z"/></svg>',
  cal: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/></svg>',
  farm: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"><path d="M12 21s-7-6.5-7-12a7 7 0 0 1 14 0c0 5.500-7 12-7 12Z"/><circle cx="12" cy="9" r="2.5"/></svg>'
};
const TABS = [['home', 'Home', ICON.home], ['weather', 'Weather', ICON.sun], ['advice', 'Crops', ICON.plant], ['calendar', 'Calendar', ICON.cal], ['farm', 'My farm', ICON.farm]];
const KIND_ICON = {flood: '🌊', frost: '❄️', heat: '🌡️', drought: '🏜️', harvest_rain: '🌧️', wind: '💨'};
const SEV = {urgent: ['urgent', 'Urgent'], warning: ['watch', 'Watch'], info: ['note', 'Note'], good: ['sow', 'Good news']};

UI.weather = null;

function nav(cur) {
  const n = todoItems().filter(i => i.sev === 'urgent').length;
  const demo = S.demo ? `<div style="background:var(--warn-bg);color:var(--warn-fg);font-weight:700;padding:.45rem 1rem;display:flex;justify-content:space-between;align-items:center">${emo('🎬')} Demo: fake storm in 2 days<button class="textbtn" onclick="setDemo(null)">Turn off</button></div>` : '';
  return demo + `<nav class="nav" aria-label="Main">${TABS.map(([id, lab, ic]) =>
    `<button onclick="go('${id}')" ${cur === id ? 'aria-current="page"' : ''}><span class="navdot">${ic}${id === 'home' && n ? `<b>${n}</b>` : ''}</span>${lab}</button>`).join('')}</nav>`;
}

async function loadFarmData() {
  UI.loading = true; UI.loadErr = '';
  try {
    if (!VARIETIES.length) VARIETIES = await API.varieties();
    await ensureSoil();
    const [w, a] = await Promise.all([
      UI.weather ? UI.weather : API.weather(S.loc.lat, S.loc.lon, S.demo),
      UI.analysis ? UI.analysis : API.analyse({location: S.loc, soil: S.soil, crops: S.crops, demo: S.demo || null})
    ]);
    UI.weather = w; UI.analysis = a; UI.loadedAt = new Date();
  } catch (e) { UI.loadErr = e.message; }
  UI.loading = false;
  render();
}
function needData() { if ((!UI.weather || !UI.analysis) && !UI.loading && !UI.loadErr) loadFarmData(); }
function refreshData() { UI.weather = null; UI.analysis = null; UI.loadErr = ''; render(); }
AFTER.home = needData;
AFTER.weather = needData;
AFTER.advice = needData;

const day = d => new Date(d + 'T12:00');
function dayLabel(d) {
  const t = new Date(); t.setHours(12, 0, 0, 0);
  const n = Math.round((day(d) - t) / 864e5);
  return n === 0 ? 'Today' : n === 1 ? 'Tomorrow' : day(d).toLocaleDateString('en-GB', {weekday: 'long'});
}
const t0 = v => v == null ? '–' : `${Math.round(v)}°`;
function rainWord(mm) { return mm >= 20 ? 'Heavy rain' : mm >= 5 ? 'Rain' : mm >= 1 ? 'Light rain' : 'Dry'; }
function windWord(g) { return g >= 60 ? 'Storm winds' : g >= 40 ? 'Windy' : g >= 20 ? 'Breezy' : 'Calm'; }
function sky(d) {
  if (d.t_min != null && d.t_min <= 0) return ['❄️', 'Frost at night'];
  if (d.rain_mm >= 5) return ['🌧️', rainWord(d.rain_mm)];
  if (d.rain_mm >= 1) return ['🌦️', 'Light rain'];
  if (d.t_max >= 25) return ['☀️', 'Sunny and warm'];
  return ['⛅', 'Dry'];
}

function todoItems() {
  const A = UI.analysis; if (!A) return [];
  const groups = [];
  A.alerts.forEach(a => {
    const g = groups.find(x => x.kind === a.kind && x.date === a.date);
    const who = a.variety_name || 'Whole farm';
    if (g) { g.crops.push(who); if (a.level === 'urgent') g.sev = 'urgent'; }
    else groups.push({kind: a.kind, sev: a.level, icon: KIND_ICON[a.kind] || '⚠️', title: a.title, text: a.message, crops: [who], date: a.date});
  });
  A.crops.forEach(c => {
    const s = c.sowing;
    if (s && s.state === 'open' && !s.wait && s.best_days && s.best_days.length)
      groups.push({kind: 'sow', sev: 'good', icon: '🌱', title: 'Good time to sow', text: s.message, crops: [c.variety_name], date: null});
    else if (s && s.state === 'open' && s.wait && s.wait.sow_from)
      groups.push({kind: 'sow', sev: 'good', icon: '🌱', title: 'When to sow', text: `Sow your ${cropLabel(c.variety_id)} after the ${s.wait.kind === 'flood' ? 'rain' : 'cold'}: ${dayLabel(s.wait.sow_from)}, ${fmtDate(s.wait.sow_from)}.`, crops: [c.variety_name], date: s.wait.sow_from});
  });
  const rank = g => g.sev === 'urgent' ? 0 : g.kind === 'sow' ? 1 : 2;
  return groups.sort((x, y) => rank(x) - rank(y));
}

const firstSentences = (t, n) => (t.match(/[^.]+(\.|$)/g) || [t]).slice(0, n).join('').trim();

function todoCard(it, short) {
  const [cls, lab] = SEV[it.sev] || SEV.info;
  const many = it.crops.length > 1;
  const text = many ? firstSentences(it.text, 2) : (short ? firstSentences(it.text, 2) : it.text);
  return `<div class="card bar-${cls}" style="margin-top:.6rem">
    <div class="row" style="align-items:flex-start"><span style="font-size:1.7rem;line-height:1.2">${emo(it.icon)}</span>
    <span class="grow"><span class="tag t-${cls}">${lab}</span>
    <span class="sumt" style="display:block;margin-top:.3rem">${esc(it.title)}${it.date ? ' · ' + esc(dayLabel(it.date)) : ''}</span>
    <span class="body" style="display:block;margin-top:.2rem">${esc(text)}</span>
    ${many || it.crops[0] === 'Whole farm' ? `<span class="note" style="display:block;margin-top:.3rem">Affects: ${it.crops.map(esc).join(', ')}</span>` : ''}</span></div></div>`;
}

const loadingCard = msg => `<div class="card body" style="text-align:center;padding:1.6rem"><span class="spin"></span> ${msg}</div>`;
const errorCard = () => `<div class="banner">We couldn’t load your farm data (${esc(UI.loadErr)}). <button class="textbtn" onclick="UI.loadErr='';render()">Try again</button></div>`;

SCREENS.home = () => {
  const W = UI.weather, today = W && W.days[0];
  let wx = UI.loadErr ? errorCard() : loadingCard('Getting your weather…');
  if (today) {
    const [ic, lab] = sky(today);
    wx = `<button class="wx" onclick="go('weather')">
      <div class="s" style="font-weight:700">${emo('📍')} Your farm · Today</div>
      <div class="row" style="justify-content:space-between;margin-top:.3rem"><div class="t">${t0(today.t_max)}</div>${emo(ic, '3.4rem')}</div>
      <div class="c">${lab}</div>
      <div class="s">Night ${t0(today.t_min)} · ${windWord(today.gust_kmh)}</div>
      <div style="text-align:right;font-weight:800;margin-top:.6rem">See the week ›</div></button>`;
  }
  const items = todoItems();
  let todo = loadingCard('Checking your crops…');
  if (UI.loadErr) todo = '';
  else if (UI.analysis) todo = items.length
    ? items.map(it => todoCard(it, false)).join('')
    : `<div class="card body" style="margin-top:.6rem">${emo('✅')} Nothing to worry about this week.</div>`;
  return `
  <div class="scroll">
    <div class="row" style="justify-content:space-between;margin-bottom:1rem"><h1>Hello!</h1>${logoImg(52)}</div>
    ${wx}
    <div class="sec">What to do now</div>
    ${todo}
    ${UI.loadedAt ? `<p class="note" style="margin-top:1rem">Updated ${UI.loadedAt.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})} · <button class="textbtn" onclick="refreshData()">Refresh</button></p>` : ''}
  </div>${nav('home')}`;
};

function dayAlerts(d) {
  return UI.analysis ? UI.analysis.alerts.filter(a => a.date === d.date) : [];
}

SCREENS.weather = () => {
  const W = UI.weather;
  if (!W) return `<div class="scroll"><h1 style="margin-bottom:1rem">Weather</h1>${UI.loadErr ? errorCard() : loadingCard('Getting your weather…')}</div>${nav('weather')}`;
  const D = W.days, today = D[0];
  const [ic, lab] = sky(today);
  const cold = D.reduce((a, b) => (b.t_min < a.t_min ? b : a));
  const windy = D.reduce((a, b) => (b.gust_kmh > a.gust_kmh ? b : a));
  const wetDays = D.filter(d => d.rain_mm >= 1).length;
  const soil = today.soil_temp_c;
  const soilWord = soil == null ? '' : soil < 5 ? ['Cold', 'watch'] : soil < 10 ? ['Cool', 'watch'] : ['Warm', 'good'];

  const days = D.map((d, i) => {
    const [dic, dlab] = sky(d), al = dayAlerts(d);
    const summary = `<span style="width:6rem;font-weight:800;color:var(--black);font-size:1.1rem">${dayLabel(d.date)}</span>${emo(dic, '1.6rem')}
      <span class="grow" style="text-align:right;font-size:1.1rem"><b style="color:var(--black)">${t0(d.t_max)}</b> <span style="color:var(--soft)">/ ${t0(d.t_min)}</span>
      ${al.length ? `<br><span class="tag t-${(SEV[al[0].level] || SEV.info)[0]}">${esc(al[0].title)}</span>` : ''}</span>`;
    const inner = [
      kv('Weather', dlab),
      kv('Rain', rainWord(d.rain_mm)),
      kv('Day', `${t0(d.t_max)} warmest`),
      kv('Night', `${t0(d.t_min)} coldest${d.t_min <= 0 ? ' · <span class="bad">frost</span>' : ''}`),
      kv('Wind', windWord(d.gust_kmh)),
      kv('Soil', d.soil_temp_c == null ? '–' : `${t0(d.soil_temp_c)} warm`),
      ...al.map(a => kv(esc(a.variety_name || 'Whole farm'), `<span class="${a.level === 'urgent' ? 'bad' : 'watch'}">${esc(a.title)}</span>`))
    ].join('');
    return acc('day-' + i, summary, inner);
  }).join('');

  return `
  <div class="scroll">
    <h1 style="margin-bottom:1rem">Weather</h1>
    <div class="wx"><div class="s" style="font-weight:700">${emo('📍')} Your farm · Today</div>
      <div class="row" style="justify-content:space-between;margin-top:.3rem"><div class="t">${t0(today.t_max)}</div>${emo(ic, '3.4rem')}</div>
      <div class="c">${lab}</div>
      <div class="s">Night ${t0(today.t_min)} · ${windWord(today.gust_kmh)}</div></div>
    <div class="sec">This week on your field</div>
    <div class="tiles">
      <div class="tile"><div class="k">Soil warmth</div><div class="v">${t0(soil)}</div><div class="w ${soilWord[1] || ''}">${soilWord[0] || ''}</div></div>
      <div class="tile"><div class="k">Rainy days</div><div class="v">${wetDays} of ${D.length}</div><div class="w ${wetDays >= 4 ? 'watch' : 'good'}">${wetDays >= 4 ? 'Wet week' : wetDays === 0 ? 'Dry week' : 'Mixed'}</div></div>
      <div class="tile"><div class="k">Coldest night</div><div class="v">${t0(cold.t_min)}</div><div class="w ${cold.t_min <= 0 ? 'bad' : 'good'}">${cold.t_min <= 0 ? 'Frost ' + dayLabel(cold.date) : 'No frost'}</div></div>
      <div class="tile"><div class="k">Strongest wind</div><div class="v" style="font-size:1.3rem">${windWord(windy.gust_kmh)}</div><div class="w ${windy.gust_kmh >= 60 ? 'bad' : 'good'}">${dayLabel(windy.date)}</div></div>
    </div>
    <div class="sec">Next 7 days · tap a day</div>
    ${days}
    <p class="note" style="margin-top:1rem">Forecast: Open-Meteo${UI.loadedAt ? ` · updated ${UI.loadedAt.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'})}` : ''} · <button class="textbtn" onclick="refreshData()">Refresh</button></p>
  </div>${nav('weather')}`;
};

const kv = (k, v) => `<div class="kv"><b>${k}</b><span class="grow">${v}</span></div>`;