'use strict';
(() => {
  const dialog = $('online-setup');
  let opener = 'nav-online-setup';
  let busy = false;
  const controls = ['setup-network-connect', 'setup-network-offline', 'setup-browser'];
  async function refreshNetwork() {
    try {
      const state = await api('/api/desktop/status');
      $('setup-network-state').textContent = 'NetworkManager: ' + state.network_state + ' (not an internet-access check).';
    } catch (error) {
      $('setup-network-state').textContent = 'Network status unavailable: ' + error.message;
    }
  }
  for (const id of ['nav-online-setup', 'nav-network-setup']) {
    $(id).addEventListener('click', () => {
      opener = id;
      dialog.showModal();
      $('setup-skip').focus();
      return refreshNetwork();
    });
  }
  async function desktopAction(actions, message) {
    if (busy) return;
    busy = true;
    controls.forEach(id => { $(id).disabled = true; });
    $('setup-network-status').textContent = 'Requesting local desktop action…';
    try {
      let result;
      for (const action of actions) {
        result = await api('/api/desktop/' + action, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
      }
      $('setup-network-status').textContent = result.already_open ? 'Window is already open. Use Alt+Tab to switch to it; close it to return.' : message;
      await refreshNetwork();
    } catch (error) {
      $('setup-network-status').textContent = 'Action not confirmed: ' + error.message;
    } finally {
      busy = false;
      controls.forEach(id => { $(id).disabled = false; });
    }
  }
  $('setup-network-connect').addEventListener('click', () => desktopAction(['network-online', 'network-settings'], 'Networking enabled; use the native Wi-Fi / wired screen. Choose Back / Quit to return. Internet access is not confirmed.'));
  $('setup-network-offline').addEventListener('click', () => desktopAction(['network-offline'], 'NetworkManager stopped and networking disabled. Local reading and imports still work.'));
  $('setup-browser').addEventListener('click', () => desktopAction(['browser'], 'Download browser requested. Close its window to return, then choose your PDF from Home → Downloads below.'));
  $('setup-network-refresh').addEventListener('click', refreshNetwork);
  window.addEventListener('focus', () => { if (dialog.open && !busy) refreshNetwork(); });
  $('setup-skip').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => $(opener).focus());
  $('setup-maps').addEventListener('click', () => {
    dialog.close(); $('nav-map').click(); $('nav-map-tools').click();
  });
  $('setup-library').addEventListener('click', () => { dialog.close(); $('nav-library').click(); });
  $('setup-import').addEventListener('submit', async event => {
    event.preventDefault();
    const file = $('setup-file').files[0];
    if (!file || !file.size || file.size > 32 * 1024 * 1024 || !$('setup-rights').checked) {
      $('setup-status').textContent = 'Choose a PDF up to 32 MiB and acknowledge authorized personal use.';
      return;
    }
    $('setup-submit').disabled = true;
    $('setup-status').textContent = 'Importing and validating locally…';
    try {
      const doc = await api('/api/personal/import', {method: 'POST', headers: {
        'Content-Type': 'application/pdf', 'X-Personal-Rights': 'acknowledged',
        'X-Document-Title': encodeURIComponent($('setup-title-input').value),
        'X-Source-Id': 'other'
      }, body: file});
      const library = await loadLibrary();
      if (!library || !library.documents.some(item => item.id === doc.id && item.sha256 === doc.sha256)) throw new Error('Library read-back did not confirm import');
      $('setup-status').textContent = 'Personal PDF imported and confirmed in Source Documents. ' + doc.extraction_status;
      $('setup-file').value = ''; $('setup-rights').checked = false;
    } catch (error) { $('setup-status').textContent = 'Import not confirmed: ' + error.message; }
    finally { $('setup-submit').disabled = false; }
  });
})();
