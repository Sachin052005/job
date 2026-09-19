document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-confirm]").forEach(function (el) {
        el.addEventListener("submit", function (event) {
            const message = el.getAttribute("data-confirm");
            if (!window.confirm(message)) {
                event.preventDefault();
            }
        });
    });

    document.querySelectorAll("[data-toggle-password]").forEach(function (btn) {
        btn.addEventListener("click", function () {
            const targetId = btn.getAttribute("data-toggle-password");
            const input = document.getElementById(targetId);
            if (!input) return;
            const icon = btn.querySelector("i");
            if (input.type === "password") {
                input.type = "text";
                if (icon) icon.className = "bi bi-eye-slash";
            } else {
                input.type = "password";
                if (icon) icon.className = "bi bi-eye";
            }
        });
    });

    document.querySelectorAll(".alert").forEach(function (alertEl) {
        setTimeout(function () {
            const alert = bootstrap.Alert.getOrCreateInstance(alertEl);
            alert.close();
        }, 6000);
    });

    const navbar = document.querySelector(".app-navbar");
    if (navbar) {
        const updateNavbarShadow = function () {
            navbar.classList.toggle("is-scrolled", window.scrollY > 12);
        };
        updateNavbarShadow();
        window.addEventListener("scroll", updateNavbarShadow, { passive: true });
    }

    const revealTargets = document.querySelectorAll(".reveal");
    if (revealTargets.length) {
        if ("IntersectionObserver" in window) {
            const observer = new IntersectionObserver(function (entries, obs) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        entry.target.classList.add("in-view");
                        obs.unobserve(entry.target);
                    }
                });
            }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });
            revealTargets.forEach(function (el) {
                observer.observe(el);
            });
        } else {
            revealTargets.forEach(function (el) {
                el.classList.add("in-view");
            });
        }
    }

    const prefersReducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    document.querySelectorAll("[data-count-to]").forEach(function (el) {
        const target = parseInt(el.getAttribute("data-count-to"), 10) || 0;
        if (prefersReducedMotion) {
            el.textContent = target + "%";
            return;
        }
        const duration = 700;
        const start = performance.now();
        function step(now) {
            const progress = Math.min(1, (now - start) / duration);
            const value = Math.round(target * progress);
            el.textContent = value + "%";
            if (progress < 1) {
                requestAnimationFrame(step);
            }
        }
        requestAnimationFrame(step);
    });
});
