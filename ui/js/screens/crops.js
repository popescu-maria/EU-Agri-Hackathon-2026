let VARIETIES = [];
const CROP_NAMES = {wheat: 'Wheat', maize: 'Maize', rye: 'Rye', barley: 'Barley'};
const CROP_ICON = {wheat: '🌾', maize: '🌽', rye: '🌾', barley: '🌾'};
const SUBTYPE_NAMES = {winter: 'Winter', spring: 'Spring', durum: 'Durum (pasta)', grain: 'Grain'};
const MATURITY = {very_early: 'very early', early: 'early', medium: 'medium', late: 'late'};
const MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];
const PARTS = [['05', 'Start'], ['15', 'Middle'], ['25', 'End']];

const vById = id => VARIETIES.find(v => v.id === id);
const vName = id => vById(id)?.name || id;
const cropLine = c => c.status === 'growing'
  ? `Planted ${MONTHS[+c.sowing_date.slice(5, 7) - 1]} ${c.sowing_date.slice(0, 4)}`
  : 'Planning to sow';

async function loadVarieties() {
  UI.varLoading = true;
  try { VARIETIES = await API.varieties(); UI.varErr = ''; }
  catch (e) { UI.varErr = e.message; }
  UI.varLoading = false;
  render();
}
AFTER.crops = () => { if (!VARIETIES.length && !UI.varErr && !UI.varLoading) loadVarieties(); };

function soilStatus() {
  if (S.soil) return `<p class="note">${emo('✅')} Soil checked: ${esc(S.soil.texture_class)}, pH ${esc(S.soil.ph)}</p>`;
  if (UI.soilErr) return `<div class="banner">We couldn’t check your soil (${esc(UI.soilErr)}). <button class="textbtn" onclick="startSoilCheck()">Try again</button></div>`;
  return `<p class="note"><span class="spin"></span> Checking your soil in the background…</p>`;
}

function varietyRow(v) {
  const extra = [MATURITY[v.maturity_group], v.confidence === 'low' ? '<span class="tag t-note">Estimated data</span>' : ''].filter(Boolean).join(' ');
  return `<button class="crow" style="width:100%;text-align:left" onclick="openAddCrop('${esc(v.id)}')">
    <span class="n">${esc(v.name)}<span class="note" style="display:block;font-weight:500">${extra}</span></span>
    <span class="textbtn">Add</span></button>`;
}

function cropFamily(code) {
  const list = VARIETIES.filter(v => v.crop_code === code);
  const groups = {};
  list.forEach(v => (groups[v.subtype || 'other'] ??= []).push(v));
  const inner = Object.entries(groups).map(([sub, vs]) =>
    `<div class="sec" style="margin:1rem 0 .2rem">${esc(SUBTYPE_NAMES[sub] || sub)}</div>${vs.map(varietyRow).join('')}`).join('');
  const summary = `<span style="font-size:1.6rem">${emo(CROP_ICON[code])}</span><span class="grow"><span class="sumt" style="display:block">${CROP_NAMES[code]}</span><span class="sums">${list.length} types</span></span>`;
  return acc('fam-' + code, summary, inner);
}

SCREENS.crops = () => {
  let list;
  if (UI.varErr) list = `<div class="banner">We couldn’t load the crop list (${esc(UI.varErr)}). <button class="textbtn" onclick="UI.varErr='';loadVarieties()">Try again</button></div>`;
  else if (!VARIETIES.length) list = `<p class="body"><span class="spin"></span> Loading crops…</p>`;
  else list = Object.keys(CROP_NAMES).filter(code => VARIETIES.some(v => v.crop_code === code)).map(cropFamily).join('');

  const mine = S.crops.length ? `<div class="sec">Your crops</div><div class="card">${S.crops.map(c => `
      <div class="kv" style="align-items:center"><span class="grow"><b style="display:block">${esc(vName(c.variety_id))}</b><span class="note">${cropLine(c)}</span></span>
      <button class="textbtn" onclick="removeCrop('${c.id}')" aria-label="Remove ${esc(vName(c.variety_id))}">Remove</button></div>`).join('')}</div>` : '';

  const n = S.crops.length;
  return `
  <div class="scroll">
    <h1 style="text-align:center">What are you growing?</h1>
    <div style="text-align:center;margin:.5rem 0 .4rem">${soilStatus()}</div>
    ${mine}
    <div class="sec">Add a crop · tap to open</div>
    ${list}
  </div>
  <div class="foot">
    <button class="big ${n ? '' : 'soft'}" onclick="${n ? "go('home')" : "UI.cropErr=true;render()"}">Done →</button>
    ${!n && UI.cropErr ? '<p class="err" style="text-align:center">Add at least one crop first.</p>' : ''}
  </div>`;
};

function openAddCrop(id) {
  const now = new Date();
  UI.add = {id, status: 'growing', m: now.getMonth(), y: now.getFullYear(), part: '15'};
  drawAddSheet();
}

function drawAddSheet() {
  const a = UI.add, v = vById(a.id), now = new Date();
  const years = [now.getFullYear(), now.getFullYear() - 1];
  const opt = (val, lab, cur) => `<option value="${val}" ${val === cur ? 'selected' : ''}>${lab}</option>`;
  const when = a.status !== 'growing' ? '' : `
    <div class="picker" style="margin-top:1rem">
      <label>Month<select id="am" onchange="UI.add.m=+this.value">${MONTHS.map((m, i) => opt(i, m, a.m)).join('')}</select></label>
      <label>Year<select id="ay" onchange="UI.add.y=+this.value">${years.map(y => opt(y, y, a.y)).join('')}</select></label>
    </div>
    <div style="font-weight:800;color:var(--black);margin:1rem 0 .4rem">Which part of the month?</div>
    <div class="seg">${PARTS.map(([val, lab]) => `<button aria-pressed="${a.part === val}" onclick="UI.add.part='${val}';drawAddSheet()">${lab}</button>`).join('')}</div>`;
  sheet(esc(v.name), `
    <div class="seg">
      <button aria-pressed="${a.status === 'growing'}" onclick="UI.add.status='growing';drawAddSheet()">Already planted</button>
      <button aria-pressed="${a.status === 'planned'}" onclick="UI.add.status='planned';drawAddSheet()">Planning to sow</button>
    </div>
    ${when}
    <p id="aerr" class="err" style="margin-top:.8rem" aria-live="polite"></p>
    <button class="big" style="margin-top:.6rem" onclick="saveCrop()">Add ${esc(v.name)}</button>`);
}

function saveCrop() {
  const a = UI.add, crop = {id: 'c' + Date.now(), variety_id: a.id, status: a.status};
  if (a.status === 'growing') {
    const date = `${a.y}-${String(a.m + 1).padStart(2, '0')}-${a.part}`;
    if (new Date(date + 'T12:00') > new Date()) { $('#aerr').textContent = 'That date is in the future. Choose “Planning to sow” or an earlier month.'; return; }
    crop.sowing_date = date;
  }
  S.crops.push(crop); UI.analysis = null; save(); closeModal(); UI.cropErr = false; render();
  toast(`${vName(a.id)} added`);
}

function removeCrop(id) {
  S.crops = S.crops.filter(c => c.id !== id); UI.analysis = null; save(); render();
}

