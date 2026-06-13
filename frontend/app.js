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
const targetDateInput = document.getElementById('target-date');

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

// --- Helpers ---
function getWeekendDatesFromInput() {
    const val = targetDateInput.value;
    if (!val) return { sat: '', sun: '' }; // Fallback to backend auto
    
    // Parse selected date (e.g. "2026-06-07")
    const d = new Date(val);
    if (isNaN(d.getTime())) return { sat: '', sun: '' };
    
    // Find closest weekend (assuming the picked date is roughly around the target weekend)
    // If the picked date is a Sunday(0), Saturday is d - 1 day.
    // If the picked date is a Saturday(6), Sunday is d + 1 day.
    const day = d.getDay();
    let satDate = new Date(d);
    let sunDate = new Date(d);
    
    if (day === 6) {
        sunDate.setDate(d.getDate() + 1);
    } else if (day === 0) {
        satDate.setDate(d.getDate() - 1);
    } else {
        // If a weekday is picked, default to the upcoming weekend
        const daysToSat = 6 - day;
        satDate.setDate(d.getDate() + daysToSat);
        sunDate.setDate(d.getDate() + daysToSat + 1);
    }
    
    const fmt = (dt) => {
        const y = dt.getFullYear();
        const m = String(dt.getMonth() + 1).padStart(2, '0');
        const dNum = String(dt.getDate()).padStart(2, '0');
        return `${y}${m}${dNum}`;
    };
    
    return { sat: fmt(satDate), sun: fmt(sunDate) };
}

// --- Event Listeners ---
btnSat.addEventListener('click', async () => {
    btnSat.classList.add('hidden');
    spinnerSat.classList.remove('hidden');
    
    const dates = getWeekendDatesFromInput();
    const q = dates.sat ? `?target_date=${dates.sat}` : '';
    
    const data = await fetchAPI(`/saturday-ceiling${q}`);
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
    const dates = getWeekendDatesFromInput();
    const qTarget = dates.sun ? `&target_date=${dates.sun}` : '';
    
    const data = await fetchAPI(`/sunday-current?up_to_race=${upTo}${qTarget}`);
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

// --- Tab Switching Logic ---
const tabBtns = document.querySelectorAll('.tab-btn');
const viewSections = document.querySelectorAll('.view-section');

tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        tabBtns.forEach(b => b.classList.remove('active'));
        viewSections.forEach(v => v.classList.remove('active'));
        btn.classList.add('active');
        const targetId = btn.getAttribute('data-target');
        const targetView = document.getElementById(targetId);
        targetView.classList.add('active');
        targetView.style.display = 'block';
        
        // Hide others
        viewSections.forEach(v => {
            if (v.id !== targetId) v.style.display = 'none';
        });

        if (targetId === 'view-copier') {
            loadRacesForCopier();
        }
    });
});

// --- Copier Logic ---
const btnFetchOdds = document.getElementById('btn-fetch-odds');
const spinnerOdds = document.getElementById('spinner-odds');
const btnCopyOdds = document.getElementById('btn-copy-odds');
const oddsOutput = document.getElementById('odds-output');

// 競馬場コード変換用
const courseMap = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
    "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉"
};

function formatRaceName(raceId) {
    const courseCode = raceId.substring(4, 6);
    const raceNum = parseInt(raceId.substring(10, 12), 10);
    const courseName = courseMap[courseCode] || courseCode;
    return `${courseName}${raceNum}R`;
}

async function loadRacesForCopier() {
    // If races are already loaded for the current date, skip.
    // Otherwise fetch from /api/races
    
    // Instead of forcing Sunday, get the exact date from the input
    const val = targetDateInput.value;
    if (!val) return;
    
    const d = new Date(val);
    if (isNaN(d.getTime())) return;
    
    const targetDate = `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;

    // We can fetch races
    const data = await fetchAPI(`/races?target_date=${targetDate}`);
    if (data && data.races) {
        const races = data.races; // List of race IDs
        
        // Populate 5 dropdowns
        for (let i = 1; i <= 5; i++) {
            const select = document.getElementById(`win5-race-${i}`);
            // Keep the selected value if it exists and is in the new list, otherwise reset
            const currentVal = select.value;
            select.innerHTML = '';
            
            // Add an empty default option
            const defaultOpt = document.createElement('option');
            defaultOpt.value = "";
            defaultOpt.innerText = "選択してください";
            select.appendChild(defaultOpt);

            races.forEach(r => {
                const opt = document.createElement('option');
                opt.value = r;
                opt.innerText = formatRaceName(r);
                select.appendChild(opt);
            });

            // Try to auto-select if empty
            if (currentVal && races.includes(currentVal)) {
                select.value = currentVal;
            }
        }
        
        // Basic Auto-select logic (just tries to pick 10R and 11R)
        // This is a naive auto-select.
        if (!document.getElementById('win5-race-1').value) {
            const r10 = races.filter(r => r.endsWith('10'));
            const r11 = races.filter(r => r.endsWith('11'));
            const autoSelects = [...r10, ...r11].sort();
            for (let i = 0; i < Math.min(5, autoSelects.length); i++) {
                document.getElementById(`win5-race-${i+1}`).value = autoSelects[i];
            }
        }
    }
}

targetDateInput.addEventListener('change', () => {
    // Reload races if in copier view
    if (document.getElementById('view-copier').classList.contains('active')) {
        loadRacesForCopier();
    }
});

btnFetchOdds.addEventListener('click', async () => {
    btnFetchOdds.classList.add('hidden');
    spinnerOdds.classList.remove('hidden');
    
    // Collect selected race IDs
    const raceIds = [];
    for (let i = 1; i <= 5; i++) {
        const val = document.getElementById(`win5-race-${i}`).value;
        if (val) raceIds.push(val);
    }
    
    if (raceIds.length === 0) {
        oddsOutput.value = "レースが選択されていません。";
        spinnerOdds.classList.add('hidden');
        btnFetchOdds.classList.remove('hidden');
        return;
    }

    // Build Query
    const qParams = raceIds.map(id => `race_ids=${id}`).join('&');
    const data = await fetchAPI(`/win5-live-odds?${qParams}`);
    
    if (data && data.races) {
        let outText = "";
        for (const r_id of raceIds) {
            outText += `【${formatRaceName(r_id)}】\n`;
            const horses = data.races[r_id] || [];
            if (horses.length === 0) {
                outText += "データがありません\n\n";
                continue;
            }
            horses.forEach(h => {
                outText += `${h.popularity}番人気 [${h.waku}枠${h.umaban}番] ${h.horse_name} (${h.jockey}) ${h.odds}倍\n`;
            });
            outText += "\n";
        }
        oddsOutput.value = outText.trim();
    } else {
        oddsOutput.value = "取得に失敗しました。";
    }

    spinnerOdds.classList.add('hidden');
    btnFetchOdds.classList.remove('hidden');
});

btnCopyOdds.addEventListener('click', () => {
    oddsOutput.select();
    document.execCommand('copy');
    const originalText = btnCopyOdds.innerText;
    btnCopyOdds.innerText = "コピー完了！";
    btnCopyOdds.style.backgroundColor = "var(--accent-success)";
    setTimeout(() => {
        btnCopyOdds.innerText = originalText;
        btnCopyOdds.style.backgroundColor = "var(--accent-secondary)";
    }, 2000);
});

// Initialize init logic
document.addEventListener('DOMContentLoaded', () => {
    // set default input to today
    const now = new Date();
    targetDateInput.value = now.toISOString().split('T')[0];
});
