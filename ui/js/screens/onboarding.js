SCREENS.welcome = () => `
  <div class="scroll center">
    <h1>Welcome to</h1>${logoImg(220)}
    <p class="lead">Your friendly farming planner</p>
  </div>
  <div class="foot"><button class="big" onclick="go('value')">Start →</button></div>`;

SCREENS.value = () => `
  <div class="scroll center" style="gap:2.2rem">
    <p class="lead" style="font-size:1.4rem;font-weight:600">${emo('🗓️')} Plan your farm<br>in one place.</p>
    <p class="lead" style="font-size:1.4rem;font-weight:600">${emo('☁️')} Advice based on<br>your local weather.</p>
    <p class="lead" style="font-size:1.4rem;font-weight:600">${emo('🌊')} Be warned before<br>floods, frost and drought.</p>
  </div>
  <div class="foot"><button class="big" onclick="go('locate')">Next →</button></div>`;

const MAP_START = {lat: 46.25, lon: 23.67, zoom: 7};
let map = null, marker = null;
UI.pin = null;
UI.locErr = '';

SCREENS.locate = () => {
  const pin = UI.pin || S.loc;
  return `
  <div class="scroll" style="display:flex;flex-direction:column;gap:1rem">
    <h1 style="text-align:center">Where is your farm?</h1>
    <p class="lead" style="text-align:center">We use it to show your local weather and soil.</p>
    <button class="big" onclick="useGeo()">${emo('📍')} Use my location</button>
    <div id="map" class="mapbox" role="application" aria-label="Map. Tap to place the pin on your field."></div>
    <p class="note" style="text-align:center">${pin ? 'Drag the pin onto your field if it is not quite right.' : 'Or tap the map to put a pin on your field.'}</p>
    ${UI.locErr ? `<p class="err" role="alert">${UI.locErr}</p>` : ''}
    <p class="note" style="margin-top:auto"><b>Why is your location needed?</b><br><i>Stream</i> uses your approximate location to fetch accurate, localized weather and soil reports. This is purely for data reporting and has no physical impact on your farm. Your privacy is protected under our <button class="textbtn" style="font-size:inherit" onclick="openPolicy()">GDPR Privacy Policy</button></p>
  </div>
  <div class="foot"><button class="big ${pin ? '' : 'soft'}" onclick="confirmLocation()">Continue →</button></div>`;
};

AFTER.locate = () => {
  if (map) { map.remove(); map = null; marker = null; }
  const pin = UI.pin || S.loc;
  map = L.map('map', {zoomControl: true}).setView(pin ? [pin.lat, pin.lon] : [MAP_START.lat, MAP_START.lon], pin ? 15 : MAP_START.zoom);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom: 19, attribution: '© OpenStreetMap'}).addTo(map);
  map.on('click', e => setPin(e.latlng.lat, e.latlng.lng));
  if (pin) addMarker(pin.lat, pin.lon);
};

function addMarker(lat, lon) {
  marker = L.marker([lat, lon], {draggable: true}).addTo(map);
  marker.on('dragend', () => { const p = marker.getLatLng(); UI.pin = {lat: p.lat, lon: p.lng}; });
}

function setPin(lat, lon, zoom) {
  const first = !UI.pin && !S.loc;
  UI.pin = {lat, lon}; UI.locErr = '';
  if (marker) marker.setLatLng([lat, lon]); else addMarker(lat, lon);
  if (zoom) map.setView([lat, lon], zoom);
  if (first) render();
}

function useGeo() {
  if (!navigator.geolocation) { UI.locErr = 'This browser can’t share your location. Tap the map instead.'; return render(); }
  toast('Finding your farm…');
  navigator.geolocation.getCurrentPosition(
    p => setPin(p.coords.latitude, p.coords.longitude, 15),
    e => { UI.locErr = e.code === 1 ? 'Location is turned off for this page. Tap the map to place the pin instead.' : 'We couldn’t find your location. Tap the map to place the pin instead.'; render(); },
    {enableHighAccuracy: true, timeout: 12000, maximumAge: 60000});
}

function confirmLocation() {
  const pin = UI.pin || S.loc;
  if (!pin) { UI.locErr = 'Put a pin on your field first: tap “Use my location” or tap the map.'; return render(); }
  const loc = {lat: +pin.lat.toFixed(4), lon: +pin.lon.toFixed(4)};
  const moved = !S.loc || S.loc.lat !== loc.lat || S.loc.lon !== loc.lon;
  S.loc = loc; UI.pin = null; UI.locErr = ''; UI.analysis = null; UI.weather = null;
  if (moved || !S.soil) { S.soil = null; S.region = null; startSoilCheck(); }
  go(S.crops.length ? 'home' : 'crops');
}

let soilJob = null;
function startSoilCheck() {
  UI.soilErr = '';
  soilJob = API.setup(S.loc).then(r => {
    S.soil = r.soil; S.region = r.region; save(); render();
  }).catch(e => {
    soilJob = null;
    if (/outside/i.test(e.message)) {
      S.loc = null; S.soil = null; S.region = null;
      UI.locErr = 'Stream doesn’t cover this place yet. Please put the pin on a field inside the supported area.';
      go('locate');
    } else {
      UI.soilErr = e.message; render();
    }
    throw e;
  });
  soilJob.catch(() => {});
  return soilJob;
}

async function ensureSoil() {
  if (S.soil) return;
  if (!soilJob) startSoilCheck();
  await soilJob;
}

const POLICY = `<p><b>Effective Date:</b> October 16, 2026<br><b>Last Updated:</b> October 16, 2026</p>
<p>At <b>Stream</b>, we respect your privacy and are committed to protecting your personal data in strict compliance with the EU General Data Protection Regulation (GDPR - Regulation EU 2016/679). This Privacy Policy details how we handle your data when you use our application.</p>
<h4>1. Data Controller</h4><p>StreamApp<br>Contact Email: privacy@streamapp.com</p>
<h4>2. What Data We Collect</h4><p>To provide localized agricultural insights, Stream collects and processes the following data:</p><ul><li><b>Approximate Location Data</b>: We collect your device's approximate geographical coordinates (latitude and longitude) to fetch accurate, localized weather and soil reports.</li><li><b>Technical &amp; Usage Data</b>: Basic device information (e.g., app version, operating system) necessary for app stability and performance monitoring.</li></ul>
<h4>3. Legal Basis for Processing (GDPR Art. 6)</h4><ul><li><b>Consent (Art. 6(1)(a)):</b> We request your explicit consent before accessing your device's location. You can grant or revoke this at any time via your device settings.</li><li><b>Legitimate Interest (Art. 6(1)(f)):</b> Processing approximate coordinates is necessary to deliver the core service you request (localized data reporting). This data collection is purely informational and has no physical impact on your farm.</li></ul>
<h4>4. How Your Location Data is Used &amp; Stored</h4><ul><li><b>No Real-Time Tracking:</b> We do not continuously track your location in the background or build a profile of your movements. Location data is queried only when retrieving weather and soil reports.</li><li><b>Data Retention:</b> Location coordinates sent to fetch reports are processed in real-time or retained only as long as necessary to provide service logs, after which they are deleted or anonymized.</li></ul>
<h4>5. Third-Party Service Providers</h4><p>To deliver environmental forecasts, approximate coordinates may be passed to third-party weather and soil API providers acting as Data Processors under GDPR agreements.</p><ul><li>All personal data is processed within the European Union (EU). If a processor operates outside the EU, transfers are strictly governed by EU Standard Contractual Clauses (SCCs).</li><li>We <b>do not</b> sell, rent, or commercialize your location data.</li></ul>
<h4>6. Your Rights Under the GDPR</h4><p>Under Chapter III of the GDPR, as an EU resident you have the right to:</p><ul><li><b>Withdraw Consent</b>: Revoke location permission at any time in your device settings.</li><li><b>Access &amp; Erasure</b>: Request a copy of or request the deletion of your personal data.</li><li><b>Lodge a Complaint</b>: You have the right to lodge a complaint with your local EU Data Protection Authority (DPA) if you believe your data has been handled unlawfully.</li></ul>
<p>To exercise your rights, please contact our Data Protection Lead at privacy@streamapp.org.</p>
<h4>7. Changes to This Policy</h4><p>Any updates to this policy will be posted directly within the <b>Stream</b> app.</p>`;

function openPolicy() { sheet('GDPR Privacy Policy', `<div class="pol">${POLICY}</div>`); }