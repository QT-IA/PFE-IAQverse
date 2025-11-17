// Utilitaires API partagés pour les prédictions
async function getPredictedScore(enseigne, salle) {
    console.log(`[api.js] getPredictedScore called for enseigne="${enseigne}", salle="${salle}"`);
    const key = `lastPrediction_${encodeURIComponent(
    enseigne
    )}_${encodeURIComponent(salle)}`;
    try {
    const stored = localStorage.getItem(key);
    if (stored) {
        const parsed = JSON.parse(stored);
        if (Date.now() - parsed.fetchedAt < 30000) {
        console.log(`[api.js] Using cached prediction for ${enseigne}/${salle}:`, parsed.predicted_score);
        return parsed; // TTL 30s
        }
    }
    } catch (e) {}
    const params = new URLSearchParams({ enseigne, salle });
    const url = `http://localhost:8000/api/predict/score?${params.toString()}`;
    console.log(`[api.js] Fetching prediction for ${enseigne}/${salle} from:`, url);
    const res = await fetch(
    `http://localhost:8000/api/predict/score?${params.toString()}`,
    { cache: "no-store" }
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (data && typeof data.predicted_score === "number") {
    const payload = { ...data, fetchedAt: Date.now() };
    localStorage.setItem(key, JSON.stringify(payload));
    console.log(`[api.js] Fetched and cached prediction for ${enseigne}/${salle}:`, data.predicted_score);
    return payload;
    }
    console.log(`[api.js] No valid prediction for ${enseigne}/${salle}`);
    return null;
}
