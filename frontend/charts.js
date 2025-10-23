///
// Fichier des graphiques IAQ
///

fetch("http://localhost:8000/iaq/all")
    .then(response => response.json())
    .then(data => {
    const timestamps = data.map(d => d.timestamp);
    const co2 = data.map(d => d.co2);
    const pm25 = data.map(d => d.pm25);
    const tvoc = data.map(d => d.tvoc);
    const temperature = data.map(d => d.temperature);
    const humidity = data.map(d => d.humidity);

    // Graphique CO₂
    Plotly.newPlot('co2-chart', [{
        x: timestamps,
        y: co2,
        type: 'scatter',
        mode: 'lines+markers',
        name: 'CO₂ (ppm)',
        line: { color: 'green' }
    }], {
        title: 'Évolution du CO₂',
        xaxis: { title: 'Heure' },
        yaxis: { title: 'ppm' }
    });

    // Graphique PM2.5
    Plotly.newPlot('pm25-chart', [{
        x: timestamps,
        y: pm25,
        type: 'bar',
        name: 'PM2.5 (µg/m³)',
        marker: { color: 'orange' }
    }], {
        title: 'Concentration de PM2.5',
        xaxis: { title: 'Heure' },
        yaxis: { title: 'µg/m³' }
    });

    // Graphique Température & Humidité
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
        line: { color: 'blue' }
    }], {
        title: 'Température & Humidité',
        xaxis: { title: 'Heure' },
        yaxis: { title: 'Valeurs' }
    });

    // Graphique TVOC
    Plotly.newPlot('tvoc-chart', [{
        x: timestamps,
        y: tvoc,
        type: 'scatter',
        name: 'TVOC (mg/m³)',
        line: { color: 'purple' }
    }], {
        title: 'Concentration de TVOC',
        xaxis: { title: 'Heure' },
        yaxis: { title: 'mg/m³' }
    });
    });