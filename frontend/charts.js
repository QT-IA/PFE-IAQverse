/* Fichier des graphiques IAQ - mise à jour dynamique sans rechargement de la page */

const API_URL = "http://localhost:8000/iaq/all";
const REFRESH_MS = 3000; // 3s
const chartIds = ["co2-chart", "pm25-chart", "comfort-chart", "tvoc-chart"];
const config = { responsive: true, displayModeBar: false };

function renderEmpty(id, message = "Aucune donnée disponible") {
  const el = document.getElementById(id);
  if (el)
    el.innerHTML = `<div style="padding:16px;color:#666">${message}</div>`;
}

function makeCommonLayout(title, yTitle) {
  return {
    autosize: true,
    margin: { t: 40, r: 20, b: 50, l: 50 },
    xaxis: { title: "Heure", type: "date" },
    title,
    yaxis: { title: yTitle },
    font: { family: "Segoe UI, sans-serif" },
  };
}

function initEmptyCharts() {
  // créer des placeholders pour que Plotly ait des graphs existants à updater
  Plotly.newPlot(
    "co2-chart",
    [{ x: [], y: [], type: "scatter", mode: "lines+markers" }],
    makeCommonLayout("Évolution du CO₂", "ppm"),
    config
  );
  Plotly.newPlot(
    "pm25-chart",
    [{ x: [], y: [], type: "bar" }],
    makeCommonLayout("Concentration de PM2.5", "µg/m³"),
    config
  );
  Plotly.newPlot(
    "comfort-chart",
    [
      {
        x: [],
        y: [],
        type: "scatter",
        name: "Température (°C)",
        line: { color: "red" },
      },
      {
        x: [],
        y: [],
        type: "scatter",
        name: "Humidité (%)",
        yaxis: "y2",
        line: { color: "blue" },
      },
    ],
    Object.assign(
      makeCommonLayout("Température & Humidité", "Température (°C)"),
      {
        yaxis2: { title: "Humidité (%)", overlaying: "y", side: "right" },
      }
    ),
    config
  );
  Plotly.newPlot(
    "tvoc-chart",
    [{ x: [], y: [], type: "scatter" }],
    makeCommonLayout("Concentration de TVOC", "mg/m³"),
    config
  );
}

function buildTracesFromData(data) {
  const timestamps = data.map((d) =>
    d.timestamp ? new Date(d.timestamp) : null
  );
  return {
    co2: [
      {
        x: timestamps,
        y: data.map((d) => d.co2),
        type: "scatter",
        mode: "lines+markers",
        name: "CO₂ (ppm)",
        line: { color: "green" },
        marker: { size: 6 },
      },
    ],
    pm25: [
      {
        x: timestamps,
        y: data.map((d) => d.pm25),
        type: "bar",
        name: "PM2.5 (µg/m³)",
        marker: { color: "orange" },
      },
    ],
    comfort: [
      {
        x: timestamps,
        y: data.map((d) => d.temperature),
        type: "scatter",
        name: "Température (°C)",
        line: { color: "red" },
      },
      {
        x: timestamps,
        y: data.map((d) => d.humidity),
        type: "scatter",
        name: "Humidité (%)",
        line: { color: "blue" },
        yaxis: "y2",
      },
    ],
    tvoc: [
      {
        x: timestamps,
        y: data.map((d) => d.tvoc),
        type: "scatter",
        name: "TVOC (mg/m³)",
        line: { color: "purple" },
      },
    ],
  };
}

function updateChartsWithData(data) {
  if (!Array.isArray(data) || data.length === 0) {
    chartIds.forEach((id) => renderEmpty(id, "Aucune donnée disponible"));
    return;
  }

  const traces = buildTracesFromData(data);

  // utiliser Plotly.react pour remplacer efficacement traces + layout
  Plotly.react(
    "co2-chart",
    traces.co2,
    makeCommonLayout("Évolution du CO₂", "ppm"),
    config
  );
  Plotly.react(
    "pm25-chart",
    traces.pm25,
    makeCommonLayout("Concentration de PM2.5", "µg/m³"),
    config
  );
  Plotly.react(
    "comfort-chart",
    traces.comfort,
    Object.assign(
      makeCommonLayout("Température & Humidité", "Température (°C)"),
      {
        yaxis2: { title: "Humidité (%)", overlaying: "y", side: "right" },
      }
    ),
    config
  );
  Plotly.react(
    "tvoc-chart",
    traces.tvoc,
    makeCommonLayout("Concentration de TVOC", "mg/m³"),
    config
  );
}

async function fetchAndUpdate() {
  try {
    const res = await fetch(API_URL);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    updateChartsWithData(data);
  } catch (err) {
    console.error("Erreur fetch IAQ :", err);
    chartIds.forEach((id) => {
      const el = document.getElementById(id);
      if (el)
        el.innerHTML = `<div style="padding:16px;color:#c00">Erreur: ${err.message}</div>`;
    });
  }
}

/* Initialisation */
if (typeof window !== "undefined" && typeof Plotly !== "undefined") {
  initEmptyCharts();
  // premier fetch immédiat
  fetchAndUpdate();
  // actualisations périodiques sans recharger la page
  setInterval(fetchAndUpdate, REFRESH_MS);

  // resize Plotly lorsque la fenêtre change (throttle)
  let resizeTimer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      chartIds.forEach((id) => {
        const gd = document.getElementById(id);
        if (gd && typeof Plotly.Plots?.resize === "function")
          Plotly.Plots.resize(gd);
      });
    }, 150);
  });
} else {
  // si exécuté dans un contexte sans DOM/Plotly
  console.warn("Charts non initialisés : fenêtre ou Plotly introuvable.");
}
