/**
 * DD1 Sonic Runner - Core Game Engine
 */

const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');
const scoreEl = document.getElementById('score');
const overlay = document.getElementById('overlay');

// Game State
let gameState = 'START'; // START, PLAYING, GAMEOVER
let score = 0;
let distance = 0;
let speed = 5;

// Constants
const GRAVITY = 0.8;
const JUMP_FORCE = -16;
const GROUND_Y = 0.85; // % of height

// Colors
const COLORS = {
    player: '#4285F4',
    obstacle: '#FF5A91',
    grid: '#915AFF22',
    gridMain: '#915AFF44'
};

class Player {
    constructor() {
        this.reset();
    }
    
    reset() {
        this.width = 40;
        this.height = 60;
        this.x = 100;
        this.y = 0;
        this.dy = 0;
        this.isGrounded = false;
        this.trail = [];
    }
    
    update() {
        // Gravity
        const groundHeight = canvas.height * GROUND_Y;
        
        if (this.y + this.height < groundHeight) {
            this.dy += GRAVITY;
            this.isGrounded = false;
        } else {
            this.y = groundHeight - this.height;
            this.dy = 0;
            this.isGrounded = true;
        }
        
        this.y += this.dy;
        
        // Trail effect
        this.trail.unshift({x: this.x, y: this.y});
        if (this.trail.length > 10) this.trail.pop();
    }
    
    draw() {
        // Draw Trail
        this.trail.forEach((t, i) => {
            ctx.globalAlpha = (10 - i) / 20;
            ctx.fillStyle = COLORS.player;
            ctx.fillRect(t.x, t.y, this.width, this.height);
        });
        
        ctx.globalAlpha = 1;
        
        // Draw Player Body (Glow)
        ctx.shadowBlur = 15;
        ctx.shadowColor = COLORS.player;
        ctx.fillStyle = COLORS.player;
        ctx.fillRect(this.x, this.y, this.width, this.height);
        
        // Face
        ctx.shadowBlur = 0;
        ctx.fillStyle = 'white';
        ctx.fillRect(this.x + this.width - 15, this.y + 15, 8, 8);
    }
    
    jump() {
        if (this.isGrounded) {
            this.dy = JUMP_FORCE;
            this.isGrounded = false;
        }
    }
}

class Obstacle {
    constructor(x) {
        this.width = 30 + Math.random() * 40;
        this.height = 40 + Math.random() * 80;
        this.x = x;
        this.y = canvas.height * GROUND_Y - this.height;
    }
    
    update() {
        this.x -= speed;
    }
    
    draw() {
        ctx.shadowBlur = 10;
        ctx.shadowColor = COLORS.obstacle;
        ctx.fillStyle = COLORS.obstacle;
        ctx.fillRect(this.x, this.y, this.width, this.height);
        ctx.shadowBlur = 0;
    }
}

const player = new Player();
let obstacles = [];
let nextObstacleTime = 0;

function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
}

window.addEventListener('resize', resize);
resize();

// Input
function handleInput() {
    if (gameState === 'PLAYING') {
        player.jump();
    } else {
        startGame();
    }
}

window.addEventListener('keydown', (e) => {
    if (e.code === 'Space') handleInput();
});
canvas.addEventListener('mousedown', handleInput);

function startGame() {
    gameState = 'PLAYING';
    score = 0;
    speed = 7;
    obstacles = [];
    player.reset();
    overlay.classList.add('hidden');
}

function gameOver() {
    gameState = 'GAMEOVER';
    overlay.classList.remove('hidden');
    document.getElementById('status-text').innerText = 'GAME OVER';
}

function drawSynthwaveGrid() {
    const time = Date.now() * 0.002;
    const gridY = canvas.height * GROUND_Y;
    
    ctx.strokeStyle = COLORS.grid;
    ctx.lineWidth = 1;
    
    // Horizontal lines
    for (let i = 0; i < 20; i++) {
        const y = gridY + (i * 40) - (time * speed % 40);
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width, y);
        ctx.stroke();
    }
    
    // Perspective Vertical lines
    ctx.strokeStyle = COLORS.gridMain;
    const centerX = canvas.width / 2;
    for (let i = -10; i <= 10; i++) {
        ctx.beginPath();
        ctx.moveTo(centerX + (i * 200), gridY);
        ctx.lineTo(centerX + (i * 1000), canvas.height);
        ctx.stroke();
    }
}

function update(time) {
    if (gameState === 'PLAYING') {
        player.update();
        
        // Spawn
        if (time > nextObstacleTime) {
            obstacles.push(new Obstacle(canvas.width + 100));
            nextObstacleTime = time + 1500 + Math.random() * 1500;
        }
        
        // Update Obstacles
        obstacles = obstacles.filter(obs => {
            obs.update();
            
            // Collision
            if (
                player.x < obs.x + obs.width &&
                player.x + player.width > obs.x &&
                player.y < obs.y + obs.height &&
                player.y + player.height > obs.y
            ) {
                gameOver();
            }
            
            return obs.x + obs.width > 0;
        });
        
        score++;
        scoreEl.innerText = score.toString().padStart(5, '0');
        speed += 0.001; // Increase difficulty
    }
    
    render();
    requestAnimationFrame(update);
}

function render() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Background Sun
    const sunGlow = ctx.createRadialGradient(canvas.width/2, 200, 0, canvas.width/2, 200, 150);
    sunGlow.addColorStop(0, '#FF5A91');
    sunGlow.addColorStop(1, 'transparent');
    ctx.fillStyle = sunGlow;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    drawSynthwaveGrid();
    
    obstacles.forEach(obs => obs.draw());
    player.draw();
}

// Initial State
document.getElementById('status-text').innerText = 'SONIC RUNNER';
overlay.classList.remove('hidden');

requestAnimationFrame(update);
