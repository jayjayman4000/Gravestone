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
  // Refresh only telemetry; never reload the page or disturb workspace state.
  let pollTimer = null;
  let inFlight = null;
  function unavailable(label, detail) {
    for (const id of ['system-battery', 'system-storage']) {
      $(id).textContent = label;
      $(id).title = detail;
    }
  }
  async function refreshSystem() {
    if (document.visibilityState === 'hidden' || inFlight) return;
    clearTimeout(pollTimer);
    const controller = new AbortController();
    const request = {controller, paused: false};
    inFlight = request;
    const deadline = setTimeout(() => controller.abort(), 5000);
    try {
      const data = await api('/api/system', {cache: 'no-store', signal: controller.signal});
      if (request.paused || controller.signal.aborted || document.visibilityState === 'hidden') return;
      const battery = data.battery;
      const storage = data.storage;
      if (battery && battery.available === true && Number.isFinite(battery.percent) && battery.percent >= 0 && battery.percent <= 100) {
        const status = ['Charging', 'Discharging', 'Full', 'Not charging'].includes(battery.status) ? battery.status : 'Unknown';
        $('system-battery').textContent = Math.round(battery.percent) + '% · ' + status;
        $('system-battery').title = 'Battery reading reported by this computer';
      } else {
        $('system-battery').textContent = 'Unavailable';
        $('system-battery').title = 'No usable battery reading reported by this computer';
      }
      if (storage && storage.available === true && Number.isFinite(storage.free_bytes) && storage.free_bytes >= 0 && Number.isFinite(storage.total_bytes) && storage.total_bytes > 0 && storage.free_bytes <= storage.total_bytes) {
        $('system-storage').textContent = (storage.free_bytes / 1000000000).toFixed(1) + ' GB free';
        $('system-storage').title = 'Configured archive data storage, not necessarily this USB drive';
      } else {
        $('system-storage').textContent = 'Unavailable';
        $('system-storage').title = 'No usable reading for configured archive data storage';
      }
    } catch (_) {
      if (!request.paused) unavailable('Unavailable · stale', 'Telemetry request failed; current reading unavailable');
    } finally {
      clearTimeout(deadline);
      inFlight = null;
      if (document.visibilityState === 'visible') {
        if (request.paused) refreshSystem();
        else pollTimer = setTimeout(refreshSystem, 15000);
      }
    }
  }
  // visibilitychange bubbles to window, alongside focus and BFCache pageshow.
  window.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') {
      clearTimeout(pollTimer);
      if (inFlight) {
        inFlight.paused = true;
        inFlight.controller.abort();
      }
      unavailable('Unavailable · paused', 'Telemetry paused while this page is hidden');
    } else refreshSystem();
  });
  window.addEventListener('focus', refreshSystem);
  window.addEventListener('pageshow', refreshSystem);
  refreshSystem();
})();
