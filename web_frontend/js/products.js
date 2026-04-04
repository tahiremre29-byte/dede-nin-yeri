const dd1Products = [
    {
        id: "prod_sub_30cm",
        name: "DD1 Quantum Subwoofer (30cm)",
        category: "Subwoofer Serisi",
        power: "500W RMS",
        features: ["15mm Xmax", "Neo Mıknatıs", "Çift Bobin"],
        color: "#ff3366",
        icon: "🔊"
    },
    {
        id: "prod_tweeter_neo",
        name: "DD1 Tiz Üstadı (Neo 3)",
        category: "Tweeter & Midrange",
        power: "150W RMS",
        features: ["Hassasiyet 98dB", "Titanyum Dome", "İpeksi Tiz"],
        color: "#00f0ff",
        icon: "🔉"
    },
    {
        id: "prod_cabin_100l",
        name: "DD1 Akustik Kabin (100L)",
        category: "Kabin Çözümleri",
        power: "N/A",
        features: ["18mm MDF", "Slot Port", "Lazer Kesim Kusursuzluk"],
        color: "#8a2be2",
        icon: "📦"
    },
    {
        id: "prod_dsp_amp",
        name: "DD1 DSP Amplifikatör",
        category: "Amplifikatör Serisi",
        power: "4x100W",
        features: ["10 Bant EQ", "Zaman Gecikmesi", "Quantum AI Filtre"],
        color: "#ffcc00",
        icon: "🎛️"
    }
];

document.addEventListener("DOMContentLoaded", () => {
    const carousel = document.getElementById("productCarousel");
    if(!carousel) return;

    // Render products
    dd1Products.forEach(product => {
        const item = document.createElement("div");
        item.classList.add("product-item");
        
        // CSS Variable injection for glow color
        item.style.setProperty("--prod-color", product.color);

        item.innerHTML = `
            <div class="prod-icon" style="text-shadow: 0 0 15px ${product.color}">${product.icon}</div>
            <div class="prod-details">
                <span class="prod-category" style="color:${product.color}">${product.category}</span>
                <h3 class="prod-title">${product.name}</h3>
                <div class="prod-tags">
                    <span>${product.power}</span>
                    <span>${product.features[0]}</span>
                </div>
            </div>
            <button class="btn-ask-ai" data-product="${product.name}" aria-label="${product.name} için AI'a sor">
                <span class="pulsing-brain">🧠</span> İncele
            </button>
        `;
        carousel.appendChild(item);
    });

    // Ask AI Buttons
    document.querySelectorAll(".btn-ask-ai").forEach(btn => {
        btn.addEventListener("click", (e) => {
            const btnTarget = e.currentTarget;
            const productName = btnTarget.getAttribute("data-product");
            
            // Interaction with JS/ai_chat.js
            const chatInput = document.getElementById("chatInput");
            const btnSend = document.getElementById("btnSend");
            
            if(chatInput && btnSend) {
                // Flash the button for visual feedback
                btnTarget.classList.add("btn-flashing");
                setTimeout(() => btnTarget.classList.remove("btn-flashing"), 300);

                // Auto-fill chat and scroll to chat
                chatInput.value = `Bana ${productName} ürününden detaylıca bahseder misin? Hangi sistemlerle uyumludur?`;
                
                // Scroll specifically to the chat window card header visually
                const chatCard = document.querySelector(".chat-card");
                if(chatCard) {
                    chatCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }

                // Simulate human slight delay then click
                setTimeout(() => {
                    btnSend.click();
                }, 600);
            }
        });
    });
});
