// =====================================================
// CivicConnect AI — Homepage Interactions
// =====================================================

// ---------- MOBILE MENU ----------

const menuToggle = document.querySelector(".menu-toggle");
const nav = document.querySelector(".navbar nav");

if (menuToggle && nav) {
    menuToggle.addEventListener("click", () => {
        const isOpen = nav.classList.toggle("mobile-open");
        menuToggle.setAttribute("aria-expanded", isOpen);
    });
}

// ---------- HOW IT WORKS SCROLL BUTTON ----------

const howItWorksButton = document.querySelector(".secondary-btn");

if (howItWorksButton) {
    howItWorksButton.addEventListener("click", () => {
        document.getElementById("how-it-works")?.scrollIntoView({ behavior: "smooth" });
    });
}

// ---------- LOGIN BUTTON ----------
// (kept as JS-triggered navigation only if login-btn has no href;
//  the template already uses {% url 'login' %} as a real link, so
//  this is a no-op safeguard for any button-based instances)

const loginButtons = document.querySelectorAll(".login-btn");

loginButtons.forEach(btn => {
    if (btn.tagName === "BUTTON") {
        btn.addEventListener("click", () => {
            window.location.href = "/login/";
        });
    }
});

// ---------- CIVIC CONTRIBUTOR BUTTON ----------

const contributorBtn = document.querySelector(".contributor-btn");

if (contributorBtn) {
    contributorBtn.addEventListener("click", () => {
        alert("Civic Contributor registration will be connected by the backend team.");
    });
}

// ---------- IMPACT STATISTICS COUNTER ----------

const statNumbers = document.querySelectorAll(".stat-number");

/**
 * Formats a number for display given its target value and suffix.
 * Handles thousands (e.g. 10000 -> "10K+") generically instead of
 * hardcoding specific numbers.
 */
function formatStatValue(value, suffix) {
    if (value >= 1000) {
        return Math.floor(value / 1000) + "K" + (suffix.includes("+") ? "+" : "");
    }
    return Math.floor(value) + suffix;
}

function startCounters() {
    statNumbers.forEach(stat => {
        const target = Number(stat.dataset.target);
        const suffix = stat.dataset.suffix || "";
        const duration = 1800;
        const stepTime = 20;
        const increment = target / (duration / stepTime);
        let current = 0;

        function updateCounter() {
            current += increment;

            if (current >= target) {
                stat.textContent = formatStatValue(target, suffix);
                return;
            }

            stat.textContent = formatStatValue(current, suffix);
            requestAnimationFrame(updateCounter);
        }

        updateCounter();
    });
}

// ---------- START COUNTER WHEN IMPACT SECTION APPEARS ----------

const impactSection = document.querySelector(".impact-section");

if (impactSection && statNumbers.length) {
    const observer = new IntersectionObserver(
        entries => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    startCounters();
                    observer.unobserve(impactSection);
                }
            });
        },
        { threshold: 0.3 }
    );

    observer.observe(impactSection);
}

// ---------- SCROLL REVEAL ----------
// Fades/slides cards into view as the user scrolls past them.
// Respects prefers-reduced-motion via the CSS side (see .reveal rules).

const revealEls = document.querySelectorAll(".reveal");

if (revealEls.length) {
    const revealObserver = new IntersectionObserver(
        entries => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add("is-visible");
                    revealObserver.unobserve(entry.target);
                }
            });
        },
        { threshold: 0.15, rootMargin: "0px 0px -40px 0px" }
    );

    revealEls.forEach(el => revealObserver.observe(el));
}