// DOM Elements
const elCeiling = document.getElementById('ceiling-value');
const elCurrent = document.getElementById('current-value');
const elRemaining = document.getElementById('remaining-value');
const elGaugeVal = document.getElementById('gauge-value');
const elMessage = document.getElementById('gauge-message');
const btnSat = document.getElementById('btn-fetch-sat');
const btnSun = document.getElementById('btn-fetch-sun');
const spinnerSat = document.getElementById('spinner-sat');
const spinnerSun = document.getElementById('spinner-sun');
const raceSelect = document.getElementById('race-select');
const statusIndicator = document.getElementById('status-indicator');

// State
let ceiling = null;
let current = null;

// API URL (Relative to root since we serve it from FastAPI)
const API_BASE = '/api';

// --- Functions ---
async function fetchAPI(endpoint) {
    try {
        const res = await fetch(`${API_BASE}${endpoint}`);
        if (!res.ok) throw new Error('API Error');
        statusIndicator.style.backgroundColor = 'var(--accent-success)';
        statusIndicator.style.boxShadow = '0 0 10px var(--accent-success)';
        return await res.json();
    } catch (e) {
        statusIndicator.style.backgroundColor = 'var(--accent-secondary)';
        statusIndicator.style.boxShadow = '0 0 10px var(--accent-secondary)';
        console.error(e);
        return null;
    }
}

function updateGauge() {
    if (ceiling === null || current === null) return;
    
    const remaining = ceiling - current;
    elRemaining.innerText = remaining > 0 ? remaining : 0;
    
    // Gauge max is ceiling.
    let ratio = 1 - (current / ceiling);
    if (ratio < 0) ratio = 0;
    if (ratio > 1) ratio = 1;
    
    // The SVG path has length ~125.6
    // offset 125.6 is empty (0%)
    // offset 0 is full (100%)
    const offset = 125.6 - (125.6 * ratio);
    elGaugeVal.style.strokeDashoffset = offset;
    
    // Color and message logic
    elMessage.className = 'gauge-message'; // reset
    if (remaining >= 20) {
        elGaugeVal.style.stroke = 'var(--accent-success)'; // Green
        elMessage.innerText = `和${remaining} 以内。大荒れまで許容される大波乱推奨！`;
        elMessage.classList.add('msg-safe');
    } else if (remaining >= 10) {
        elGaugeVal.style.stroke = 'var(--accent-warning)'; // Yellow
        elMessage.innerText = `和${remaining} 以内。中穴狙いが面白そう。`;
        elMessage.classList.add('msg-warn');
    } else if (remaining > 0) {
        elGaugeVal.style.stroke = 'var(--accent-secondary)'; // Red
        elMessage.innerText = `和${remaining} 以内。超ガチガチ決着濃厚！本命狙い！`;
        elMessage.classList.add('msg-danger');
    } else {
        elGaugeVal.style.stroke = 'var(--accent-secondary)';
        elMessage.innerText = `すでに上限突破！波乱の連続です。`;
        elMessage.classList.add('msg-danger');
    }
}

// --- Event Listeners ---
btnSat.addEventListener('click', async () => {
    btnSat.classList.add('hidden');
    spinnerSat.classList.remove('hidden');
    
    const data = await fetchAPI('/saturday-ceiling');
    if (data && data.ceiling !== undefined) {
        ceiling = data.ceiling;
        elCeiling.innerText = ceiling;
        updateGauge();
    }
    
    spinnerSat.classList.add('hidden');
    btnSat.classList.remove('hidden');
});

btnSun.addEventListener('click', async () => {
    btnSun.classList.add('hidden');
    spinnerSun.classList.remove('hidden');
    
    const upTo = raceSelect.value;
    const data = await fetchAPI(`/sunday-current?up_to_race=${upTo}`);
    if (data && data.current_sum !== undefined) {
        current = data.current_sum;
        elCurrent.innerText = current;
        updateGauge();
    }
    
    spinnerSun.classList.add('hidden');
    btnSun.classList.remove('hidden');
});

// Initial Ping
fetchAPI('/status');
