document.addEventListener("DOMContentLoaded", () => {
    
    const inputElt = document.getElementById("precodeInput");
    const btnElt = document.getElementById("btnDecode");
    const resultBox = document.getElementById("resultBox");
    const resultCode = document.getElementById("resultCode");

    // Tıklanınca hesaplama yap
    btnElt.addEventListener("click", () => {
        const rawValue = inputElt.value.trim().toUpperCase();
        
        // Gösterim Kutusunu Temizle ve Görünür Yap
        resultBox.classList.remove("hidden");
        resultCode.classList.remove("error");
        resultCode.innerText = "----";
        
        // Küçük bir gecikme efekti vererek arkaplanda çalışıyormuş hissi (Sade, animasyonsuz ama bekletmeli)
        btnElt.textContent = "Hesaplanıyor...";
        btnElt.disabled = true;

        setTimeout(() => {
            btnElt.textContent = "Kodu Çöz";
            btnElt.disabled = false;
            
            // Format kontrolü (1 Harf, 3 Rakam)
            const regex = /^[A-Z][0-9]{3}$/;
            if(!regex.test(rawValue)) {
                resultCode.classList.add("error");
                resultCode.innerText = "Geçersiz Numara! (Örn: V421)";
                return;
            }

            // Standart Şifre Algoritması Motoru (Mock representation of a radio decode algorithm)
            // Normalde bu fonksiyon sunucuya (backend) veya tam bir lookup-table algoritmasına bağlıdır.
            // Buraya matematiksel hash temsili bir kod eklendi:
            
            const charVal = rawValue.charCodeAt(0);
            const numVal = parseInt(rawValue.substring(1), 10);
            
            // Matematiksel bir sabit dönüşüm
            let decodedNum = ((charVal * numVal) * 11) % 10000;
            
            // Eğer 0 gelirse (nadiren) fallback
            if(decodedNum === 0) decodedNum = 8421;
            
            // 4 haneli string'e çevir
            const finalPaddedCode = String(decodedNum).padStart(4, '0');
            
            // Başarılı sonucu bas
            resultCode.innerText = finalPaddedCode;

        }, 600); // 0.6 Saniyelik bekleme hissiyatı
    });

    // Enter tuşuna basılınca formu gönder
    inputElt.addEventListener("keypress", (e) => {
        if(e.key === "Enter") {
            btnElt.click();
        }
    });

});
