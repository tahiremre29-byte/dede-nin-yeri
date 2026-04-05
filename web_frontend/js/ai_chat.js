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
        
        msgDiv.appendChild(spanMsg);
        chatWindow.appendChild(msgDiv);
        scrollToBottom();

        if (isUser) {
            spanMsg.textContent = text;
        } else {
            let i = 0;
            function typeWriter() {
                if (i < text.length) {
                    spanMsg.textContent += text.charAt(i);
                    i++;
                    scrollToBottom();
                    setTimeout(typeWriter, 15);
                }
            }
            typeWriter();
        }
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
            
            // EĞER AKUSTİK TASARIM YAPILDIYSA SAĞ PANELE GÖRSEL VE SOHBETE BUTON BAS
            if (data.action === "design" && data.design) {
                renderDesignResult(data.design);
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

    const renderDesignResult = (design) => {
        // 1. Sohbet Penceresine Üretim Butonu Ekle
        const msgDiv = document.createElement("div");
        msgDiv.classList.add("message", "ai-message");
        msgDiv.style.background = "rgba(153, 0, 255, 0.1)";
        msgDiv.style.border = "1px solid var(--purple-glow)";
        msgDiv.style.maxWidth = "90%";
        msgDiv.innerHTML = `
            <div style="font-weight: bold; color: var(--neon-cyan); margin-bottom: 5px;">🔧 Tasarım Mühürlendi!</div>
            <div style="font-size: 0.85rem; margin-bottom: 10px;">Hacim: ${design.net_volume_l}L, Frekans: ${design.tuning_hz}Hz</div>
            <button id="btnProduceDxf_${design.design_id}" style="width: 100%; padding: 8px; background: var(--purple-glow); border: none; border-radius: 4px; color: #fff; font-weight: bold; cursor: pointer;">Laser/CNC Üretim Dosyasını Çıkar (DXF)</button>
            <div id="dxfLinkZone_${design.design_id}" style="margin-top: 10px;"></div>
        `;
        chatWindow.appendChild(msgDiv);
        scrollToBottom();

        // 2. Sağdaki Görselizasyon Paneline Tasarım Bilgilerini Bas ve 3D Modeli Çağır
        const visualZone = document.getElementById("dynamicContentZone");
        const placeholder = document.getElementById("workspacePlaceholder");
        if (placeholder) placeholder.style.display = "none";
        
        if (visualZone) {
            // Ölçüler (mm)
            const w = design.dimensions?.w_mm || 0;
            const h = design.dimensions?.h_mm || 0;
            const d = design.dimensions?.d_mm || 0;

            visualZone.innerHTML = `
                <div style="background: rgba(0,0,0,0.85); border: 1px solid var(--cyan-glow); padding: 20px; border-radius: 12px; margin: auto; width: 95%; max-width: 800px; text-align: left; box-sizing: border-box; box-shadow: 0 0 15px rgba(0, 240, 255, 0.2);">
                    <h3 style="color: var(--cyan-glow); margin-top: 0; text-align: center; text-transform: uppercase; letter-spacing: 2px;">Aktif Akustik Model</h3>
                    <div style="display: flex; flex-wrap: wrap; justify-content: space-between; border-bottom: 1px solid #444; padding-bottom: 10px; margin-bottom: 15px;">
                        <div style="flex: 1; min-width: 250px; padding-right: 15px;">
                            <p style="margin: 5px 0;"><strong>Tasarım ID:</strong> <span style="font-family: monospace; color:#ccc;">${design.design_id}</span>
                            <button id="btnPlayDonence_${design.design_id}" style="background: none; border: 1px solid var(--neon-purple); color: var(--neon-purple); border-radius: 4px; padding: 2px 8px; cursor: pointer; font-size: 0.8em; margin-left: 10px;">🎵 İmza (Dönence)</button></p>
                            <p style="margin: 5px 0;"><strong>Net Hacim:</strong> <span style="color: #fff;">${design.net_volume_l} Litre</span></p>
                            <p style="margin: 5px 0;"><strong>Tuning/Frekans:</strong> <span style="color: #fff;">${design.tuning_hz} Hz</span></p>
                            <p style="margin: 5px 0; color: #aaa; font-size: 0.85em; background: rgba(255,255,255,0.05); padding: 8px; border-radius: 4px; border-left: 3px solid var(--neon-purple);">Özet: ${design.advice || '-'}</p>
                        </div>
                        <div style="text-align: right; min-width: 150px; background: rgba(0,255,102,0.1); padding: 10px; border-radius: 8px; border: 1px solid rgba(0,255,102,0.3);">
                            <p style="margin: 0 0 5px 0; color: #00ff66; border-bottom: 1px solid rgba(0,255,102,0.2); padding-bottom: 5px;"><strong>Dış Ölçüler (mm)</strong></p>
                            <p style="margin: 5px 0; font-family: monospace; font-size: 1.1em;">Gen (W): <b style="color:#fff;">${w}</b></p>
                            <p style="margin: 5px 0; font-family: monospace; font-size: 1.1em;">Yük (H): <b style="color:#fff;">${h}</b></p>
                            <p style="margin: 5px 0; font-family: monospace; font-size: 1.1em;">Derin (D): <b style="color:#fff;">${d}</b></p>
                        </div>
                    </div>
                    
                    <div style="display: flex; gap: 15px; margin-top: 20px;">
                        <!-- 2D Üstten Kesim Planı -->
                        <div style="flex: 1; border: 1px dashed var(--cyan-glow); border-radius: 8px; position: relative;">
                            <div style="position: absolute; top: -10px; left: 10px; background: #000; padding: 0 5px; color: var(--cyan-glow); font-size: 12px; font-weight: bold;">2D Kesim Plakası</div>
                            <div id="cabinet2D" style="width: 100%; height: 250px;"></div>
                        </div>

                        <!-- 3D Kabin Simulasyonu -->
                        <div style="flex: 1.5; border: 1px dashed #9900ff; border-radius: 8px; position: relative; background: radial-gradient(circle, rgba(153,0,255,0.1) 0%, rgba(0,0,0,0) 70%);">
                            <div style="position: absolute; top: -10px; left: 10px; background: #000; padding: 0 5px; color: #9900ff; font-size: 12px; font-weight: bold;">3D Kutu Simülatörü</div>
                            <div id="cabinet3D" style="width: 100%; height: 250px; cursor: move;"></div>
                        </div>
                    </div>
                </div>
            `;

            // Çizimleri renderla (DOM yüklendikten hemen sonra)
            setTimeout(() => {
                if (window.DD1Visualizer && design) {
                    window.DD1Visualizer.render3D("cabinet3D", design);
                    window.DD1Visualizer.render2D("cabinet2D", design);
                    
                    // Dijital İmza (Barış Manço - Dönence) Oynat
                    if (window.UI_Audio && window.UI_Audio.playDonenceSignature) {
                        try {
                            window.UI_Audio.playDonenceSignature();
                        } catch(e) {
                            console.log("Audio play blocked by browser interaction policy.");
                        }
                    }
                }
                
                // Müzik çalma butonu event listener
                const btnPlay = document.getElementById(`btnPlayDonence_${design.design_id}`);
                if (btnPlay && window.UI_Audio && window.UI_Audio.playDonenceSignature) {
                    btnPlay.addEventListener("click", () => {
                        window.UI_Audio.playDonenceSignature();
                    });
                }
            }, 100);
        }

        // 3. Üretim Butonu Click Event
        const btnProduce = document.getElementById(`btnProduceDxf_${design.design_id}`);
        btnProduce.addEventListener("click", () => {
            btnProduce.innerText = "Hazırlanıyor...";
            btnProduce.disabled = true;

            const BASE_URL = window.ENV ? window.ENV.API_BASE_URL : "";
            fetch(`${BASE_URL}/api/design/produce`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ design_id: design.design_id })
            })
            .then(res => res.json())
            .then(data => {
                if (data.download_url) {
                    btnProduce.innerText = "Başarılı!";
                    btnProduce.style.background = "#00ff66";
                    btnProduce.style.color = "#000";
                    const linkZone = document.getElementById(`dxfLinkZone_${design.design_id}`);
                    linkZone.innerHTML = `<a href="${BASE_URL}${data.download_url}" target="_blank" style="display: block; text-align: center; background: #00ff66; color: #000; font-weight: bold; padding: 10px; border-radius: 4px; text-decoration: none;">DXF İndir</a>`;
                } else {
                    throw new Error(data.detail || "URL gelmedi");
                }
            })
            .catch(err => {
                alert(`Üretim Hatası: ${err.message}`);
                btnProduce.innerText = "Hata! Tekrar Dene";
                btnProduce.disabled = false;
            });
        });
    };

});
