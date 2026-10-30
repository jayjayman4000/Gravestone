'use strict';
// Controlled workspaces keep searches and unsaved notebook drafts in place.
(() => {
  function bindDialog(name, openerID) {
    const dialog = $(name);
    const opener = $(openerID);
    const back = $(name + '-back');
    let returnTo = opener;
    function open(from) {
      returnTo = from || opener;
      if (!dialog.open) dialog.showModal();
      back.focus();
    }
    opener.addEventListener('click', () => open(opener));
    back.addEventListener('click', () => dialog.close());
    dialog.addEventListener('close', () => { if (returnTo && returnTo.isConnected) returnTo.focus(); });
    return open;
  }
  const openLibrary = bindDialog('library', 'nav-library');
  bindDialog('notebook', 'nav-notebook');
  bindDialog('display-menu', 'nav-display-menu');
  bindDialog('start-here', 'nav-start-here');
  const openMap = bindDialog('map-view', 'nav-map');
  bindDialog('map-tools', 'nav-map-tools');
  $('topic-maps').addEventListener('click', () => openMap($('topic-maps')));
  $('start-open-library').addEventListener('click', () => {
    $('start-here').close();
    openLibrary($('nav-library'));
  });
  $('nav-command').addEventListener('click', event => {
    event.preventDefault();
    $('command-query').focus();
  });
  libraryReady.then(library => {
    $('start-source-links').replaceChildren();
    if (!library || !library.documents.length) {
      $('start-source-links').append(element('p', 'No installed source originals available.'));
      return;
    }
    for (const doc of library.documents) $('start-source-links').append(localLink(doc, doc.title));
  });
  // Read once: lack of a battery, endpoint or usable mount is not a zero reading.
  api('/api/system').then(data => {
    const battery = data.battery;
    const storage = data.storage;
    if (battery && battery.available === true && Number.isFinite(battery.percent) && battery.percent >= 0 && battery.percent <= 100) {
      $('system-battery').textContent = Math.round(battery.percent) + '%' + (battery.charging === true ? ' · Charging' : '');
    }
    if (storage && storage.available === true && Number.isFinite(storage.free_bytes) && storage.free_bytes >= 0 && Number.isFinite(storage.total_bytes) && storage.total_bytes > 0 && storage.free_bytes <= storage.total_bytes) {
      $('system-storage').textContent = (storage.free_bytes / 1000000000).toFixed(1) + ' GB free';
      $('system-storage').title = 'Configured archive data storage, not necessarily this USB drive';
    }
  }).catch(() => { /* Unavailable remains visible; never substitute fake telemetry. */ });
})();
