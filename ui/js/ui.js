const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const emo = (s, size) => `<span class="e"${size ? ` style="font-size:${size}"` : ''} aria-hidden="true">${s}</span>`;
const logoImg = w => `<img src="img/logo.png" alt="Stream" width="${w}" height="${w}" style="width:${w}px;height:${w}px;border-radius:50%">`;

const SCREENS = {};
const AFTER = {};
const UI = {open: new Set()};

function go(step) {
  S.step = step; save(); render();
  const sc = $('.scroll'); if (sc) sc.scrollTop = 0;
}

function render() {
  const step = SCREENS[S.step] ? S.step : 'welcome';
  const app = $('#app'), old = app.querySelector('.scroll');
  const keep = (UI.screen === step && old) ? old.scrollTop : 0;
  app.innerHTML = SCREENS[step]();
  UI.screen = step;
  app.querySelectorAll('details.acc[data-id]').forEach(d =>
    d.addEventListener('toggle', () => d.open ? UI.open.add(d.dataset.id) : UI.open.delete(d.dataset.id)));
  const sc = app.querySelector('.scroll'); if (sc) sc.scrollTop = keep;
  if (AFTER[step]) AFTER[step]();
}

function acc(id, summary, inner, cls = '') {
  return `<details class="acc ${cls}" data-id="${id}" ${UI.open.has(id) ? 'open' : ''}><summary>${summary}</summary><div class="in">${inner}</div></details>`;
}

function sheet(title, body) {
  $('#modal').innerHTML = `<div class="dim" onclick="if(event.target===this)closeModal()">
    <div class="sheet" role="dialog" aria-modal="true" aria-label="${esc(title)}">
      <div class="hd"><b style="font-size:1.3rem;color:var(--black)">${title}</b><button class="xbtn" onclick="closeModal()" aria-label="Close">✕</button></div>
      <div class="bd">${body}</div></div></div>`;
  $('#modal .xbtn').focus();
}
function closeModal() { $('#modal').innerHTML = ''; }
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });

function toast(msg) {
  const t = document.createElement('div');
  t.className = 'toast'; t.setAttribute('role', 'status'); t.textContent = msg;
  $('#device').appendChild(t);
  setTimeout(() => t.remove(), 4000);
}