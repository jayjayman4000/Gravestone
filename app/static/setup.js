'use strict';
(() => {
  const dialog = $('online-setup');
  $('nav-online-setup').addEventListener('click', () => {
    dialog.showModal();
    $('setup-skip').focus();
  });
  $('setup-skip').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => $('nav-online-setup').focus());
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
