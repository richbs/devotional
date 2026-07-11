// ─── Data ────────────────────────────────────────────────────────────────────
// window.slides / window.timeouts are set by PHP in index.php <head>

const slides   = window.slides   || [];
const timeouts = window.timeouts || [];


// ─── DOM refs ────────────────────────────────────────────────────────────────

const pagesEl    = document.getElementById("pages");
const progressEl = document.querySelector(".progress");
const jumpsEl    = document.querySelector(".jumps");
const dot        = document.querySelector(".progress-dot");   // styles.css: view-transition-name: dot
const counter    = document.getElementById("page-current");


// ─── Build slides ────────────────────────────────────────────────────────────
// Creates .leaf imgs inside #pages. CSS hides all but .leaf.active.
// Only the active leaf gets view-transition-name:page (styles.css) so VT
// captures exactly one element per transition.

slides.forEach((src, i) => {
    const img = document.createElement("img");
    img.className = "leaf" + (i === 0 ? " active" : "");
    img.src = src;
    img.alt = "";
    if (!document.startViewTransition) {
      img.classList.add("fader");
    }
    pagesEl.appendChild(img);
});


// ─── Build progress bar ──────────────────────────────────────────────────────
// Inserts one .nav-page button per slide, before .progress-dot so the dot
// (absolutely positioned) floats above the buttons in z-order.

slides.forEach((_, i) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "nav-page" + (i === 0 ? " active" : "");
    btn.setAttribute("aria-label", `Page ${i + 1}`);
    progressEl.insertBefore(btn, dot);
});


// ─── Build jump buttons ──────────────────────────────────────────────────────
// 5 circular buttons inside .jumps, each jumping 20% through the slide list.
// data-target is the slide index; updateJumps() keeps .active in sync.

const JUMP_COUNT = 5;
for (let j = 0; j < JUMP_COUNT; j++) {
    const target = Math.floor((j * slides.length) / JUMP_COUNT);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "jump" + (j === 0 ? " active" : "");
    btn.dataset.target = String(target);
    btn.setAttribute("aria-label", `Jump to page ${target + 1}`);
    jumpsEl.appendChild(btn);
}

document.getElementById("page-total").textContent = slides.length;


// ─── Live queries (after DOM is built) ───────────────────────────────────────

const leaves   = document.querySelectorAll("#pages .leaf");
const navPages = document.querySelectorAll(".nav-page");
const jumps    = document.querySelectorAll(".jump");
let current = 0;


// ─── Navigation ──────────────────────────────────────────────────────────────

function updateDot(index) {
    dot.style.left = `${((index + 0.5) / leaves.length) * 100}%`;  // animated by styles.css transition
    counter.textContent = index + 1;
}

function updateJumps(index) {
    let activeJump = -1;
    jumps.forEach((btn, i) => {
        if (Number(btn.dataset.target) <= index) activeJump = i;
    });
    jumps.forEach((btn, i) => btn.classList.toggle("active", i === activeJump));
}

// Central navigation function. Drives View Transitions with typed animations:
// 'forward' / 'backward' → slide keyframes in styles.css
// 'fade'                 → VT default cross-fade (no extra keyframes needed)
function go(index) {
    if (index === current || index < 0 || index >= leaves.length) return;

    const direction = index > current ? "forward" : "backward";
    const prev = current;
    current = index;

    navPages[prev].classList.remove("active");
    navPages[index].classList.add("active");
    updateJumps(index);
    updateDot(index);

    const update = () => {
        leaves[prev].classList.remove("active");
        leaves[index].classList.add("active");
    };

    if (!document.startViewTransition) { update(); return; }

    const isFade = pagesEl.classList.contains("fade");
    document.startViewTransition({ update, types: isFade ? ["fade"] : [direction] });
}

navPages.forEach((btn, i) => btn.addEventListener("click", () => go(i)));
jumps.forEach((btn) => btn.addEventListener("click", () => go(Number(btn.dataset.target))));

document.getElementById("nav-home").addEventListener("click", () => go(0));
document.getElementById("nav-prev").addEventListener("click", () => go(current - 1));
document.getElementById("nav-next").addEventListener("click", () => go(current + 1));

document.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight") go(current + 1);
    if (e.key === "ArrowLeft")  go(current - 1);
});

pagesEl.addEventListener("click", (e) => {
    const rect = pagesEl.getBoundingClientRect();
    go(e.clientX - rect.left > rect.width / 2 ? current + 1 : current - 1);
});

updateDot(0);


// ─── Idle timeout overlay ────────────────────────────────────────────────────
// Full-viewport overlay styled in styles.css (.timeout / .timeout__image).
// Two stacked <img> layers crossfade via inline opacity; CSS transition handles
// the animation (transition: opacity 0.8s ease on .timeout__image).
// Appended to <body> (not inside <main>) so it sits above everything.

const IDLE_TIMEOUT_MS = 120000;  // ms before overlay appears; 0 = disabled
const SLIDE_DURATION  = 8000;    // ms each timeout image is shown
const FADE_DURATION   = 500;     // ms — must be <= CSS transition duration

const overlay = document.createElement("div");
overlay.className = "timeout";
overlay.hidden = true;

const layerA = document.createElement("img");
const layerB = document.createElement("img");
layerA.className = "timeout__image";
layerB.className = "timeout__image";
layerA.alt = layerB.alt = "";
overlay.append(layerA, layerB);
document.body.appendChild(overlay);

let cycleTimer    = null;
let aActive       = true;
let nextIndex     = 0;
let idleTimer     = null;
let overlayActive = false;

function startCycle() {
    if (timeouts.length < 2) return;
    cycleTimer = setInterval(() => {
        const showing = aActive ? layerA : layerB;
        const hiding  = aActive ? layerB : layerA;
        showing.style.opacity = 0;
        hiding.style.opacity  = 1;
        aActive = !aActive;
        // Preload next image into the now-hidden layer once it has faded out
        setTimeout(() => {
            showing.src = timeouts[nextIndex];
            nextIndex = (nextIndex + 1) % timeouts.length;
        }, FADE_DURATION + 50);
    }, SLIDE_DURATION);
}

function showOverlay() {
    if (overlayActive || !timeouts.length) return;
    overlayActive = true;
    aActive   = true;
    nextIndex = 2 % timeouts.length;
    layerA.src = timeouts[0];
    layerA.style.opacity = 1;
    layerB.src = timeouts[1 % timeouts.length];
    layerB.style.opacity = 0;
    overlay.hidden = false;
    startCycle();
}

function hideOverlay() {
    if (!overlayActive) return;
    overlayActive = false;
    overlay.hidden = true;
    clearInterval(cycleTimer);
    cycleTimer = null;
    go(0);
    resetIdleTimer();
}

function resetIdleTimer() {
    if (!IDLE_TIMEOUT_MS) return;
    clearTimeout(idleTimer);
    idleTimer = setTimeout(showOverlay, IDLE_TIMEOUT_MS);
}

["mousedown", "touchstart", "keydown"].forEach((evt) => {
    window.addEventListener(evt, () => {
        if (overlayActive) hideOverlay();
        else resetIdleTimer();
    }, { passive: true });
});

// Show overlay immediately on load; any interaction dismisses it
showOverlay();
