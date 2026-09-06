/* =========================================================
   Zivex — Main Frontend Script
   static/script.js
   ========================================================= */
"use strict";
document.addEventListener("DOMContentLoaded", () => {
    /* =====================================================
       Helpers
       ===================================================== */
    const $ = (selector, parent = document) =>
        parent.querySelector(selector);
    const $$ = (selector, parent = document) =>
        Array.from(parent.querySelectorAll(selector));
    /* =====================================================
       Mobile Navigation
       ===================================================== */
    const navbar = $(".navbar");
    const navToggle = $(".nav-toggle");
    const navMenu = $(".nav-links");
    if (navToggle && navMenu) {
        navToggle.setAttribute("aria-expanded", "false");
        navToggle.addEventListener("click", () => {
            const isOpen = navMenu.classList.toggle("active");
            navToggle.classList.toggle("active", isOpen);
            navToggle.setAttribute("aria-expanded", String(isOpen));
            document.body.classList.toggle("nav-open", isOpen);
        });
        $$(".nav-links a").forEach((link) => {
            link.addEventListener("click", () => {
                navMenu.classList.remove("active");
                navToggle.classList.remove("active");
                navToggle.setAttribute("aria-expanded", "false");
                document.body.classList.remove("nav-open");
            });
        });
        document.addEventListener("click", (event) => {
            if (
                navMenu.classList.contains("active") &&
                navbar &&
                !navbar.contains(event.target)
            ) {
                navMenu.classList.remove("active");
                navToggle.classList.remove("active");
                navToggle.setAttribute("aria-expanded", "false");
                document.body.classList.remove("nav-open");
            }
        });
    }
    /* =====================================================
       Smooth Scrolling
       ===================================================== */
    $$('a[href^="#"]').forEach((link) => {
        link.addEventListener("click", (event) => {
            const targetId = link.getAttribute("href");
            if (!targetId || targetId === "#") {
                return;
            }
            const target = $(targetId);
            if (!target) {
                return;
            }
            event.preventDefault();
            target.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });
            if (history.pushState) {
                history.pushState(null, "", targetId);
            }
        });
    });
    /* =====================================================
       Navbar Scroll Effect
       ===================================================== */
    const updateNavbar = () => {
        if (!navbar) {
            return;
        }
        navbar.classList.toggle("scrolled", window.scrollY > 20);
    };
    updateNavbar();
    window.addEventListener(
        "scroll",
        updateNavbar,
        {
            passive: true
        }
    );
    /* =====================================================
       Reveal Animations
       ===================================================== */
    const revealElements = $$(
        ".reveal, .feature-card, .security-card, .section-title, .hero-content, .hero-visual"
    );
    const reducedMotion = window.matchMedia(
        "(prefers-reduced-motion: reduce)"
    ).matches;
    if (reducedMotion) {
        revealElements.forEach((element) => {
            element.classList.add("visible");
        });
    } else if ("IntersectionObserver" in window) {
        const revealObserver = new IntersectionObserver(
            (entries, observer) => {
                entries.forEach((entry) => {
                    if (!entry.isIntersecting) {
                        return;
                    }
                    entry.target.classList.add("visible");
                    observer.unobserve(entry.target);
                });
            },
            {
                threshold: 0.12,
                rootMargin: "0px 0px -40px 0px"
            }
        );
        revealElements.forEach((element) => {
            element.classList.add("reveal");
            revealObserver.observe(element);
        });
    } else {
        revealElements.forEach((element) => {
            element.classList.add("visible");
        });
    }
    /* =====================================================
       Feature Cards — Keyboard Accessibility
       ===================================================== */
    $$(".feature-card, .security-card").forEach((card) => {
        card.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                const link = $("a", card);
                if (link) {
                    event.preventDefault();
                    link.click();
                }
            }
        });
    });
    /* =====================================================
       Dashboard Preview — Interactive Tabs
       ===================================================== */
    const previewTabs = $$("[data-dashboard-tab]");
    const previewPanels = $$("[data-dashboard-panel]");
    if (previewTabs.length && previewPanels.length) {
        const activateDashboardTab = (tabName) => {
            previewTabs.forEach((tab) => {
                const active =
                    tab.dataset.dashboardTab === tabName;
                tab.classList.toggle("active", active);
                tab.setAttribute("aria-selected", String(active));
            });
            previewPanels.forEach((panel) => {
                const active =
                    panel.dataset.dashboardPanel === tabName;
                panel.classList.toggle("active", active);
                panel.hidden = !active;
            });
        };
        previewTabs.forEach((tab) => {
            tab.addEventListener("click", () => {
                const tabName = tab.dataset.dashboardTab;
                if (tabName) {
                    activateDashboardTab(tabName);
                }
            });
        });
        const defaultTab =
            previewTabs.find((tab) =>
                tab.classList.contains("active")
            )?.dataset.dashboardTab ||
            previewTabs[0]?.dataset.dashboardTab;
        if (defaultTab) {
            activateDashboardTab(defaultTab);
        }
    }
    /* =====================================================
       Copy Buttons
       ===================================================== */
    $$("[data-copy]").forEach((button) => {
        button.addEventListener("click", async () => {
            const value = button.dataset.copy;
            if (!value || !navigator.clipboard) {
                return;
            }
            const originalText = button.textContent;
            try {
                await navigator.clipboard.writeText(value);
                button.textContent = "Copied";
                window.setTimeout(() => {
                    button.textContent = originalText;
                }, 1600);
            } catch {
                button.textContent = "Failed";
                window.setTimeout(() => {
                    button.textContent = originalText;
                }, 1600);
            }
        });
    });
    /* =====================================================
       Dynamic Year
       ===================================================== */
    const yearElements = $$("[data-current-year]");
    const currentYear = new Date().getFullYear();
    yearElements.forEach((element) => {
        element.textContent = currentYear;
    });
    /* =====================================================
       Back To Top
       ===================================================== */
    const backToTop = $("[data-back-to-top]");
    if (backToTop) {
        const updateBackToTop = () => {
            backToTop.classList.toggle(
                "visible",
                window.scrollY > 500
            );
        };
        updateBackToTop();
        window.addEventListener(
            "scroll",
            updateBackToTop,
            {
                passive: true
            }
        );
        backToTop.addEventListener("click", () => {
            window.scrollTo({
                top: 0,
                behavior: reducedMotion ? "auto" : "smooth"
            });
        });
    }
    /* =====================================================
       Button Loading State
       ===================================================== */
    $$("button[data-loading], a[data-loading]").forEach(
        (element) => {
            element.addEventListener("click", () => {
                if (element.dataset.loading === "false") {
                    return;
                }
                element.classList.add("loading");
                element.setAttribute("aria-busy", "true");
            });
        }
    );
    /* =====================================================
       External Links
       ===================================================== */
    $$('a[href^="http://"], a[href^="https://"]').forEach(
        (link) => {
            try {
                const url = new URL(link.href);
                if (url.origin !== window.location.origin) {
                    link.setAttribute(
                        "rel",
                        "noopener noreferrer"
                    );
                }
            } catch {
                // Ignore malformed URLs.
            }
        }
    );
    /* =====================================================
       Prevent Double Submit
       ===================================================== */
    $$("form").forEach((form) => {
        form.addEventListener("submit", () => {
            const submitButtons = $$(
                'button[type="submit"], input[type="submit"]',
                form
            );
            submitButtons.forEach((button) => {
                button.disabled = true;
                button.setAttribute("aria-busy", "true");
            });
        });
    });
    /* =====================================================
       Page Loaded State
       ===================================================== */
    requestAnimationFrame(() => {
        document.documentElement.classList.add("js-ready");
        document.body.classList.add("page-loaded");
    });
    /* =====================================================
       Console Branding
       ===================================================== */
    if (window.console) {
        console.log(
            "%cZivex",
            "font-size: 24px; font-weight: 800;"
        );
        console.log(
            "Zivex Dashboard — Frontend initialized."
        );
    }
});
