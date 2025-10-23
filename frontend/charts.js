///
// Fichier des graphiques IAQ
///

(async () => {
  try {
    const res = await fetch('http://localhost:8000/iaq/all');
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (!Array.isArray(data) || data.length === 0) {
      console.warn('Aucune donnée IAQ reçue pour tracer les graphiques.');
      ['co2-chart','pm25-chart','comfort-chart','tvoc-chart'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = '<div style="padding:16px;color:#666">Aucune donnée disponible</div>';
      });
      return;
    }

    // Convertir les timestamps en Date pour un affichage temporel fiable
    const timestamps = data.map(d => d.timestamp ? new Date(d.timestamp) : null);
    const co2 = data.map(d => d.co2);
    const pm25 = data.map(d => d.pm25);
    const tvoc = data.map(d => d.tvoc);
    const temperature = data.map(d => d.temperature);
    const humidity = data.map(d => d.humidity);

    const commonLayout = {
      autosize: true,
      margin: { t: 40, r: 20, b: 50, l: 50 },
      xaxis: { title: 'Heure', type: 'date' },
      font: { family: 'Segoe UI, sans-serif' }
    };

    const config = { responsive: true, displayModeBar: false };

    // Graphique CO₂
    Plotly.newPlot('co2-chart', [{
      x: timestamps,
      y: co2,
      type: 'scatter',
      mode: 'lines+markers',
      name: 'CO₂ (ppm)',
      line: { color: 'green' },
      marker: { size: 6 }
    }], Object.assign({}, commonLayout, { title: 'Évolution du CO₂', yaxis: { title: 'ppm' } }), config);

    // Graphique PM2.5
    Plotly.newPlot('pm25-chart', [{
      x: timestamps,
      y: pm25,
      type: 'bar',
      name: 'PM2.5 (µg/m³)',
      marker: { color: 'orange' }
    }], Object.assign({}, commonLayout, { title: 'Concentration de PM2.5', yaxis: { title: 'µg/m³' } }), config);

    // Graphique Température & Humidité (deux axes Y)
    Plotly.newPlot('comfort-chart', [{
      x: timestamps,
      y: temperature,
      type: 'scatter',
      name: 'Température (°C)',
      line: { color: 'red' }
    }, {
      x: timestamps,
      y: humidity,
      type: 'scatter',
      name: 'Humidité (%)',
      line: { color: 'blue' },
      yaxis: 'y2'
    }], Object.assign({}, commonLayout, {
      title: 'Température & Humidité',
      yaxis: { title: 'Température (°C)' },
      yaxis2: { title: 'Humidité (%)', overlaying: 'y', side: 'right' }
    }), config);

    // Graphique TVOC
    Plotly.newPlot('tvoc-chart', [{
      x: timestamps,
      y: tvoc,
      type: 'scatter',
      name: 'TVOC (mg/m³)',
      line: { color: 'purple' }
    }], Object.assign({}, commonLayout, { title: 'Concentration de TVOC', yaxis: { title: 'mg/m³' } }), config);

    // Forcer un resize initial pour s'assurer que Plotly prend la taille CSS
    const chartIds = ['co2-chart', 'pm25-chart', 'comfort-chart', 'tvoc-chart'];
    chartIds.forEach(id => {
      const gd = document.getElementById(id);
      if (gd && typeof Plotly.Plots?.resize === 'function') Plotly.Plots.resize(gd);
    });

    // Redimensionnement responsive (throttle)
    let resizeTimer = null;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        chartIds.forEach(id => {
          const gd = document.getElementById(id);
          if (gd && typeof Plotly.Plots?.resize === 'function') Plotly.Plots.resize(gd);
        });
      }, 150);
    });
  } catch (err) {
    console.error('Erreur lors du chargement des graphiques IAQ :', err);
    ['co2-chart','pm25-chart','comfort-chart','tvoc-chart'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.innerHTML = `<div style="padding:16px;color:#c00">Erreur: ${err.message}</div>`;
    });
  }
})();