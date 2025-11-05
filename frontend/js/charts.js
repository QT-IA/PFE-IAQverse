// Configuration
const REFRESH_MS = 3000; // 3s
/* Fichier des graphiques IAQ - mise à jour dynamique sans rechargement de la page */
const API_URL_WINDOW = "http://localhost:8000/iaq/window";
const chartIds = ["co2-chart", "pm25-chart", "comfort-chart", "tvoc-chart"];
// Evite le conflit avec la variable globale "config" utilisée par index.html
const plotlyConfig = { responsive: true, displayModeBar: false };

// Utiliser des variables globales (var) pour partager avec index.html
var currentEnseigne = window.currentEnseigne || "Maison";
var currentSalle = window.currentSalle || "Salon";
let seenTimestamps = new Set(); // pour déduplication et append

// Affiche un message si aucune donnée
function renderEmpty(id, message = "Aucune donnée disponible") {
  const el = document.getElementById(id);
  if (el) el.innerHTML = `<div style="padding:16px;color:#666">${message}</div>`;
}

// Mise en page commune des graphiques
function makeCommonLayout(title, yTitle) {
  const isDark = document.documentElement.getAttribute('data-theme') === 'sombre';
  return {
    autosize: true,
    margin: { t: 40, r: 50, b: 50, l: 50 },
    xaxis: { title: "Heure", type: "date", color: isDark ? '#a8b2c1' : '#2c3e50', gridcolor: isDark ? '#3a4049' : '#e2e8f0' },
    title: { text: title, font: { color: isDark ? '#e4e7eb' : '#2c3e50' } },
    yaxis: { title: yTitle, color: isDark ? '#a8b2c1' : '#2c3e50', gridcolor: isDark ? '#3a4049' : '#e2e8f0' },
    font: { family: "Segoe UI, sans-serif", color: isDark ? '#e4e7eb' : '#2c3e50' },
    paper_bgcolor: isDark ? '#252930' : '#ffffff',
    plot_bgcolor: isDark ? '#252930' : '#ffffff'
  };
}

// Initialise les graphiques vides
function initEmptyCharts() {
  Plotly.newPlot("co2-chart", [{ x: [], y: [], type: "scatter", mode: "lines+markers" }], makeCommonLayout("Évolution du CO₂", "ppm"), plotlyConfig);
  Plotly.newPlot("pm25-chart", [{ x: [], y: [], type: "bar" }], makeCommonLayout("Concentration de PM2.5", "µg/m³"), plotlyConfig);
  Plotly.newPlot(
    "comfort-chart",
    [
      { x: [], y: [], type: "scatter", name: "Température (°C)", line: { color: "red" } },
      { x: [], y: [], type: "scatter", name: "Humidité (%)", yaxis: "y2", line: { color: "blue" } },
    ],
    Object.assign(makeCommonLayout("Température & Humidité", "Température (°C)"), { margin: { r: 100, l: 100}, yaxis2: { title: "Humidité (%)", overlaying: "y", side: "right" }, legend: { orientation: "h", y: -0.2 } }),
    plotlyConfig
  );
  Plotly.newPlot("tvoc-chart", [{ x: [], y: [], type: "scatter" }], makeCommonLayout("Concentration de TVOC", "mg/m³"), plotlyConfig);
}

// Réinitialise les graphiques (appelé lors d'un changement d'enseigne/salle)
function resetCharts() {
  chartIds.forEach(id => { const el = document.getElementById(id); if (el) el.innerHTML = ""; });
  initEmptyCharts();
  seenTimestamps = new Set();
}

// Transforme les données en traces Plotly
function buildTracesFromData(data) {
  const timestamps = data.map((d) => (d.timestamp ? new Date(d.timestamp) : null));
  return {
    co2: [{ x: timestamps, y: data.map(d => d.co2), type: "scatter", mode: "lines+markers", name: "CO₂ (ppm)", line: { color: "green" }, marker: { size: 6 } }],
    pm25: [{ x: timestamps, y: data.map(d => d.pm25), type: "bar", name: "PM2.5 (µg/m³)", marker: { color: "orange" } }],
    comfort: [
      { x: timestamps, y: data.map(d => d.temperature), type: "scatter", name: "Température (°C)", line: { color: "red" } },
      { x: timestamps, y: data.map(d => d.humidity), type: "scatter", name: "Humidité (%)", line: { color: "blue" }, yaxis: "y2" },
    ],
    tvoc: [{ x: timestamps, y: data.map(d => d.tvoc), type: "scatter", name: "TVOC (mg/m³)", line: { color: "purple" } }],
  };
}

// Met à jour les graphiques avec les données
function updateChartsWithData(data) {
  if (!Array.isArray(data) || data.length === 0) { chartIds.forEach(id => renderEmpty(id)); return; }
  const traces = buildTracesFromData(data);
  Plotly.react("co2-chart", traces.co2, makeCommonLayout("Évolution du CO₂", "ppm"), plotlyConfig);
  Plotly.react("pm25-chart", traces.pm25, makeCommonLayout("Concentration de PM2.5", "µg/m³"), plotlyConfig);
  Plotly.react("comfort-chart", traces.comfort, Object.assign(makeCommonLayout("Température & Humidité", "Température (°C)"), { yaxis2: { title: "Humidité (%)", overlaying: "y", side: "right" }, legend: { orientation: "h", x: 0.5, xanchor: "center", y: -0.5, yanchor: "bottom" } }), plotlyConfig);
  Plotly.react("tvoc-chart", traces.tvoc, makeCommonLayout("Concentration de TVOC", "mg/m³"), plotlyConfig);
}

// Récupère les données depuis l’API
async function fetchAndUpdate() {
  try {
    if (typeof window === "undefined" || typeof window.fetch !== "function") throw new Error("fetch indisponible dans ce contexte");
    const params = new URLSearchParams({ enseigne: currentEnseigne || "", salle: currentSalle || "", hours: String(1), step: "5min" });
    const url = `${API_URL_WINDOW}?${params.toString()}`;
    console.debug("IAQ fetch:", url);
    const res = await window.fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (!Array.isArray(data) || data.length === 0) { chartIds.forEach(id => renderEmpty(id, "Pas de données")); return; }
    data.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    const fresh = data.filter(d => d && d.timestamp && !seenTimestamps.has(d.timestamp));
    if (fresh.length === 0) return;
    fresh.forEach(d => seenTimestamps.add(d.timestamp));
    const co2El = document.getElementById("co2-chart");
    const hasData = co2El && co2El.data && co2El.data[0] && co2El.data[0].x && co2El.data[0].x.length > 0;
    if (!hasData) { updateChartsWithData(data); return; }
    const xs = fresh.map(d => (d.timestamp ? new Date(d.timestamp) : null));
    Plotly.extendTraces("co2-chart", { x: [xs], y: [fresh.map(d => d.co2)] }, [0]);
    Plotly.extendTraces("pm25-chart", { x: [xs], y: [fresh.map(d => d.pm25)] }, [0]);
    Plotly.extendTraces("comfort-chart", { x: [xs, xs], y: [fresh.map(d => d.temperature), fresh.map(d => d.humidity)] }, [0, 1]);
    Plotly.extendTraces("tvoc-chart", { x: [xs], y: [fresh.map(d => d.tvoc)] }, [0]);
  } catch (err) {
    console.error("Erreur fetch IAQ :", err);
    chartIds.forEach(id => { const el = document.getElementById(id); if (el) el.innerHTML = `<div style="padding:16px;color:#c00">Erreur: ${err.message}</div>`; });
  }
}

/* Initialisation */
if (typeof window !== "undefined" && typeof Plotly !== "undefined") {
  initEmptyCharts();
  fetchAndUpdate();
  setInterval(fetchAndUpdate, REFRESH_MS);
  let resizeTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      chartIds.forEach((id) => { const gd = document.getElementById(id); if (gd && typeof Plotly.Plots?.resize === "function") Plotly.Plots.resize(gd); });
    }, 150);
  });
} else {
  console.warn("Charts non initialisés : fenêtre ou Plotly introuvable.");
}

// Exposer au global
if (typeof window !== "undefined") {
  window.resetCharts = resetCharts;
  window.fetchAndUpdate = fetchAndUpdate;
  window.currentEnseigne = currentEnseigne;
  window.currentSalle = currentSalle;
  window.refreshChartsTheme = refreshChartsTheme;
}

// Mise à jour du thème
function refreshChartsTheme() {
  chartIds.forEach(id => {
    const gd = document.getElementById(id);
    if (gd && gd.data && gd.data.length > 0) {
      let title = ""; let yaxisTitle = "";
      switch(id) {
        case "co2-chart": title = "Évolution du CO₂"; yaxisTitle = "ppm"; break;
        case "pm25-chart": title = "Concentration de PM2.5"; yaxisTitle = "µg/m³"; break;
        case "comfort-chart": title = "Température & Humidité"; yaxisTitle = "Température (°C)"; break;
        case "tvoc-chart": title = "Concentration de TVOC"; yaxisTitle = "mg/m³"; break;
      }
      const newLayout = makeCommonLayout(title, yaxisTitle);
      if (id === "comfort-chart" && gd.layout.yaxis2) { newLayout.yaxis2 = gd.layout.yaxis2; newLayout.legend = gd.layout.legend; }
      Plotly.react(id, gd.data, newLayout, plotlyConfig);
    }
  });
}
