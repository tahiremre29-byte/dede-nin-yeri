document.addEventListener("DOMContentLoaded", () => {
    
    const chatInput = document.getElementById("chatInput");
    const btnSend = document.getElementById("btnSend");
    const chatWindow = document.getElementById("chatWindow");

    // Helper: Scroll to bottom
    const scrollToBottom = () => {
        chatWindow.scrollTop = chatWindow.scrollHeight;
    };

    // Helper: Add message to UI
    const addMessage = (text, isUser = false) => {
        const msgDiv = document.createElement("div");
        msgDiv.classList.add("message");
        msgDiv.classList.add(isUser ? "user-message" : "ai-message");

        const spanMsg = document.createElement("span");
        spanMsg.classList.add("msg-text");
        spanMsg.textContent = text;
        
        msgDiv.appendChild(spanMsg);
        chatWindow.appendChild(msgDiv);
        scrollToBottom();
    };

    // Helper: Add Typing Indicator
    const addTypingIndicator = () => {
        const msgDiv = document.createElement("div");
        msgDiv.classList.add("message", "ai-message", "typing-indicator");
        msgDiv.id = "typingIndicator";
        
        for(let i=0; i<3; i++) {
            const dot = document.createElement("div");
            dot.classList.add("dot");
            msgDiv.appendChild(dot);
        }
        
        chatWindow.appendChild(msgDiv);
        scrollToBottom();
    };

    const removeTypingIndicator = () => {
        const ind = document.getElementById("typingIndicator");
        if(ind) ind.remove();
    };

    let chatHistory = [];
    let chatContext = {};

    const handleSend = () => {
        const text = chatInput.value.trim();
        if(!text) return;

        // User message
        addMessage(text, true);
        chatInput.value = "";
        
        chatHistory.push({ role: "user", content: text });

        // AI Typing...
        addTypingIndicator();

        // Simulate AI Response with Real DD1 Platform API
        const BASE_URL = window.ENV ? window.ENV.API_BASE_URL : "";
        fetch(`${BASE_URL}/chat/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: text,
                session_id: localStorage.getItem('dd1_session_id') || "",
                context: chatContext,
                history: chatHistory
            })
        })
        .then(res => res.json())
        .then(data => {
            removeTypingIndicator();
            
            // DD1 backend'inden gelen 'reply' veya doğrudan mesaja dönüş
            const responseText = data.reply || data.user_visible_response || "Anlaşılamadı.";
            addMessage(responseText, false);
            chatHistory.push({ role: "model", content: responseText });
            
            // Context güncelle - Tüm çıkarılmış verileri (kökteki ve paneldeki) sakla
            if (data.extracted_info) {
                chatContext = { ...chatContext, ...data.extracted_info, ...(data.extracted_info.normalized_panel || {}) };
            }

            // Gelen usta kartları (Tezgahtar sonucu) varsa UI'a bas
            if(data.ui_cards && data.ui_cards.length > 0) {
                renderCards(data.ui_cards);
            }
            
            if(window.UI_Audio) window.UI_Audio.click(); // Gelen mesaj sesi
        })
        .catch(err => {
            removeTypingIndicator();
            console.error("DD1 API HTTP Hatası:", err);
            addMessage("Bağlantı Hatası: API'ye ulaşılamıyor (Ağ veya CORS hatası olabilir). Lütfen sayfanın güncel olduğundan emin olun.", false);
        });
    };

    const renderCards = (cards) => {
        const cardsContainer = document.createElement("div");
        cardsContainer.classList.add("ai-cards-container");
        cardsContainer.style.display = "flex";
        cardsContainer.style.gap = "10px";
        cardsContainer.style.overflowX = "auto";
        cardsContainer.style.padding = "10px 0";
        cardsContainer.style.marginTop = "5px";

        cards.forEach(card => {
            const cardEl = document.createElement("div");
            cardEl.style.background = "rgba(0, 240, 255, 0.05)";
            cardEl.style.border = "1px solid rgba(0, 240, 255, 0.2)";
            cardEl.style.borderRadius = "8px";
            cardEl.style.padding = "10px";
            cardEl.style.minWidth = "200px";
            cardEl.style.color = "#fff";
            cardEl.style.fontSize = "0.85rem";
            
            const title = document.createElement("strong");
            title.textContent = card.model;
            title.style.color = "var(--cyan-glow)";
            title.style.display = "block";
            title.style.marginBottom = "5px";
            
            const rms = document.createElement("div");
            rms.textContent = `Güç: ${card.rms_w || '?'}W RMS`;
            
            const selectBtn = document.createElement("button");
            selectBtn.textContent = "Bunu Seç";
            selectBtn.style.marginTop = "8px";
            selectBtn.style.background = "rgba(0, 240, 255, 0.1)";
            selectBtn.style.border = "1px solid var(--cyan-glow)";
            selectBtn.style.color = "var(--cyan-glow)";
            selectBtn.style.padding = "4px 8px";
            selectBtn.style.borderRadius = "4px";
            selectBtn.style.cursor = "pointer";
            selectBtn.style.width = "100%";
            
            selectBtn.addEventListener("click", () => {
                chatInput.value = `${card.brand || ''} ${card.model} modelini seçiyorum.`;
                handleSend();
            });

            cardEl.appendChild(title);
            cardEl.appendChild(rms);
            if(card.fs_hz) {
                const fs_hz = document.createElement("div");
                fs_hz.textContent = `Fs: ${card.fs_hz} Hz`;
                cardEl.appendChild(fs_hz);
            }
            cardEl.appendChild(selectBtn);
            cardsContainer.appendChild(cardEl);
        });

        chatWindow.appendChild(cardsContainer);
        scrollToBottom();
    };

    btnSend.addEventListener("click", handleSend);
    chatInput.addEventListener("keypress", (e) => {
        if(e.key === "Enter") {
            handleSend();
        }
    });

});
