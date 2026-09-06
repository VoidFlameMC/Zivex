/* =========================================================
   ZIVEX — MAIN FRONTEND SCRIPT
   static/script.js
   ========================================================= */

"use strict";

document.addEventListener("DOMContentLoaded", () => {

    /* =====================================================
       HELPERS
    ===================================================== */

    const $ = (selector, parent = document) =>
        parent.querySelector(selector);

    const $$ = (selector, parent = document) =>
        Array.from(parent.querySelectorAll(selector));


    /* =====================================================
       ZIVEX HOME — NAVBAR
       ===================================================== */

    const homeNavbar = $(".z-navbar");

    const updateHomeNavbar = () => {
        if (!homeNavbar) return;

        homeNavbar.classList.toggle(
            "scrolled",
            window.scrollY > 20
        );
    };

    updateHomeNavbar();

    window.addEventListener(
        "scroll",
        updateHomeNavbar,
        { passive: true }
    );


    /* =====================================================
       ZIVEX HOME — SMOOTH SCROLL
       ===================================================== */

    $$('.zivex-home a[href^="#"]').forEach((link) => {

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

            try {
                history.pushState(
                    null,
                    "",
                    targetId
                );
            } catch {
                // Ignore history errors.
            }

        });

    });


    /* =====================================================
       REVEAL ANIMATIONS
       ===================================================== */

    const revealElements = $$(
        [
            ".zivex-home .z-feature",
            ".zivex-home .z-security-content",
            ".zivex-home .z-security-card",
            ".zivex-home .z-cta",
            ".zivex-home .z-preview-wrapper"
        ].join(",")
    );

    const reducedMotion = window.matchMedia(
        "(prefers-reduced-motion: reduce)"
    ).matches;


    if (reducedMotion) {

        revealElements.forEach((element) => {
            element.classList.add("visible");
        });

    } else if ("IntersectionObserver" in window) {

        const revealObserver =
            new IntersectionObserver(
                (entries, observer) => {

                    entries.forEach((entry) => {

                        if (!entry.isIntersecting) {
                            return;
                        }

                        entry.target.classList.add(
                            "visible"
                        );

                        observer.unobserve(
                            entry.target
                        );

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
       DASHBOARD PREVIEW
       ===================================================== */

    const preview = $(".z-preview");

    if (preview && !reducedMotion) {

        preview.addEventListener(
            "mousemove",
            (event) => {

                const rect =
                    preview.getBoundingClientRect();

                const x =
                    event.clientX - rect.left;

                const y =
                    event.clientY - rect.top;

                const rotateY =
                    ((x / rect.width) - 0.5) * 4;

                const rotateX =
                    ((y / rect.height) - 0.5) * -3;

                preview.style.transform =
                    `perspective(1200px)
                     rotateX(${rotateX}deg)
                     rotateY(${rotateY}deg)
                     translateY(-4px)`;

            }
        );


        preview.addEventListener(
            "mouseleave",
            () => {

                preview.style.transform =
                    "perspective(1200px) rotateY(-3deg)";

            }
        );

    }


    /* =====================================================
       BUTTON LOADING
       ===================================================== */

    $$(
        "button[data-loading], a[data-loading]"
    ).forEach((element) => {

        element.addEventListener(
            "click",
            () => {

                if (
                    element.dataset.loading ===
                    "false"
                ) {
                    return;
                }

                element.classList.add("loading");

                element.setAttribute(
                    "aria-busy",
                    "true"
                );

            }
        );

    });


    /* =====================================================
       EXTERNAL LINKS
       ===================================================== */

    $$(
        'a[href^="http://"], a[href^="https://"]'
    ).forEach((link) => {

        try {

            const url =
                new URL(link.href);

            if (
                url.origin !==
                window.location.origin
            ) {

                link.setAttribute(
                    "rel",
                    "noopener noreferrer"
                );

            }

        } catch {
            // Ignore malformed URLs.
        }

    });


    /* =====================================================
       PREVENT DOUBLE SUBMIT
       ===================================================== */

    $$("form").forEach((form) => {

        form.addEventListener(
            "submit",
            () => {

                const submitButtons =
                    $$(
                        'button[type="submit"], input[type="submit"]',
                        form
                    );


                submitButtons.forEach(
                    (button) => {

                        button.disabled = true;

                        button.setAttribute(
                            "aria-busy",
                            "true"
                        );

                    }
                );

            }
        );

    });


    /* =====================================================
       DYNAMIC YEAR
       ===================================================== */

    const yearElements =
        $$("[data-current-year]");

    const currentYear =
        new Date().getFullYear();

    yearElements.forEach((element) => {

        element.textContent =
            currentYear;

    });


    /* =====================================================
       BACK TO TOP
       ===================================================== */

    const backToTop =
        $("[data-back-to-top]");

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
            { passive: true }
        );


        backToTop.addEventListener(
            "click",
            () => {

                window.scrollTo({
                    top: 0,
                    behavior:
                        reducedMotion
                            ? "auto"
                            : "smooth"
                });

            }
        );

    }


    /* =====================================================
       DASHBOARD — MOBILE SIDEBAR
       ===================================================== */

    const dashboardSidebar =
        $(".dashboard-sidebar");

    const dashboardToggle =
        $(".dashboard-menu-toggle");

    const dashboardOverlay =
        $("#dashboard-overlay");


    const closeDashboardSidebar = () => {

        if (dashboardSidebar) {
            dashboardSidebar.classList.remove(
                "open"
            );
        }

        if (dashboardOverlay) {
            dashboardOverlay.classList.remove(
                "active"
            );
        }

        document.body.classList.remove(
            "dashboard-menu-open"
        );

    };


    const openDashboardSidebar = () => {

        if (dashboardSidebar) {
            dashboardSidebar.classList.add(
                "open"
            );
        }

        if (dashboardOverlay) {
            dashboardOverlay.classList.add(
                "active"
            );
        }

        document.body.classList.add(
            "dashboard-menu-open"
        );

    };


    if (
        dashboardSidebar &&
        dashboardToggle
    ) {

        dashboardToggle.addEventListener(
            "click",
            () => {

                const isOpen =
                    dashboardSidebar.classList.contains(
                        "open"
                    );

                if (isOpen) {
                    closeDashboardSidebar();
                } else {
                    openDashboardSidebar();
                }

            }
        );

    }


    if (dashboardOverlay) {

        dashboardOverlay.addEventListener(
            "click",
            closeDashboardSidebar
        );

    }


    /* =====================================================
       DASHBOARD — CLOSE AFTER NAVIGATION
       ===================================================== */

    $$(".dashboard-sidebar a").forEach(
        (link) => {

            link.addEventListener(
                "click",
                () => {

                    if (
                        window.innerWidth <= 900
                    ) {
                        closeDashboardSidebar();
                    }

                }
            );

        }
    );


    /* =====================================================
       DASHBOARD — ESC KEY
       ===================================================== */

    document.addEventListener(
        "keydown",
        (event) => {

            if (event.key === "Escape") {

                closeDashboardSidebar();

            }

        }
    );


    /* =====================================================
       DASHBOARD — RESPONSIVE RESET
       ===================================================== */

    window.addEventListener(
        "resize",
        () => {

            if (window.innerWidth > 900) {

                closeDashboardSidebar();

            }

        }
    );


    /* =====================================================
       COPY BUTTONS
       ===================================================== */

    $$("[data-copy]").forEach((button) => {

        button.addEventListener(
            "click",
            async () => {

                const value =
                    button.dataset.copy;

                if (
                    !value ||
                    !navigator.clipboard
                ) {
                    return;
                }

                const originalText =
                    button.textContent;

                try {

                    await navigator.clipboard.writeText(
                        value
                    );

                    button.textContent =
                        "تم النسخ";

                    window.setTimeout(
                        () => {

                            button.textContent =
                                originalText;

                        },
                        1600
                    );

                } catch {

                    button.textContent =
                        "فشل النسخ";

                    window.setTimeout(
                        () => {

                            button.textContent =
                                originalText;

                        },
                        1600
                    );

                }

            }
        );

    });


    /* =====================================================
       PAGE LOADED
       ===================================================== */

    requestAnimationFrame(() => {

        document.documentElement.classList.add(
            "js-ready"
        );

        document.body.classList.add(
            "page-loaded"
        );

    });


    /* =====================================================
       CONSOLE BRANDING
       ===================================================== */

    if (window.console) {

        console.log(
            "%cZivex",
            "font-size:24px;font-weight:800;"
        );

        console.log(
            "Zivex Frontend initialized."
        );

    }

});
