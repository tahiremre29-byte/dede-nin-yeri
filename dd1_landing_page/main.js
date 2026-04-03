// ── Nav Scroll Effect ────────────────────────────────────────────────────────
const nav = document.getElementById('main-nav');
window.addEventListener('scroll', () => {
    nav.classList.toggle('scrolled', window.scrollY > 60);
});

// ── T/S Toggle ───────────────────────────────────────────────────────────────
const toggleBtn = document.getElementById('ts-toggle-btn');
const tsFields  = document.getElementById('ts-fields');
if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
        const open = !tsFields.classList.contains('hidden');
        tsFields.classList.toggle('hidden', open);
        toggleBtn.querySelector('span').textContent = open ? '▶' : '▼';
    });
}

// ── Animated Stat Counters ────────────────────────────────────────────────────
function animateCounters() {
    document.querySelectorAll('.stat-num[data-target]').forEach(el => {
        const target = parseInt(el.dataset.target, 10);
        let current = 0;
        const step = Math.max(1, Math.ceil(target / 40));
        const interval = setInterval(() => {
            current = Math.min(current + step, target);
            el.textContent = current;
            if (current >= target) clearInterval(interval);
        }, 40);
    });
}

// Observe stats section
const statsSection = document.querySelector('.stats-section');
if (statsSection) {
    const observer = new IntersectionObserver(entries => {
        if (entries[0].isIntersecting) {
            animateCounters();
            observer.disconnect();
        }
    }, { threshold: 0.4 });
    observer.observe(statsSection);
}

// ── Calculator Form ───────────────────────────────────────────────────────────
const calcForm  = document.getElementById('dd1-quick-calc');
const resultsDiv = document.getElementById('results');
const calcBtn   = document.getElementById('calc-btn');
const calcBtnText = document.getElementById('calc-btn-text');

if (calcForm) {
    calcForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        calcBtnText.textContent = 'Hesaplanıyor...';
        calcBtn.disabled = true;

        const diameter = parseInt(document.getElementById('diameter').value);
        const vehicle  = document.getElementById('vehicle').value;
        const purpose  = document.getElementById('purpose').value;

        // T/S parametreler (opsiyonel)
        const fsVal  = parseFloat(document.getElementById('fs')?.value);
        const qtsVal = parseFloat(document.getElementById('qts')?.value);
        const vasVal = parseFloat(document.getElementById('vas')?.value);
        const rmsVal = parseInt(document.getElementById('rms')?.value) || 500;

        const payload = {
            diameter_inch:         diameter,
            rms_power:             rmsVal,
            vehicle:               vehicle,
            purpose:               purpose,
            material_thickness_mm: 18,
            enclosure_type:        'aero',
            ...(fsVal && qtsVal && vasVal ? { fs: fsVal, qts: qtsVal, vas: vasVal } : {})
        };

        try {
            const response = await fetch('http://localhost:8000/design/enclosure', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': 'premium-dev'
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) throw new Error(`Motor yanıt vermedi (${response.status})`);

            const data = await response.json();

            // Sonuçları doldur
            resultsDiv.classList.remove('hidden');

            document.getElementById('res-volume').textContent = `${data.net_volume_l} L`;
            document.getElementById('res-tuning').textContent = `${data.tuning_hz} Hz`;
            document.getElementById('res-spl').textContent    = data.peak_spl_db ? `${data.peak_spl_db} dB` : '--';
            document.getElementById('res-pv').textContent     = data.port_velocity_ms ? `${data.port_velocity_ms} m/s` : '--';
            document.getElementById('res-f3').textContent     = data.f3_hz ? `${data.f3_hz} Hz` : '--';
            document.getElementById('res-mode').textContent   = data.mode || '--';

            const adviceText = (data.acoustic_advice || 'Tavsiye alınamadı.')
                .replace(/\n\n/g, '<br><br>')
                .replace(/\n/g, '<br>');
            document.getElementById('res-advice').innerHTML = adviceText;

            resultsDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

        } catch (err) {
            const advice = document.getElementById('res-advice');
            resultsDiv.classList.remove('hidden');
            advice.textContent = `⚠️ ${err.message}. Backend sunucusunun çalıştığından emin olun: python main.py`;
            document.getElementById('res-volume').textContent = '--';
            document.getElementById('res-tuning').textContent = '--';
            document.getElementById('res-spl').textContent = '--';
        } finally {
            calcBtnText.textContent = 'Hesaplamayı Başlat';
            calcBtn.disabled = false;
        }
    });
}

console.log('DD1 Platform v2.0 — AI-Powered Acoustic Engine Loaded');
