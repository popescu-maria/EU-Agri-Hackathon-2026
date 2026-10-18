const API = {
  async call(path, body) {
    const opts = body === undefined ? {} : {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    };
    const r = await fetch(path, opts);
    if (!r.ok) {
      let msg;
      try { msg = (await r.json()).detail; } catch (e) {}
      throw new Error(msg || `Server error ${r.status}`);
    }
    return r.json();
  },
  varieties: ()      => API.call('/api/varieties'),
  setup:     loc     => API.call('/api/setup', loc),          
  analyse:   payload => API.call('/api/analyse', payload),
  weather:   (lat, lon, demo) => API.call(`/api/weather?lat=${lat}&lon=${lon}${demo ? '&demo=' + demo : ''}`)   
};