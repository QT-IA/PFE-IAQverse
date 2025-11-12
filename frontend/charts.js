// Configuration
const REFRESH_MS = 3000; // 3s
/* Fichier des graphiques IAQ - mise à jour dynamique sans rechargement de la page */
const API_URL_DATA = "http://localhost:8000/iaq/data";
const chartIds = ["co2-chart", "pm25-chart", "comfort-chart", "tvoc-chart"];
// Evite le conflit avec la variable globale "config" utilisée par index.html
const plotlyConfig = { responsive: true, displayModeBar: false };

// Utiliser des variables globales (var) pour partager avec index.html
var currentEnseigne = window.currentEnseigne || "Maison";
var currentSalle = window.currentSalle || "Salon";
let seenTimestamps = new Set(); // pour déduplication et append

// getApiUrl supprimé (filtrage côté client après récupération)

// Affiche un message si aucune donnée
function renderEmpty(id, message = "Aucune donnée disponible") {
  const el = document.getElementById(id);
  if (el) el.innerHTML = `<div style="padding:16px;color:#666">${message}</div>`;
}

// Mise en page commune des graphiques
function makeCommonLayout(title, yTitle) {
  // Détecter le thème actuel
  const isDark = document.documentElement.getAttribute('data-theme') === 'sombre';
  
  return {
    autosize: true,
    margin: { t: 40, r: 50, b: 50, l: 50 },
    xaxis: { 
      title: "Heure", 
      type: "date",
      color: isDark ? '#a8b2c1' : '#2c3e50',
      gridcolor: isDark ? '#3a4049' : '#e2e8f0'
    },
    title: {
      text: title,
      font: { color: isDark ? '#e4e7eb' : '#2c3e50' }
    },
    yaxis: { 
      title: yTitle,
      color: isDark ? '#a8b2c1' : '#2c3e50',
      gridcolor: isDark ? '#3a4049' : '#e2e8f0'
    },
    font: { 
      family: "Segoe UI, sans-serif",
      color: isDark ? '#e4e7eb' : '#2c3e50'
    },
    paper_bgcolor: isDark ? '#252930' : '#ffffff',
    plot_bgcolor: isDark ? '#252930' : '#ffffff'
  };
}

// Initialise les graphiques vides
function initEmptyCharts() {
  // créer des placeholders pour que Plotly ait des graphs existants à updater
  Plotly.newPlot(
    "co2-chart",
    [{ x: [], y: [], type: "scatter", mode: "lines+markers" }],
    makeCommonLayout("Évolution du CO₂", "ppm"),
    plotlyConfig
  );
  Plotly.newPlot(
    "pm25-chart",
    [{ x: [], y: [], type: "bar" }],
    makeCommonLayout("Concentration de PM2.5", "µg/m³"),
    plotlyConfig
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
    Object.assign(makeCommonLayout("Température & Humidité", "Température (°C)"), {
      margin: { r: 100, l: 100},
      yaxis2: { title: "Humidité (%)", overlaying: "y", side: "right" },
      // legend at the bottom of the graph
      legend: { orientation: "h", y: -0.2 },
    }),
    plotlyConfig
  );
  Plotly.newPlot(
    "tvoc-chart",
    [{ x: [], y: [], type: "scatter" }],
    makeCommonLayout("Concentration de TVOC", "mg/m³"),
    plotlyConfig
  );
}

// Réinitialise les graphiques (appelé lors d'un changement d'enseigne/salle)
function resetCharts() {
  // effacer le contenu et réinitialiser les figures vides
  chartIds.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.innerHTML = "";
  });
  initEmptyCharts();
  seenTimestamps = new Set();
}

// Transforme les données en traces Plotly
function buildTracesFromData(data) {
  const timestamps = data.map((d) => (d.timestamp ? new Date(d.timestamp) : null));
  return {
    co2: [{
      x: timestamps,
      y: data.map(d => d.co2),
      type: "scatter",
      mode: "lines+markers",
      name: "CO₂ (ppm)",
      line: { color: "green" },
      marker: { size: 6 },
    }],
    pm25: [{
      x: timestamps,
      y: data.map(d => d.pm25),
      type: "bar",
      name: "PM2.5 (µg/m³)",
      marker: { color: "orange" },
    }],
    comfort: [
      {
        x: timestamps,
        y: data.map(d => d.temperature),
        type: "scatter",
        name: "Température (°C)",
        line: { color: "red" },
      },
      {
        x: timestamps,
        y: data.map(d => d.humidity),
        type: "scatter",
        name: "Humidité (%)",
        line: { color: "blue" },
        yaxis: "y2",
      },
    ],
    tvoc: [{
      x: timestamps,
      y: data.map(d => d.tvoc),
      type: "scatter",
      name: "TVOC (mg/m³)",
      line: { color: "purple" },
    }],
  };
}

// Met à jour les graphiques avec les données
function updateChartsWithData(data) {
  if (!Array.isArray(data) || data.length === 0) {
    chartIds.forEach(id => renderEmpty(id));
    return;
  }

  const traces = buildTracesFromData(data);

  // utiliser Plotly.react pour remplacer efficacement traces + layout
  Plotly.react("co2-chart", traces.co2, makeCommonLayout("Évolution du CO₂", "ppm"), plotlyConfig);
  Plotly.react("pm25-chart", traces.pm25, makeCommonLayout("Concentration de PM2.5", "µg/m³"), plotlyConfig);
  Plotly.react(
    "comfort-chart",
    traces.comfort,
    Object.assign(makeCommonLayout("Température & Humidité", "Température (°C)"), {
      yaxis2: { title: "Humidité (%)", overlaying: "y", side: "right" },
      legend: { orientation: "h", x: 0.5, xanchor: "center", y: -0.5, yanchor: "bottom" }
    }),
    plotlyConfig
  );
  Plotly.react("tvoc-chart", traces.tvoc, makeCommonLayout("Concentration de TVOC", "mg/m³"), plotlyConfig);
}

// Pas de fenêtre glissante côté client : on récupère les agrégats côté serveur et on filtre ici

// Récupère les données depuis l’API
async function fetchAndUpdate() {
  try {
    if (typeof window === "undefined" || typeof window.fetch !== "function") {
      throw new Error("fetch indisponible dans ce contexte");
    }
    // demander la dernière heure pour l'enseigne/salle courants (filtrage côté serveur)
    const params = new URLSearchParams({
      enseigne: currentEnseigne || "",
      salle: currentSalle || "",
      hours: String(1),
      step: "5min",
    });
    const url = `${API_URL_DATA}?${params.toString()}`;
    console.debug("IAQ fetch:", url);
    const res = await window.fetch(url, { cache: "no-store" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (!Array.isArray(data) || data.length === 0) {
      chartIds.forEach(id => renderEmpty(id, "Pas de données"));
      return;
    }
    // trier par timestamp croissant et afficher
    data.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

    // Sélectionner uniquement les nouveaux points (par timestamp unique)
    const fresh = data.filter(d => d && d.timestamp && !seenTimestamps.has(d.timestamp));
    if (fresh.length === 0) return; // rien de nouveau

    // Marquer comme vus
    fresh.forEach(d => seenTimestamps.add(d.timestamp));

    // Si aucun point affiché jusqu'ici (graphiques vides), on dessine tout le set courant
    const co2El = document.getElementById("co2-chart");
    const hasData = co2El && co2El.data && co2El.data[0] && co2El.data[0].x && co2El.data[0].x.length > 0;
    if (!hasData) {
      updateChartsWithData(data);
      return;
    }

    // Sinon on fait un append incrémental pour chaque graphique
    const xs = fresh.map(d => (d.timestamp ? new Date(d.timestamp) : null));
    // CO2
    const co2 = fresh.map(d => d.co2);
    Plotly.extendTraces("co2-chart", { x: [xs], y: [co2] }, [0]);
    // PM2.5
    const pm25 = fresh.map(d => d.pm25);
    Plotly.extendTraces("pm25-chart", { x: [xs], y: [pm25] }, [0]);
    // Comfort (temp & humidity)
    const temp = fresh.map(d => d.temperature);
    const hum = fresh.map(d => d.humidity);
    Plotly.extendTraces("comfort-chart", { x: [xs, xs], y: [temp, hum] }, [0, 1]);
    // TVOC
    const tvoc = fresh.map(d => d.tvoc);
    Plotly.extendTraces("tvoc-chart", { x: [xs], y: [tvoc] }, [0]);
  } catch (err) {
    console.error("Erreur fetch IAQ :", err);
    chartIds.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.innerHTML = `<div style="padding:16px;color:#c00">Erreur: ${err.message}</div>`;
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
        if (gd && typeof Plotly.Plots?.resize === "function") Plotly.Plots.resize(gd);
      });
    }, 150);
  });
} else {
  // si exécuté dans un contexte sans DOM/Plotly
  console.warn("Charts non initialisés : fenêtre ou Plotly introuvable.");
}

// Exposer explicitement certaines fonctions/états au scope global
if (typeof window !== "undefined") {
  window.resetCharts = resetCharts;
  window.fetchAndUpdate = fetchAndUpdate;
  window.currentEnseigne = currentEnseigne;
  window.currentSalle = currentSalle;
  window.refreshChartsTheme = refreshChartsTheme;
}

// Fonction pour rafraîchir les graphiques lors du changement de thème
function refreshChartsTheme() {
  chartIds.forEach(id => {
    const gd = document.getElementById(id);
    if (gd && gd.data && gd.data.length > 0) {
      // Récupérer le layout actuel et le mettre à jour avec le nouveau thème
      const currentLayout = gd.layout;
      
      // Déterminer le titre actuel pour recréer le layout
      let title = "";
      let yaxisTitle = "";
      
      switch(id) {
        case "co2-chart":
          title = "Évolution du CO₂";
          yaxisTitle = "ppm";
          break;
        case "pm25-chart":
          title = "Concentration de PM2.5";
          yaxisTitle = "µg/m³";
          break;
        case "comfort-chart":
          title = "Température & Humidité";
          yaxisTitle = "Température (°C)";
          break;
        case "tvoc-chart":
          title = "Concentration de TVOC";
          yaxisTitle = "mg/m³";
          break;
      }
      
      // Créer un nouveau layout avec le thème actuel
      const newLayout = makeCommonLayout(title, yaxisTitle);
      
      // Préserver les configurations spécifiques (comme yaxis2 pour comfort-chart)
      if (id === "comfort-chart" && currentLayout.yaxis2) {
        newLayout.yaxis2 = currentLayout.yaxis2;
        newLayout.legend = currentLayout.legend;
      }
      
      // Mettre à jour le graphique avec le nouveau layout
      Plotly.react(id, gd.data, newLayout, plotlyConfig);
    }
  });
}
