'use strict';
(() => {
  const dialog = $('online-setup');
  let loaded = false;
  $('nav-online-setup').addEventListener('click', async () => {
    dialog.showModal();
    $('setup-skip').focus();
    if (loaded) return;
    try {
      const catalog = await api('/api/setup');
      $('setup-guides').replaceChildren();
      for (const guide of catalog.guides) {
        const row = element('section');
        const label = element('label', guide.title + ' · official terms/download page');
        const address = element('input');
        address.type = 'url'; address.value = guide.url; address.readOnly = true;
        address.id = 'publisher-' + guide.id;
        label.htmlFor = address.id;
        const copy = element('button', 'Copy publisher page address'); copy.type = 'button';
        copy.addEventListener('click', async () => {
          address.focus(); address.select();
          try {
            await navigator.clipboard.writeText(guide.url);
            $('setup-status').textContent = 'Address copied. Open it in a separate ordinary browser; this archive stays here.';
          } catch (_) {
            $('setup-status').textContent = 'Address selected. Use your system Copy command, then a separate ordinary browser.';
          }
        });
        row.append(label, address, copy); $('setup-guides').append(row);
        const option = element('option', guide.title); option.value = guide.id;
        $('setup-source').append(option);
      }
      loaded = true;
    } catch (error) { $('setup-status').textContent = error.message; }
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
        'X-Source-Id': $('setup-source').value
      }, body: file});
      const library = await loadLibrary();
      if (!library || !library.documents.some(item => item.id === doc.id && item.sha256 === doc.sha256)) throw new Error('Library read-back did not confirm import');
      $('setup-status').textContent = 'Personal PDF imported and confirmed in Source Documents. ' + doc.extraction_status;
      $('setup-file').value = ''; $('setup-rights').checked = false;
    } catch (error) { $('setup-status').textContent = 'Import not confirmed: ' + error.message; }
    finally { $('setup-submit').disabled = false; }
  });
})();
