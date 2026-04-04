document.addEventListener("DOMContentLoaded", () => {
    // Buttons and elements
    const btnCalculate = document.getElementById("btnCalculate");
    const btnProduce = document.getElementById("btnProduce");
    const resultCard = document.getElementById("designResultCard");
    const downloadArea = document.getElementById("downloadArea");
    const btnDownload = document.getElementById("btnDownload");
    
    // Form fields
    const fVehicle = document.getElementById("dfVehicle");
    const fPurpose = document.getElementById("dfPurpose");
    const fDiameter = document.getElementById("dfDiameter");
    const fPower = document.getElementById("dfPower");
    const fPortType = document.getElementById("dfPortType");
    const fThickness = document.getElementById("dfThickness");

    // Result fields
    const rDesignId = document.getElementById("resDesignId");
    const rLiters = document.getElementById("resLiters");
    const rTuning = document.getElementById("resTuning");
    const rSummary = document.getElementById("resSummary");

    let currentDesignId = null;

    // Local configuration URL changed to modular config
    const BASE_URL = window.ENV ? window.ENV.API_BASE_URL : "";

    btnCalculate.addEventListener("click", async () => {
        btnCalculate.innerText = "Akustik Hesaplanıyor...";
        btnCalculate.disabled = true;
        resultCard.style.display = "none";
        downloadArea.style.display = "none";
        
        try {
            let sessId = localStorage.getItem('dd1_session_id') || "";
            const payload = {
                session_id: sessId,
                vehicle: fVehicle.value,
                purpose: fPurpose.value,
                diameter_inch: parseInt(fDiameter.value),
                rms_power: parseInt(fPower.value),
                material_thickness_mm: parseInt(fThickness.value),
                port_type: fPortType.value
            };

            const response = await fetch(`${BASE_URL}/api/design/calculate`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            
            const data = await response.json();
            if (!response.ok) {
                throw new Error(JSON.stringify(data.detail || data));
            }

            // Fill the results card
            currentDesignId = data.design_id || null;
            rDesignId.innerText = currentDesignId ? currentDesignId : "HATA";
            rSummary.innerText = data.summary || data.message || "Mühürlendi.";
            
            // Populate the newly added API fields directly from the backend
            rLiters.innerText = data.net_volume_l !== undefined ? data.net_volume_l : "N/A";
            rTuning.innerText = data.tuning_hz !== undefined ? data.tuning_hz : "N/A";
            
            // For box type, look at what user selected since it calculates for that, or get it from backend if returned.
            const portType = fPortType.value;
            const resBoxType = document.getElementById("resBoxType");
            if (resBoxType) {
                resBoxType.innerText = (portType === 'ported') ? 'Portlu Kutu' : (portType === 'sealed' ? 'Kapalı Kutu' : 'Bandpass');
            }
            
            // Safety measure: Only show Produce button if we have a valid locked design ID and liters
            if (currentDesignId && data.net_volume_l !== undefined) {
                btnProduce.style.display = "block";
                btnProduce.disabled = false;
            } else {
                btnProduce.style.display = "none";
                btnProduce.disabled = true;
            }
            
            resultCard.style.display = "block";

            if (window.UI_Audio) window.UI_Audio.click(); 

        } catch (error) {
            alert(`Hata: ${error.message}`);
        } finally {
            btnCalculate.innerText = "1. Akustik Hesapla (Calculate)";
            btnCalculate.disabled = false;
        }
    });

    btnProduce.addEventListener("click", async () => {
        if (!currentDesignId) return;

        btnProduce.innerText = "Parça Kesim Dosyası Oluşturuluyor...";
        btnProduce.disabled = true;
        downloadArea.style.display = "none";

        try {
            // ONLY pass design_id as requested by the Immutable contract! No overrides.
            const payload = {
                design_id: currentDesignId
            };

            const response = await fetch(`${BASE_URL}/api/design/produce`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            const data = await response.json();
            if (!response.ok) {
                throw new Error(JSON.stringify(data.detail || data));
            }

            // Show download link
            btnDownload.href = `${BASE_URL}${data.download_url}`;
            downloadArea.style.display = "block";

            if (window.UI_Audio) window.UI_Audio.click();

        } catch (error) {
            alert(`Üretim Hatası: ${error.message}`);
        } finally {
            btnProduce.innerText = "2. DXF Üret (Produce)";
            btnProduce.disabled = false;
        }
    });

    // Language Modes Simulation
    const modeBtns = document.querySelectorAll(".mode-btn");
    modeBtns.forEach(btn => {
        btn.addEventListener("click", (e) => {
            modeBtns.forEach(b => b.classList.remove("active", "selected"));
            e.target.classList.add("active", "selected");
            e.target.style.background = "var(--cyan-glow)";
            e.target.style.color = "#000";
            alert(`Sistem Dili Değiştirildi: ${e.target.dataset.mode}`);
        });
    });
});
