/* ============================================================================
   Burgersfort Water Drilling — site interactions
   No icon-font dependency. Progressive enhancement for navigation, pricing,
   the FAQ accordion, project lightbox and locally hosted videos.
   ============================================================================ */

(() => {
  "use strict";
  document.documentElement.classList.add("js");

  const header = document.getElementById("site-header");
  const menuButton = document.getElementById("menu-button");
  const mobileNav = document.getElementById("mobile-nav");
  const navBackdrop = document.getElementById("nav-backdrop");

  // Give the sticky header a subtle scroll state without needing a library.
  const updateHeader = () => header?.classList.toggle("scrolled", window.scrollY > 18);
  updateHeader();
  window.addEventListener("scroll", updateHeader, { passive: true });

  // Accessible mobile navigation: reflect state for assistive technology and
  // return focus to the trigger when a user closes the menu with Escape.
  function setMobileNav(open, returnFocus = false) {
    if (!mobileNav || !menuButton) return;
    mobileNav.classList.toggle("open", open);
    menuButton.classList.toggle("is-open", open);
    navBackdrop?.classList.toggle("open", open);
    document.body.classList.toggle("nav-open", open);
    menuButton.setAttribute("aria-expanded", String(open));
    menuButton.setAttribute("aria-label", open ? "Close navigation" : "Open navigation");
    mobileNav.setAttribute("aria-hidden", String(!open));
    if (open) {
      const firstLink = mobileNav.querySelector("a");
      window.requestAnimationFrame(() => firstLink?.focus());
    } else if (returnFocus) {
      menuButton.focus();
    }
  }

  menuButton?.addEventListener("click", () => {
    setMobileNav(menuButton.getAttribute("aria-expanded") !== "true");
  });
  navBackdrop?.addEventListener("click", () => setMobileNav(false));
  mobileNav?.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => setMobileNav(false));
  });
  window.addEventListener("resize", () => {
    if (window.innerWidth > 980) setMobileNav(false);
  }, { passive: true });

  // Reveal animations are decorative. If IntersectionObserver is unsupported,
  // content remains visible instead of being hidden indefinitely.
  const revealElements = [...document.querySelectorAll(".reveal")];
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    revealElements.forEach((element) => element.classList.add("visible"));
  } else if ("IntersectionObserver" in window) {
    const revealObserver = new IntersectionObserver((entries, observer) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1, rootMargin: "0px 0px -24px 0px" });
    revealElements.forEach((element) => revealObserver.observe(element));
  } else {
    revealElements.forEach((element) => element.classList.add("visible"));
  }

  // ------------------------------------------------------------------------
  // Price calculator. The total, breakdown and WhatsApp enquiry all use the
  // same selected component values. There is no unexplained package override.
  // ------------------------------------------------------------------------
  const cataloguePrices = {
    30: { drilling: 9000, pvc: 4500, pump: 5000 },
    35: { drilling: 10500, pvc: 6000, pump: 8500 },
    40: { drilling: 12000, pvc: 7000, pump: 10000 },
    45: { drilling: 13500, pvc: 8000, pump: 10500 },
    50: { drilling: 15000, pvc: 8500, pump: 11500 },
    55: { drilling: 16500, pvc: 9000, pump: 12000 },
    60: { drilling: 18000, pvc: 10000, pump: 12500 },
    65: { drilling: 19500, pvc: 11000, pump: 13000 },
    70: { drilling: 21000, pvc: 11500, pump: 13500 },
    75: { drilling: 22500, pvc: 12500, pump: 14000 },
    80: { drilling: 24000, pvc: 13000, pump: 14500 },
    85: { drilling: 25000, pvc: 14000, pump: 15000 },
    90: { drilling: 27000, pvc: 15000, pump: 15500 },
    95: { drilling: 28500, pvc: 16000, pump: 16000 },
    100: { drilling: 30000, pvc: 17000, pump: 16500 },
  };
  const formatMoney = (amount) => `R${Number(amount).toLocaleString("en-ZA")}`;
  const depthSelect = document.getElementById("depth-select");
  const includePvc = document.getElementById("include-pvc");
  const includePump = document.getElementById("include-pump");
  const calculatorTotal = document.getElementById("calculator-total");
  const calculatorBreakdown = document.getElementById("calculator-breakdown");
  const calculatorWhatsapp = document.getElementById("calculator-whatsapp");

  function updateCalculator() {
    if (!depthSelect || !calculatorTotal || !calculatorBreakdown || !calculatorWhatsapp) return;
    const metres = Number(depthSelect.value);
    const selection = cataloguePrices[metres];
    if (!selection) return;

    const selectedParts = [{ label: "Drilling", price: selection.drilling }];
    if (includePvc?.checked) selectedParts.push({ label: "PVC casing", price: selection.pvc });
    if (includePump?.checked) selectedParts.push({ label: "Pump", price: selection.pump });

    const estimate = selectedParts.reduce((sum, part) => sum + part.price, 0);
    const breakdown = selectedParts.map((part) => `${part.label} ${formatMoney(part.price)}`).join(" + ");
    calculatorTotal.textContent = formatMoney(estimate);
    calculatorBreakdown.textContent = breakdown;
    calculatorTotal.setAttribute("aria-label", `Estimated component total ${formatMoney(estimate)}`);

    const message = [
      "Hello Burgersfort Water Drilling, I would like a free site survey and quotation.",
      `Estimated depth: ${metres} metres.`,
      `Selected components: ${selectedParts.map((part) => `${part.label} ${formatMoney(part.price)}`).join(", ")}.`,
      `Indicative component total: ${formatMoney(estimate)}.`,
      "Please confirm availability, site conditions and the final quotation."
    ].join(" ");
    calculatorWhatsapp.href = `https://wa.me/27818021758?text=${encodeURIComponent(message)}`;
    calculatorWhatsapp.setAttribute("aria-label", `Request a free site survey and discuss the ${formatMoney(estimate)} estimate on WhatsApp`);
  }

  [depthSelect, includePvc, includePump].forEach((control) => {
    control?.addEventListener("input", updateCalculator);
    control?.addEventListener("change", updateCalculator);
  });
  updateCalculator();

  // ------------------------------------------------------------------------
  // FAQ accordion. Button states and hidden panel states stay in sync.
  // ------------------------------------------------------------------------
  const faqButtons = [...document.querySelectorAll(".faq-item button[aria-controls]")];
  faqButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const item = button.closest(".faq-item");
      const panelId = button.getAttribute("aria-controls");
      const panel = panelId ? document.getElementById(panelId) : null;
      const willOpen = button.getAttribute("aria-expanded") !== "true";

      document.querySelectorAll(".faq-item.open").forEach((openItem) => {
        if (openItem !== item) {
          openItem.classList.remove("open");
          const otherButton = openItem.querySelector("button[aria-controls]");
          const otherPanelId = otherButton?.getAttribute("aria-controls");
          const otherPanel = otherPanelId ? document.getElementById(otherPanelId) : null;
          otherButton?.setAttribute("aria-expanded", "false");
          otherPanel?.setAttribute("aria-hidden", "true");
        }
      });

      item?.classList.toggle("open", willOpen);
      button.setAttribute("aria-expanded", String(willOpen));
      panel?.setAttribute("aria-hidden", String(!willOpen));
    });
  });

  // ------------------------------------------------------------------------
  // Project lightbox: keyboard trap, Escape-to-close, backdrop close, and
  // focus return to the photo button that opened it.
  // ------------------------------------------------------------------------
  const lightbox = document.getElementById("lightbox");
  const lightboxImage = lightbox?.querySelector("img");
  const lightboxCloseButton = lightbox?.querySelector(".lightbox-close");
  let lightboxTrigger = null;

  function openLightbox(trigger) {
    if (!lightbox || !lightboxImage) return;
    const sourceImage = trigger.querySelector("img");
    const source = trigger.getAttribute("data-lightbox");
    if (!source) return;

    lightboxTrigger = trigger;
    lightboxImage.src = source;
    lightboxImage.alt = sourceImage?.alt || "Expanded project photograph";
    lightbox.classList.add("open");
    lightbox.setAttribute("aria-hidden", "false");
    document.body.classList.add("lightbox-open");
    window.requestAnimationFrame(() => lightboxCloseButton?.focus());
  }

  function closeLightbox() {
    if (!lightbox || !lightbox.classList.contains("open")) return;
    lightbox.classList.remove("open");
    lightbox.setAttribute("aria-hidden", "true");
    document.body.classList.remove("lightbox-open");
    lightboxImage?.removeAttribute("src");
    const focusTarget = lightboxTrigger;
    lightboxTrigger = null;
    if (focusTarget?.isConnected) focusTarget.focus();
  }

  document.querySelectorAll("[data-lightbox]").forEach((button) => {
    button.addEventListener("click", () => openLightbox(button));
  });
  lightboxCloseButton?.addEventListener("click", closeLightbox);
  lightbox?.addEventListener("click", (event) => {
    if (event.target === lightbox) closeLightbox();
  });
  lightbox?.addEventListener("keydown", (event) => {
    if (event.key !== "Tab") return;
    const focusable = [...lightbox.querySelectorAll('button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])')]
      .filter((element) => element.getAttribute("aria-hidden") !== "true" && element.getClientRects().length > 0);
    if (!focusable.length) {
      event.preventDefault();
      lightbox.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      if (lightbox?.classList.contains("open")) closeLightbox();
      if (mobileNav?.classList.contains("open")) setMobileNav(false, true);
    }
  });

  // Avoid competing audio/video tracks when visitors play a local work clip.
  const workVideos = [...document.querySelectorAll(".work-video-card video")];
  workVideos.forEach((video) => {
    video.addEventListener("play", () => {
      workVideos.forEach((otherVideo) => {
        if (otherVideo !== video) otherVideo.pause();
      });
    });
  });
})();
