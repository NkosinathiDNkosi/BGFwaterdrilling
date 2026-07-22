/* Admin interactions. This file is loaded at the end of admin/base.html. */
// Mobile sidebar: open from the menu; close from the overlay or any nav link.
const sidebar = document.getElementById("sidebar");
const menu = document.getElementById("menuBtn");
const overlay = document.getElementById("overlay");
const closeMenu = () => {
  sidebar?.classList.remove("open");
  overlay?.classList.remove("show");
};
menu?.addEventListener("click", () => {
  sidebar?.classList.toggle("open");
  overlay?.classList.toggle("show");
});
overlay?.addEventListener("click", closeMenu);
document
  .querySelectorAll(".sidebar nav a")
  .forEach((link) => link.addEventListener("click", closeMenu));
// Remove temporary status messages after 4.5 seconds.
setTimeout(
  () => document.querySelectorAll(".flash").forEach((item) => item.remove()),
  4500,
);
