/* --------------------------------------------------------------------------
   Burgersfort Water Drilling — interactions
   Includes navigation, reveal animation, calculator, gallery and water burst.
---------------------------------------------------------------------------- */

// Sticky navigation styling.
const header = document.getElementById("site-header");
window.addEventListener("scroll", () => {
  header?.classList.toggle("scrolled", window.scrollY > 24);
});

// Mobile navigation — accessible, animated and touch friendly.
const menuButton = document.getElementById("menu-button");
const mobileNav = document.getElementById("mobile-nav");
const navBackdrop = document.getElementById("nav-backdrop");

function setMobileNav(open) {
  mobileNav?.classList.toggle("open", open);
  menuButton?.classList.toggle("is-open", open);
  navBackdrop?.classList.toggle("open", open);
  document.body.classList.toggle("nav-open", open);
  menuButton?.setAttribute("aria-expanded", String(open));
  menuButton?.setAttribute(
    "aria-label",
    open ? "Close navigation" : "Open navigation",
  );
  mobileNav?.setAttribute("aria-hidden", String(!open));
}

menuButton?.addEventListener("click", () =>
  setMobileNav(!mobileNav?.classList.contains("open")),
);
navBackdrop?.addEventListener("click", () => setMobileNav(false));
mobileNav
  ?.querySelectorAll("a")
  .forEach((link) => link.addEventListener("click", () => setMobileNav(false)));
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") setMobileNav(false);
});
window.addEventListener(
  "resize",
  () => {
    if (innerWidth > 980) setMobileNav(false);
  },
  { passive: true },
);

// Reveal elements only once when they enter the viewport.
const revealObserver = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("visible");
        revealObserver.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.12 },
);
document
  .querySelectorAll(".reveal")
  .forEach((element) => revealObserver.observe(element));

// EDIT HERE: PRICE CATALOGUE
// Change the numbers below or add a depth; keep the property names unchanged.
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
const formatMoney = (value) => `R${value.toLocaleString("en-ZA")}`;
const depth = document.getElementById("depth-select");
const includePvc = document.getElementById("include-pvc");
const includePump = document.getElementById("include-pump");
const total = document.getElementById("calculator-total");
const breakdown = document.getElementById("calculator-breakdown");
const quoteLink = document.getElementById("calculator-whatsapp");

function updateCalculator() {
  if (!depth) return;
  const metres = Number(depth.value);
  const item = cataloguePrices[metres];
  if (!item || !total || !breakdown || !quoteLink) return;
  let sum = item.drilling;
  const parts = [`Drilling ${formatMoney(item.drilling)}`];

  if (includePvc?.checked) {
    sum += item.pvc;
    parts.push(`PVC ${formatMoney(item.pvc)}`);
  }
  if (includePump?.checked) {
    sum += item.pump;
    parts.push(`Pump ${formatMoney(item.pump)}`);
  }

  const special = metres === 30 && includePvc?.checked && includePump?.checked;
  total.textContent = special ? "R24 500 special" : formatMoney(sum);
  breakdown.textContent = special
    ? "Current advertised 30 m package."
    : parts.join(" + ");
  // EDIT HERE: WHATSAPP QUOTE
  // Change this message or replace 27818021758 with the business number.
  const text = `Hello Burgersfort Water Drilling, I would like a free survey and quotation for a ${metres} metre package including ${parts.join(", ")}.`;
  quoteLink.href = `https://wa.me/27818021758?text=${encodeURIComponent(text)}`;
}
[depth, includePvc, includePump].forEach((control) => {
  control?.addEventListener("input", updateCalculator, { passive: true });
  control?.addEventListener("change", updateCalculator, { passive: true });
});
// Paint the correct estimate before the next frame and keep it synchronous thereafter.
updateCalculator();
requestAnimationFrame(updateCalculator);

// FAQ accordion keeps only one answer open at a time.
document.querySelectorAll(".faq-item button").forEach((button) => {
  button.addEventListener("click", () => {
    const item = button.closest(".faq-item");
    document.querySelectorAll(".faq-item.open").forEach((openItem) => {
      if (openItem !== item) openItem.classList.remove("open");
    });
    item.classList.toggle("open");
  });
});

// Project lightbox.
const lightbox = document.getElementById("lightbox");
const lightboxImage = lightbox?.querySelector("img");
document.querySelectorAll("[data-lightbox]").forEach((button) => {
  button.addEventListener("click", () => {
    lightboxImage.src = button.dataset.lightbox;
    lightbox.classList.add("open");
  });
});
function closeLightbox() {
  lightbox?.classList.remove("open");
}
lightbox
  ?.querySelector(".lightbox-close")
  ?.addEventListener("click", closeLightbox);
lightbox?.addEventListener("click", (event) => {
  if (event.target === lightbox) closeLightbox();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeLightbox();
});

// Small magnetic movement on the main hero button.
document.querySelectorAll(".magnetic").forEach((button) => {
  button.addEventListener("mousemove", (event) => {
    const rect = button.getBoundingClientRect();
    const x = (event.clientX - rect.left - rect.width / 2) * 0.12;
    const y = (event.clientY - rect.top - rect.height / 2) * 0.12;
    button.style.transform = `translate(${x}px, ${y}px)`;
  });
  button.addEventListener("mouseleave", () => {
    button.style.transform = "";
  });
});

// Recent Work slideshows — reels and project images rotate independently.
document.querySelectorAll("[data-slideshow]").forEach((slideshow) => {
  const slides = [...slideshow.querySelectorAll("[data-slide]")];
  const previousButton = slideshow.querySelector("[data-slide-prev]");
  const nextButton = slideshow.querySelector("[data-slide-next]");
  const dotsContainer = slideshow.querySelector("[data-slide-dots]");
  const delay = Number(slideshow.dataset.delay) || 6000;
  let activeIndex = Math.max(
    0,
    slides.findIndex((slide) => slide.classList.contains("is-active")),
  );
  let timer;

  if (slides.length < 2) return;

  const dots = slides.map((_, index) => {
    const dot = document.createElement("button");
    dot.type = "button";
    dot.setAttribute("aria-label", `Show item ${index + 1}`);
    dot.addEventListener("click", () => {
      showSlide(index);
      restart();
    });
    dotsContainer?.appendChild(dot);
    return dot;
  });

  function showSlide(index) {
    activeIndex = (index + slides.length) % slides.length;
    slides.forEach((slide, slideIndex) => {
      const isActive = slideIndex === activeIndex;
      slide.classList.toggle("is-active", isActive);
      slide.setAttribute("aria-hidden", String(!isActive));
    });
    dots.forEach((dot, dotIndex) => {
      const isActive = dotIndex === activeIndex;
      dot.classList.toggle("is-active", isActive);
      dot.setAttribute("aria-current", isActive ? "true" : "false");
    });
  }

  function stop() {
    clearInterval(timer);
  }

  function start() {
    stop();
    if (!document.hidden) {
      timer = setInterval(() => showSlide(activeIndex + 1), delay);
    }
  }

  function restart() {
    stop();
    start();
  }

  previousButton?.addEventListener("click", () => {
    showSlide(activeIndex - 1);
    restart();
  });
  nextButton?.addEventListener("click", () => {
    showSlide(activeIndex + 1);
    restart();
  });
  slideshow.addEventListener("mouseenter", stop);
  slideshow.addEventListener("mouseleave", start);
  slideshow.addEventListener("focusin", stop);
  slideshow.addEventListener("focusout", start);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) stop();
    else start();
  });

  showSlide(activeIndex);
  start();
});

// Lightweight, mobile-first screen splash. The photograph stays completely static.
const splash = document.getElementById("screen-splash");
const splashHero = document.getElementById("home");

if (
  splash &&
  splashHero &&
  !matchMedia("(prefers-reduced-motion: reduce)").matches
) {
  let splashTimer;
  let heroVisible = true;

  const playSplash = () => {
    if (!heroVisible || document.hidden) return;
    splash.classList.remove("is-playing");
    // Restart CSS animations without running a permanent render loop.
    void splash.offsetWidth;
    splash.classList.add("is-playing");
  };

  const scheduleSplash = (delay = 4800) => {
    clearTimeout(splashTimer);
    splashTimer = setTimeout(() => {
      playSplash();
      scheduleSplash(innerWidth <= 700 ? 7200 : 6200);
    }, delay);
  };

  const observer = new IntersectionObserver(
    (entries) => {
      heroVisible = entries[0]?.isIntersecting ?? true;
      if (heroVisible) scheduleSplash(900);
      else clearTimeout(splashTimer);
    },
    { threshold: 0.15 },
  );

  observer.observe(splashHero);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) clearTimeout(splashTimer);
    else if (heroVisible) scheduleSplash(700);
  });
}
