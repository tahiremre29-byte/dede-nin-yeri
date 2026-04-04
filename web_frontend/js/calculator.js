document.addEventListener("DOMContentLoaded", () => {
    const calcW = document.getElementById("calcW");
    const calcH = document.getElementById("calcH");
    const calcD = document.getElementById("calcD");
    const btnCalc = document.getElementById("btnCalc");
    const resultBox = document.getElementById("calcResultBox");
    const resultText = document.getElementById("calcResult");

    btnCalc.addEventListener("click", () => {
        resultBox.classList.remove("hidden");
        
        const w = parseFloat(calcW.value);
        const h = parseFloat(calcH.value);
        const d = parseFloat(calcD.value);
        
        if (isNaN(w) || isNaN(h) || isNaN(d) || w <= 0 || h <= 0 || d <= 0) {
            resultText.innerText = "HATA";
            resultText.style.color = "#ff3333";
            resultText.style.textShadow = "0 0 10px rgba(255, 51, 51, 0.8)";
            resultBox.querySelector(".result-label").innerText = "Geçersiz veya Eksik Ölçü";
            return;
        }

        // Kuantum Hesaplama Hissi (Bekletme efekti)
        btnCalc.disabled = true;
        resultText.innerText = "...";
        resultText.style.color = "#00cc66";
        resultText.style.textShadow = "0 0 20px rgba(0,204,102,0.8)";
        resultBox.querySelector(".result-label").innerText = "Kuantum Simülasyonu Hesaplanıyor...";
        
        setTimeout(() => {
            btnCalc.disabled = false;
            
            // Gerçek Matematiksel Hacim: W x H x D / 1000 (Litreye Çevirim)
            const grossVolume = (w * h * d) / 1000;
            
            // %15 Ağaç (MDF) kalınlık toleransı ve Port kaybını düşürerek %85 Net hacim buluruz 
            const netVolume = grossVolume * 0.85; 
            
            // Virgülden sonra 1 hane
            resultText.innerText = netVolume.toFixed(1) + " L";
            resultBox.querySelector(".result-label").innerText = "İdeal Net Kabin Hacmi";

            // Eğer varsa UI Ses motorundan onay sesi çağır
            if (window.UI_Audio) window.UI_Audio.click();

        }, 800);
    });
});
