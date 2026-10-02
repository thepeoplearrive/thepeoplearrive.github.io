// Footer year, and a visible focus ring around the Substack signup embed.
// Focus inside a cross-origin iframe cannot be styled from this page, so mark the
// frame itself while it holds keyboard focus.
document.querySelectorAll('[data-year]').forEach(function (el) { el.textContent = new Date().getFullYear(); });
var frames = Array.prototype.slice.call(document.querySelectorAll('iframe.signup'));
if (frames.length) {
  window.addEventListener('blur', function () {
    setTimeout(function () {
      frames.forEach(function (f) { f.classList.toggle('has-focus', document.activeElement === f); });
    }, 0);
  });
  window.addEventListener('focus', function () {
    frames.forEach(function (f) { f.classList.remove('has-focus'); });
  });
}
