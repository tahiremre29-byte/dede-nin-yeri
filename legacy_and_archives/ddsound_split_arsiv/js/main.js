const left = document.querySelector('.left');
const right = document.querySelector('.right');
const container = document.querySelector('.container');

// Sound (Left) Hover Events
left.addEventListener('mouseenter', () => {
    container.classList.add('hover-left');
});
left.addEventListener('mouseleave', () => {
    container.classList.remove('hover-left');
});

// Garage (Right) Hover Events
right.addEventListener('mouseenter', () => {
    container.classList.add('hover-right');
});
right.addEventListener('mouseleave', () => {
    container.classList.remove('hover-right');
});

// For Touch Devices (Mobile)
left.addEventListener('touchstart', () => {
    container.classList.remove('hover-right');
    container.classList.add('hover-left');
});

right.addEventListener('touchstart', () => {
    container.classList.remove('hover-left');
    container.classList.add('hover-right');
});
