const STORE_KEY = 'stream.state';

const DEFAULTS = () => ({
  step: 'welcome', 
  loc: null,         
  soil: null,        
  region: null,     
  crops: [],         
  large: false,
  demo: null 
});

const S = (() => {
  try { return Object.assign(DEFAULTS(), JSON.parse(localStorage.getItem(STORE_KEY) || '{}')); }
  catch (e) { return DEFAULTS(); }
})();

function save() {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(S)); } catch (e) { /* private mode: keep going without saving */ }
}

function resetAll() {
  try { localStorage.removeItem(STORE_KEY); } catch (e) {}
  Object.keys(S).forEach(k => delete S[k]);
  Object.assign(S, DEFAULTS());
  UI.analysis = null;
  UI.weather = null;
  UI.loadErr = '';
  document.documentElement.classList.remove('large');
  closeModal();
  go('welcome');
}