/**
 * Particle Animation System
 * Creates a futuristic animated background with
 * floating particles, connections, and subtle movement.
 */

(function () {
    const canvas = document.getElementById('particleCanvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let particles = [];
    let animationId;
    let mouse = { x: null, y: null, radius: 150 };

    const CONFIG = {
        particleCount: 80,
        particleSize: { min: 1, max: 3 },
        speed: { min: 0.15, max: 0.5 },
        connectionDistance: 140,
        colors: [
            'rgba(0, 212, 255, 0.6)',
            'rgba(0, 102, 255, 0.5)',
            'rgba(139, 92, 246, 0.4)',
            'rgba(0, 212, 255, 0.3)',
        ],
        lineColor: 'rgba(0, 212, 255, 0.07)',
    };

    function resize() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }

    class Particle {
        constructor() {
            this.x = Math.random() * canvas.width;
            this.y = Math.random() * canvas.height;
            this.size = CONFIG.particleSize.min + Math.random() * (CONFIG.particleSize.max - CONFIG.particleSize.min);
            this.speedX = (Math.random() - 0.5) * (CONFIG.speed.max - CONFIG.speed.min) + (Math.random() > 0.5 ? CONFIG.speed.min : -CONFIG.speed.min);
            this.speedY = (Math.random() - 0.5) * (CONFIG.speed.max - CONFIG.speed.min) + (Math.random() > 0.5 ? CONFIG.speed.min : -CONFIG.speed.min);
            this.color = CONFIG.colors[Math.floor(Math.random() * CONFIG.colors.length)];
            this.opacity = 0.3 + Math.random() * 0.5;
            this.pulse = Math.random() * Math.PI * 2;
        }

        update() {
            this.x += this.speedX;
            this.y += this.speedY;
            this.pulse += 0.02;

            // Wrap around edges
            if (this.x < -10) this.x = canvas.width + 10;
            if (this.x > canvas.width + 10) this.x = -10;
            if (this.y < -10) this.y = canvas.height + 10;
            if (this.y > canvas.height + 10) this.y = -10;

            // Mouse interaction
            if (mouse.x !== null) {
                const dx = this.x - mouse.x;
                const dy = this.y - mouse.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < mouse.radius) {
                    const force = (mouse.radius - dist) / mouse.radius;
                    this.x += dx * force * 0.02;
                    this.y += dy * force * 0.02;
                }
            }
        }

        draw() {
            const sizeOsc = this.size + Math.sin(this.pulse) * 0.5;
            ctx.beginPath();
            ctx.arc(this.x, this.y, Math.max(0.5, sizeOsc), 0, Math.PI * 2);
            ctx.fillStyle = this.color;
            ctx.globalAlpha = this.opacity + Math.sin(this.pulse) * 0.15;
            ctx.fill();
            ctx.globalAlpha = 1;
        }
    }

    function init() {
        particles = [];
        const count = Math.min(CONFIG.particleCount, Math.floor((canvas.width * canvas.height) / 15000));
        for (let i = 0; i < count; i++) {
            particles.push(new Particle());
        }
    }

    function drawConnections() {
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < CONFIG.connectionDistance) {
                    const opacity = (1 - dist / CONFIG.connectionDistance) * 0.12;
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.strokeStyle = `rgba(0, 212, 255, ${opacity})`;
                    ctx.lineWidth = 0.5;
                    ctx.stroke();
                }
            }
        }
    }

    function animate() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        particles.forEach(p => {
            p.update();
            p.draw();
        });

        drawConnections();
        animationId = requestAnimationFrame(animate);
    }

    // Event Listeners
    window.addEventListener('resize', () => {
        resize();
        init();
    });

    window.addEventListener('mousemove', (e) => {
        mouse.x = e.clientX;
        mouse.y = e.clientY;
    });

    window.addEventListener('mouseout', () => {
        mouse.x = null;
        mouse.y = null;
    });

    // Start
    resize();
    init();
    animate();
})();
