// DD1 3D & 2D Görselleştirme Modülü
// Gereksinim: Three.js ve OrbitControls

window.DD1Visualizer = {
    render3D: function(containerId, design) {
        const container = document.getElementById(containerId);
        if (!container) return;
        
        container.innerHTML = ""; 
        
        const w = design?.dimensions?.w_mm || 500;
        const h = design?.dimensions?.h_mm || 350;
        const d = design?.dimensions?.d_mm || 400;
        const type = design?.enclosure_type || "ported";
        
        const width = w / 10;
        const height = h / 10;
        const depth = d / 10;
        
        const scene = new THREE.Scene();
        
        const camera = new THREE.PerspectiveCamera(45, container.clientWidth / container.clientHeight, 0.1, 1000);
        
        // Auto-framing based on max dimension
        const maxDim = Math.max(width, height, depth);
        camera.position.set(maxDim * 1.2, maxDim * 1.0, maxDim * 2.0);
        
        const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true });
        renderer.setSize(container.clientWidth, container.clientHeight);
        renderer.setPixelRatio(window.devicePixelRatio);
        container.appendChild(renderer.domElement);
        
        const controls = new THREE.OrbitControls(camera, renderer.domElement);
        controls.enableDamping = true;
        controls.dampingFactor = 0.05;
        controls.autoRotate = true;
        controls.autoRotateSpeed = 1.5;
        controls.target.set(0, 0, 0);
        
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
        scene.add(ambientLight);
        
        const directionalLight = new THREE.DirectionalLight(0x00f0ff, 1);
        directionalLight.position.set(100, 200, 50);
        scene.add(directionalLight);
        
        const pointLight = new THREE.PointLight(0x9900ff, 1, 500);
        pointLight.position.set(-50, -50, -50);
        scene.add(pointLight);

        // Group to hold everything
        const boxGroup = new THREE.Group();
        scene.add(boxGroup);

        const geometry = new THREE.BoxGeometry(width, height, depth);
        
        const material = new THREE.MeshPhysicalMaterial({
            color: 0x00aaff,
            metalness: 0.1,
            roughness: 0.2,
            transmission: 0.8,
            thickness: 0.5,
            transparent: true,
            opacity: 0.8
        });
        
        const cube = new THREE.Mesh(geometry, material);
        boxGroup.add(cube);
        
        const edges = new THREE.EdgesGeometry(geometry);
        const lineMaterial = new THREE.LineBasicMaterial({ color: 0x00f0ff, linewidth: 2 });
        const wireframe = new THREE.LineSegments(edges, lineMaterial);
        cube.add(wireframe);
        
        // Speaker Cone (Front Face)
        const speakerRadius = Math.min(width, height) * 0.35;
        const speakerGeo = new THREE.CylinderGeometry(speakerRadius, speakerRadius * 0.8, 2, 32);
        speakerGeo.rotateX(Math.PI / 2); // Point towards front (Z axis)
        
        const speakerMat = new THREE.MeshStandardMaterial({
            color: 0x222222,
            metalness: 0.5,
            roughness: 0.8
        });
        
        const speaker = new THREE.Mesh(speakerGeo, speakerMat);
        // Position on the front face (Z = depth/2), slight offset so it protrudes
        speaker.position.set(0, 0, (depth / 2) + 1);
        
        // Speaker surround/edge
        const surroundGeo = new THREE.TorusGeometry(speakerRadius, speakerRadius * 0.1, 16, 64);
        const surroundMat = new THREE.MeshStandardMaterial({ color: 0x111111, roughness: 0.9 });
        const surround = new THREE.Mesh(surroundGeo, surroundMat);
        surround.position.set(0, 0, (depth / 2) + 1);
        
        boxGroup.add(speaker);
        boxGroup.add(surround);
        
        // Port Slot (If type is ported/L-Port)
        if (type !== "kutu_kapali" && type !== "sealed") {
            let gapWidth = width * 0.1;
            let gapHeight = height - 3.6; // 36mm = 3.6cm internal reduction
            
            if (design && design.port && design.port.gap_mm) {
                gapWidth = design.port.gap_mm / 10; // Convert mm to cm
            }
            
            const portGeo = new THREE.BoxGeometry(gapWidth, gapHeight, depth * 0.8);
            const portMat = new THREE.MeshStandardMaterial({
                color: 0x050505, // Dark inside
                metalness: 0.1,
                roughness: 0.9
            });
            const port = new THREE.Mesh(portGeo, portMat);
            
            // Position on the right side vertically
            const portX = (width / 2) - 1.8 - (gapWidth / 2); // 1.8cm = 18mm thickness
            port.position.set(portX, 0, (depth / 2) - (depth * 0.4) + 1);
            
            // Front edge wireframe for the port
            const portEdges = new THREE.EdgesGeometry(new THREE.BoxGeometry(gapWidth, gapHeight, 2));
            const portWire = new THREE.LineSegments(portEdges, new THREE.LineBasicMaterial({ color: 0x9900ff, linewidth: 2 }));
            portWire.position.set(portX, 0, (depth / 2));
            
            boxGroup.add(port);
            boxGroup.add(portWire);
            
            // Adjust speaker slightly left to make room for the right-side port
            speaker.position.x -= (gapWidth / 2);
            surround.position.x -= (gapWidth / 2);
        }

        window.addEventListener('resize', () => {
            if(!container) return;
            camera.aspect = container.clientWidth / container.clientHeight;
            camera.updateProjectionMatrix();
            renderer.setSize(container.clientWidth, container.clientHeight);
        });

        const animate = function () {
            requestAnimationFrame(animate);
            controls.update();
            renderer.render(scene, camera);
        };
        animate();
    },

    render2D: function(containerId, design) {
        const container = document.getElementById(containerId);
        if (!container) return;
        
        container.innerHTML = `<canvas style="width:100%; height:100%;"></canvas>`;
        const canvas = container.querySelector("canvas");
        const ctx = canvas.getContext("2d");
        
        const w = design?.dimensions?.w_mm || 500;
        const h = design?.dimensions?.h_mm || 350;
        const d = design?.dimensions?.d_mm || 400;
        const thickness = 18; 
        
        const draw = () => {
            canvas.width = container.clientWidth;
            canvas.height = container.clientHeight;
            const cW = canvas.width;
            const cH = canvas.height;
            
            ctx.clearRect(0, 0, cW, cH);
            
            // Layout dimension logic
            const layoutW = (w * 2) + 60;
            const layoutH = h + (d - 36) + (h - 36) + 120;
            
            const scaleX = (cW * 0.9) / layoutW;
            const scaleY = (cH * 0.9) / layoutH;
            const scale = Math.min(scaleX, scaleY);
            
            const offsetX = (cW - (layoutW * scale)) / 2;
            const offsetY = (cH - (layoutH * scale)) / 2;
            
            ctx.lineWidth = 1;
            ctx.strokeStyle = "#00f0ff";
            ctx.fillStyle = "rgba(0, 240, 255, 0.1)";
            ctx.font = "10px Courier New";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            
            const drawPanel = (x, y, pw, ph, label) => {
                const sw = pw * scale;
                const sh = ph * scale;
                ctx.fillRect(x, y, sw, sh);
                ctx.strokeRect(x, y, sw, sh);
                ctx.fillStyle = "#fff";
                ctx.fillText(`${label}`, x + sw/2, y + Math.max(sh/2 - 6, 10));
                ctx.fillStyle = "#00ff66";
                ctx.fillText(`(${pw}x${ph})`, x + sw/2, y + Math.max(sh/2 + 6, 22));
                ctx.fillStyle = "rgba(0, 240, 255, 0.1)";
            };
            
            // Ön & Arka
            drawPanel(offsetX, offsetY, w, h, "Ön/Arka");
            
            // Subwoofer cutout sembolik (İlk ön panele)
            ctx.beginPath();
            ctx.setLineDash([5, 5]);
            ctx.arc(offsetX + (w*scale)/2, offsetY + (h*scale)/2, Math.min(w, h)*scale*0.35, 0, 2*Math.PI);
            ctx.stroke();
            ctx.setLineDash([]);
            
            drawPanel(offsetX + (w*scale) + 20*scale, offsetY, w, h, "Ön/Arka");
            
            // Alt & Üst
            const altUstD = d - (thickness*2);
            let currentY = offsetY + (h*scale) + 20*scale;
            drawPanel(offsetX, currentY, w, altUstD, "Üst/Alt");
            drawPanel(offsetX + (w*scale) + 20*scale, currentY, w, altUstD, "Üst/Alt");
            
            // Yanlar
            const yanH = h - (thickness*2);
            currentY += (altUstD*scale) + 20*scale;
            drawPanel(offsetX, currentY, altUstD, yanH, "Yan");
            drawPanel(offsetX + (altUstD*scale) + 20*scale, currentY, altUstD, yanH, "Yan");
            
            // İç Port Panelleri (L-Port parçaları)
            if (design?.port?.type !== "sealed" && design?.panel_list) {
                const portPanels = design.panel_list.filter(p => p.name.includes("Port") && p.name !== "Bağlantı Portu");
                let portOffsetX = offsetX + (altUstD*2*scale) + 40*scale;
                
                portPanels.forEach((pPanel, i) => {
                    const label = portPanels.length > 1 ? `Port (P${i+1})` : "L-Port";
                    drawPanel(portOffsetX, currentY, pPanel.w, yanH, label);
                    portOffsetX += (pPanel.w * scale) + 20*scale;
                });
            }
        };
        
        draw();
        window.addEventListener('resize', draw);
    }
};
