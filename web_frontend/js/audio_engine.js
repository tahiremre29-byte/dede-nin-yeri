/**
 * DDSOUND QUANTUM AI - Audio Engine
 * Dosya dışından (mp3/wav) ses çağırmak yerine düşük gecikmeli (zero-latency) 
 * Web Audio API Oscillators kullanarak fütüristik UI/Bilim kurgu efektleri sentezler.
 */
document.addEventListener("DOMContentLoaded", () => {
    let audioCtx = null;
    
    // Kullanıcı ilk etkileşimde ses motorunu uyandırır (Tarayıcı güvenlik kısıtlamaları sebebiyle)
    const initAudio = () => {
        if (!audioCtx) {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
    };
    document.addEventListener("click", initAudio, { once: true });
    document.addEventListener("keydown", initAudio, { once: true });
    
    // 1. Hover "Blip" Sesi (Çok hafif tiz bir elektronik bipleme)
    const playHoverBlip = () => {
        if (!audioCtx) return;
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        
        osc.type = 'sine';
        osc.frequency.setValueAtTime(800, audioCtx.currentTime); // 800Hz yüksek perde
        osc.frequency.exponentialRampToValueAtTime(300, audioCtx.currentTime + 0.05); // Enerji düşüşü
        
        gain.gain.setValueAtTime(0.015, audioCtx.currentTime); // Çok düşük ses seviyesi
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.05);
        
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        
        osc.start();
        osc.stop(audioCtx.currentTime + 0.06);
    };

    // 2. Click "Swoosh/Beep" Sesi (Tıklandığında gelen onay sesi)
    const playClickConfirm = () => {
        if (!audioCtx) return;
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(1200, audioCtx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(400, audioCtx.currentTime + 0.1);
        
        gain.gain.setValueAtTime(0.04, audioCtx.currentTime); 
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.15);
        
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        
        osc.start();
        osc.stop(audioCtx.currentTime + 0.16);
    };

    // 3. AI Yazma Sesi ("Tak tak tak" klavye hissi için kısa vuruşlar)
    window.UI_Audio = {
        playTypeBlip: () => {
            if (!audioCtx) return;
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            
            osc.type = 'square';
            osc.frequency.setValueAtTime(150 + Math.random() * 50, audioCtx.currentTime);
            
            gain.gain.setValueAtTime(0.01, audioCtx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.03);
            
            osc.connect(gain);
            gain.connect(audioCtx.destination);
            
            osc.start();
            osc.stop(audioCtx.currentTime + 0.04);
        },
        click: playClickConfirm,
        
        // Barış Manço - Dönence (MP3 Player)
        playDonenceSignature: () => {
            const signatureAudio = new Audio("audio/donence.mp3");
            signatureAudio.volume = 0.6;
            
            // Hata çıkarsa (dosya yoksa UI üstünde belli etmesin, log atsın)
            signatureAudio.play().catch(e => {
                console.log("[DD1_Audio] İmza sesi çalınamadı. 'audio/donence.mp3' dosyasını klasöre eklediğinizden emin olun.", e);
            });
        }
    };

    // Bütün butonlara ve belirlenen (.hover-sfx) inputlara efekt ekle
    const hoverElements = document.querySelectorAll('button, .hover-sfx, .ai-badge, .tool-desc');
    hoverElements.forEach(el => {
        el.addEventListener('mouseenter', () => playHoverBlip());
    });
    
    const clickElements = document.querySelectorAll('button');
    clickElements.forEach(el => {
        el.addEventListener('mousedown', () => window.UI_Audio.click());
    });
});
