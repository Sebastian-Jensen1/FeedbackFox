// Henter en URL og parser JSON, kaster en beskrivende fejl hvis kaldet fejler.
async function fetchJson(url, options) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const errText = await response.text();
    throw new Error(`API-fejl (${response.status}): ${errText}`);
  }
  return response.json();
}

module.exports = { fetchJson };
