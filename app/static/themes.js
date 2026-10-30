'use strict';
// Only palette preference is stored here; never searches or notebook text.
(() => {
  const palettes = ['amber', 'red', 'green', 'contrast'];
  function apply(name, persist) {
    if (!palettes.includes(name)) name = 'amber';
    document.documentElement.dataset.theme = name;
    for (const palette of palettes) {
      document.getElementById('theme-' + palette).setAttribute('aria-pressed', String(palette === name));
    }
    if (persist) {
      try { localStorage.setItem('gravestone-palette', name); } catch (_) { /* Reading still works without storage. */ }
    }
    document.dispatchEvent(new CustomEvent('gravestone-theme-change'));
  }
  let saved = 'amber';
  try { saved = localStorage.getItem('gravestone-palette') || 'amber'; } catch (_) { /* Restricted browsers use the default. */ }
  apply(saved, false);
  for (const name of palettes) document.getElementById('theme-' + name).addEventListener('click', () => apply(name, true));
})();
