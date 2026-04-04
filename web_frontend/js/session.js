async function getOrCreateSession() {
    let sessionId = localStorage.getItem('dd1_session_id');
    if (!sessionId) {
        try {
            const resp = await fetch('/api/session/start', { method: 'POST' });
            if (resp.ok) {
                const data = await resp.json();
                sessionId = data.session_id;
                localStorage.setItem('dd1_session_id', sessionId);
                console.log("New session started:", sessionId);
            }
        } catch (e) {
            console.error("Failed to start session", e);
        }
    }
    
    // Feature flag fetch for Auth requirements
    try {
        const confResp = await fetch('/api/config/features');
        if (confResp.ok) {
            const features = await confResp.json();
            if (features.auth_registration_required) {
                const modal = document.getElementById('authOverlay');
                if (modal) modal.style.display = 'flex';
            }
        }
    } catch (e) {
        console.error("Failed to fetch features", e);
    }
    
    return sessionId;
}

// Call on load
document.addEventListener('DOMContentLoaded', () => {
    getOrCreateSession();

    const btnRegister = document.getElementById('btnRegister');
    if (btnRegister) {
        btnRegister.addEventListener('click', async () => {
            const name = document.getElementById('regName').value.trim();
            const email = document.getElementById('regEmail').value.trim();
            const gdpr = document.getElementById('gdprConsent').checked;
            const marketing = document.getElementById('marketingConsent').checked;
            const errorEl = document.getElementById('regError');

            if (!name || !email || !gdpr) {
                errorEl.innerText = "Lütfen ad, e-posta alanlarını doldurup kullanım koşullarını onaylayın.";
                errorEl.style.display = 'block';
                return;
            }

            const sessionId = localStorage.getItem('dd1_session_id');
            if (!sessionId) {
                errorEl.innerText = "Oturum bulunamadı. Sayfayı yenileyin.";
                errorEl.style.display = 'block';
                return;
            }

            errorEl.style.display = 'none';
            btnRegister.innerText = "Kaydediliyor...";
            btnRegister.disabled = true;

            const apiUrl = (window.ENV && window.ENV.API_BASE_URL) ? window.ENV.API_BASE_URL : '';

            try {
                const resp = await fetch(apiUrl + '/api/session/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        session_id: sessionId,
                        name: name,
                        email: email,
                        gdpr_consent: gdpr,
                        marketing_consent: marketing
                    })
                });

                if (resp.ok) {
                    const data = await resp.json();
                    if (data.status === "success") {
                        document.getElementById('authOverlay').style.display = 'none';
                    } else {
                        throw new Error(data.message || "Kayıt hatası.");
                    }
                } else {
                    throw new Error("Sunucu bağlantısı kurulamadı.");
                }
            } catch (e) {
                errorEl.innerText = e.message;
                errorEl.style.display = 'block';
            } finally {
                btnRegister.innerText = "Kayıt Ol ve Başla";
                btnRegister.disabled = false;
            }
        });
    }
});
