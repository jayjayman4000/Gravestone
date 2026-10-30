'use strict';
const $ = id => document.getElementById(id);
const PREVIEW_WARNING = 'Machine-extracted search preview — not verified; open the original document and read full context.';
function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function contentURL(path) {
  if (typeof path !== 'string' || !path || /^[a-z][a-z0-9+.-]*:/i.test(path) || path.includes('\\') || /[%?#\x00-\x1f\x7f]/.test(path)) return null;
  const parts = path.split('/');
  if (parts.some(part => !part || part === '.' || part === '..')) return null;
  return '/content/' + parts.map(encodeURIComponent).join('/');
}
function originalURL(path) {
  return typeof path === 'string' && path.startsWith('originals/') && /\.pdf$/i.test(path) ? contentURL(path) : null;
}
const documentsByFile = new Map();
let readerOpener = null;
let readerVersion = 0;
let readerState = null;
let readerControlsReady = false;
function readerInteger(value, fallback) {
  if (typeof value === 'string' && /^\d+$/.test(value)) value = Number(value);
  return Number.isSafeInteger(value) && value > 0 ? value : fallback;
}
function updateReaderControls() {
  const state = readerState;
  if (!state) return;
  $('reader-page').textContent = (state.ready ? 'Physical PDF page ' : 'Requested physical PDF page ') + state.page +
    (state.pages ? ' of ' + state.pages : '') + (state.ready ? '' : ' — not yet displayed');
  $('reader-prev').disabled = !state.loaded || state.page <= 1;
  $('reader-next').disabled = !state.loaded || state.page >= state.pages;
  $('reader-zoom-out').disabled = !state.loaded || state.zoom <= 50;
  $('reader-zoom-in').disabled = !state.loaded || state.zoom >= 300;
  $('reader-copy').disabled = !state.ready || !state.textCompatible;
  $('reader-zoom').textContent = state.zoom + '%';
}
async function renderReaderPage() {
  const state = readerState;
  if (!state || !state.loaded) return;
  const version = ++state.renderVersion;
  state.ready = false;
  clearReaderCopy();
  updateReaderControls();
  $('reader-status').textContent = 'Rendering original physical PDF page ' + state.page + '… Copy is unavailable until it is displayed.';
  const current = () => readerState === state && state.renderVersion === version && $('reader').open;
  try {
    const displayed = await state.viewer.render(state.page, state.zoom);
    if (!current() || !displayed) return;
    state.displayedPage = displayed.page;
    state.ready = true;
    updateReaderControls();
    $('reader-status').textContent = 'Original physical PDF page ' + displayed.page + ' displayed. ' +
      (state.textCompatible ? 'Copy uses unverified machine-extracted text from this page.' :
        'Manifest page count does not match the actual PDF; extracted-text copying is disabled.') +
      ' Export downloads the complete unchanged PDF, not your notebook.';
  } catch (_) {
    if (!current()) return;
    state.ready = false;
    updateReaderControls();
    $('reader-status').textContent = 'PDF page could not display. Export the complete original or use Back to library. No native viewer or replacement text is substituted.';
  }
}
function readerInit() {
  if (readerControlsReady) return;
  readerControlsReady = true;
  const controls = element('div', undefined, 'reader-controls');
  controls.id = 'reader-controls';
  controls.setAttribute('role', 'group');
  controls.setAttribute('aria-label', 'Original PDF page and zoom controls');
  const makeButton = (id, label, action) => {
    const button = element('button', label, 'button reader-control');
    button.id = id;
    button.type = 'button';
    button.addEventListener('click', action);
    return button;
  };
  const move = delta => {
    if (!readerState || !readerState.loaded) return;
    readerState.page = Math.max(1, Math.min(readerState.pages || 1, readerState.page + delta));
    return renderReaderPage();
  };
  const zoom = delta => {
    if (!readerState || !readerState.loaded) return;
    readerState.zoom = Math.max(50, Math.min(300, readerState.zoom + delta));
    return renderReaderPage();
  };
  const page = element('span');
  page.id = 'reader-page';
  page.setAttribute('aria-live', 'polite');
  const scale = element('span');
  scale.id = 'reader-zoom';
  controls.append(makeButton('reader-prev', '← Previous page', () => move(-1)), page,
    makeButton('reader-next', 'Next page →', () => move(1)),
    makeButton('reader-zoom-out', '− Zoom out', () => zoom(-25)), scale,
    makeButton('reader-zoom-in', '+ Zoom in', () => zoom(25)),
    makeButton('reader-copy', 'Copy page text', copyReaderText), $('reader-download'));
  const header = $('reader-header') || $('reader-title').parentElement || $('reader');
  header.append(controls);
  // Place primary controls before long notices so short displays do not clip them.
  const details = $('reader-details') || $('reader-source');
  if (typeof header.insertBefore === 'function' && details.parentElement === header) header.insertBefore(controls, details);
  const panel = element('section', undefined, 'reader-copy-panel');
  panel.id = 'reader-copy-panel';
  panel.hidden = true;
  panel.setAttribute('aria-label', 'Selectable source page text');
  const label = element('label', 'Clipboard unavailable. Text is selected below; use your system Copy command. Unverified extraction — compare the original PDF.');
  label.setAttribute('for', 'reader-copy-text');
  const box = element('textarea');
  box.id = 'reader-copy-text';
  box.readOnly = true;
  box.rows = 8;
  panel.append(label, box, makeButton('reader-copy-close', 'Close extracted text', () => {
    clearReaderCopy();
    $('reader-copy').focus();
  }));
  controls.parentElement.append(panel);
}
function clearReaderCopy() {
  if (readerState) ++readerState.copyVersion;
  $('reader-copy-panel').hidden = true;
  $('reader-copy-text').value = '';
}
async function copyReaderText() {
  const state = readerState;
  if (!state || !state.ready || !state.textCompatible) return;
  clearReaderCopy();
  const copyVersion = ++state.copyVersion;
  const page = state.displayedPage;
  const current = () => readerState === state && state.ready && state.displayedPage === page && state.copyVersion === copyVersion && $('reader').open;
  $('reader-status').textContent = 'Loading unverified extracted source-page text…';
  try {
    if (!state.textURL || !state.pages) throw new Error('No validated page text index.');
    const response = await fetch(state.textURL, {redirect: 'error', credentials: 'same-origin'});
    if (!current()) return;
    if (!response.ok || !/^text\/plain(?:;|$)/i.test(response.headers.get('Content-Type') || '')) throw new Error('Text index unavailable.');
    const raw = await response.text();
    if (!current()) return;
    const pages = raw.split('\f');
    if (pages.length !== state.pages || !pages[page - 1].trim()) throw new Error('No reliable extracted text for this physical page.');
    const copied = 'Source: ' + state.doc.title + ' · ' + (state.doc.publisher || 'Publisher not supplied') + '\n' +
      'Physical PDF page ' + page + ' of ' + state.pages + ' · Unverified machine-extracted text\n' +
      state.url + '#page=' + page + '\n\n' + pages[page - 1];
    $('reader-copy-text').value = copied;
    try {
      if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error('Clipboard API unavailable');
      await navigator.clipboard.writeText(copied);
      if (current()) {
        $('reader-copy-panel').hidden = true;
        $('reader-status').textContent = 'Copied extracted text from physical PDF page ' + page + '. Unverified extraction; compare the original PDF.';
      }
    } catch (_) {
      if (!current()) return;
      $('reader-copy-panel').hidden = false;
      $('reader-copy-text').focus();
      $('reader-copy-text').select();
      $('reader-status').textContent = 'Automatic clipboard copy unavailable. Selectable extracted text is open; use your system Copy command.';
    }
  } catch (_) {
    if (current()) $('reader-status').textContent = 'Extracted text unavailable for this physical page. Read or export the complete original PDF; no replacement text is generated.';
  }
}
readerInit();
async function openReader(doc, opener) {
  const manifest = documentsByFile.get(doc.file);
  doc = {...doc, ...manifest, page: doc.page};
  const pages = readerInteger(doc.pages, null);
  const textPath = manifest && manifest.text_file;
  const textURL = typeof textPath === 'string' && textPath.startsWith('search/') && /\.txt$/i.test(textPath) ? contentURL(textPath) : null;
  readerState?.viewer?.destroy();
  const state = {doc, textURL, copyVersion: 0, renderVersion: 0, page: readerInteger(doc.page, 1), pages: null, zoom: 100, ready: false, loaded: false};
  readerState = state;
  clearReaderCopy();
  updateReaderControls();
  const version = ++readerVersion;
  readerOpener = opener;
  $('reader-title').textContent = doc.title;
  const sourceInfo = element('details');
  sourceInfo.append(element('summary', 'Source information · rights & provenance'),
    element('p', 'Unmodified local publisher original · ' + (doc.publisher || 'Publisher not supplied')),
    element('p', doc.rights || 'Rights information not supplied. Consult collection provenance.'),
    element('p', 'Publisher URL (requires network): ' + (doc.url || 'Not supplied')),
    element('p', 'Retrieved: ' + (doc.retrieved_at || 'Not supplied') + ' · Edition: ' + (doc.edition || 'Not supplied')),
    element('p', 'SHA-256 (manifest): ' + (doc.sha256 || 'Not supplied')),
    element('p', doc.extraction_status || PREVIEW_WARNING)
  );
  if (/cdc|centers for disease control/i.test((doc.publisher || '') + ' ' + (doc.url || ''))) {
    sourceInfo.append(element('p', 'Source: Centers for Disease Control and Prevention (CDC). This material is available free from CDC. Reference to CDC does not imply endorsement by CDC, ATSDR, HHS, or the United States Government of Gravestone or any product or service.'));
  }
  $('reader-source').replaceChildren(sourceInfo);
  const url = originalURL(doc.file);
  $('reader-body').replaceChildren();
  $('reader-status').textContent = 'Checking local original…';
  $('reader-download').hidden = true;
  $('reader-download').removeAttribute('href');
  $('reader-download').textContent = 'Export original — complete PDF';
  $('reader-download').className = 'button reader-export';
  $('reader-download').title = 'Download the unchanged complete publisher PDF, not only the selected page';
  if (!$('reader').open) $('reader').showModal();
  $('reader-back').focus();
  try {
    if (!url) throw new Error('Invalid local original path.');
    const response = await fetch(url, {method: 'HEAD', redirect: 'error', credentials: 'same-origin'});
    if (version !== readerVersion || !$('reader').open) return;
    if (!response.ok || response.headers.get('Content-Type') !== 'application/pdf') {
      throw new Error('Local PDF original unavailable or not a PDF.');
    }
    $('reader-download').href = url;
    $('reader-download').download = doc.file.split('/').pop();
    $('reader-download').hidden = false;
    state.url = url;
    // Each open owns a separate mount: late cleanup cannot erase its successor.
    const mount = element('div');
    $('reader-body').replaceChildren(mount);
    const viewer = await window.loadControlledPDFViewer(mount);
    if (version !== readerVersion || !$('reader').open) { viewer.destroy(); return; }
    state.viewer = viewer;
    const actualPages = readerInteger(await viewer.load(url), null);
    if (version !== readerVersion || !$('reader').open) return;
    if (!actualPages) throw new Error('Invalid actual PDF page count.');
    state.pages = actualPages;
    state.page = Math.min(actualPages, state.page);
    state.textCompatible = pages === actualPages;
    state.loaded = true;
    await renderReaderPage();
  } catch (_) {
    if (version === readerVersion && $('reader').open) {
      state.viewer?.destroy();
      $('reader-status').textContent = 'Local PDF original unavailable or could not display. Export the complete original if available, or use Back to library. No native viewer or replacement text is substituted.';
    }
  }
}
$('reader-back').addEventListener('click', () => $('reader').close());
$('reader').addEventListener('close', () => {
  ++readerVersion;
  clearReaderCopy();
  readerState?.viewer?.destroy();
  readerState = null;
  $('reader-page').textContent = '';
  $('reader-zoom').textContent = '';
  $('reader-body').replaceChildren();
  if (readerOpener && readerOpener.isConnected) readerOpener.focus();
  readerOpener = null;
});
function localLink(doc, title) {
  const link = element('button', title, 'button');
  link.type = 'button';
  if (originalURL(doc.file)) {
    link.addEventListener('click', () => openReader(doc, link));
  } else {
    link.textContent = 'Original file unavailable (local PDF required)';
    link.disabled = true;
  }
  return link;
}
window.localLink = localLink;
async function api(path, options) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Local service request failed');
  return data;
}
function showError(target, error) {
  target.replaceChildren(element('p', error.message, 'error'));
}
async function loadStatus() {
  try {
    const status = await api('/api/status');
    $('runtime-status').textContent = status.status === 'prototype' ? 'Prototype online' : status.status;
    $('persistence-note').textContent = status.persistence_note;
  } catch (error) {
    $('runtime-status').textContent = 'Service unavailable';
  }
}
async function loadLibrary() {
  try {
    const library = await api('/api/library');
    $('document-count').textContent = String(library.documents.length).padStart(2, '0');
    $('document-list').replaceChildren();
    for (const doc of library.documents) {
      documentsByFile.set(doc.file, doc);
      const card = element('article', undefined, 'document');
      card.append(element('span', doc.publisher || 'Publisher not supplied', 'eyebrow'),
                  element('h3', doc.title), element('p', 'Locally stored original document', 'muted'),
                  localLink(doc, 'Open original'));
      const details = element('details');
      details.append(element('summary', 'Provenance & file details'));
      const list = element('dl');
      for (const [label, value] of [['Publisher', doc.publisher], ['Rights', doc.rights],
              ['Retrieved', doc.retrieved_at], ['SHA-256 (manifest)', doc.sha256],
              ['Text extraction', doc.extraction_status || 'Not visually verified']]) {
        list.append(element('dt', label), element('dd', value || 'Not supplied'));
      }
      details.append(list);
      try {
        const source = new URL(doc.url);
        if (['https:', 'http:'].includes(source.protocol)) {
          const link = element('a', 'Publisher source (requires network)', 'source-link');
          link.href = source.href;
          link.target = '_blank';
          link.rel = 'noopener noreferrer';
          details.append(link);
        }
      } catch (_) { /* Missing provenance is not a reason to invent it. */ }
      card.append(details);
      $('document-list').append(card);
    }
    if (!library.documents.length) $('document-list').append(element('p', 'No documents have been installed.'));
    return library;
  } catch (error) {
    $('document-count').textContent = 'Unavailable';
    showError($('document-list'), error);
    return null;
  }
}
let searchVersion = 0;
$('search-form').addEventListener('submit', async event => {
  event.preventDefault();
  const version = ++searchVersion;
  const query = $('search-query').value.trim();
  if (!query) { $('search-results').replaceChildren(); return; }
  $('search-results').replaceChildren(element('p', 'Searching installed text…'));
  try {
    const data = await api('/api/search?q=' + encodeURIComponent(query));
    await libraryReady; // Reuse full source/rights metadata for search originals.
    if (version !== searchVersion) return;
    $('search-results').replaceChildren(element('p', `${data.results.length} preview matches (maximum 50). Missing or unextractable text is not searched.`, 'muted'));
    for (const hit of data.results) {
      const card = element('article', undefined, 'search-hit');
      const source = {...hit, ...documentsByFile.get(hit.file), page: hit.page};
      const open = localLink(source, hit.title);
      open.className = 'source-open';
      card.append(open,
                  element('p', (source.publisher || 'Publisher not supplied') + ' · ' +
                    (hit.page ? 'PDF page ' + hit.page : 'PDF page not supplied'), 'source-meta'),
                  element('pre', hit.excerpt, 'snippet'));
      $('search-results').append(card);
    }
    if (!data.results.length) $('search-results').append(element('p', 'No matching preview text found. Browse the originals; this does not mean the topic is absent.'));
  } catch (error) {
    if (version === searchVersion) showError($('search-results'), error);
  }
});
let dirty = false;
async function loadNotes() {
  try {
    const notes = await api('/api/notes');
    $('note-text').value = notes.text;
    $('saved-preview').textContent = notes.text;
    $('note-text').disabled = false;
    $('save-note').disabled = false;
    $('note-status').textContent = 'Notebook loaded. Saves require persistent storage to survive a reboot.';
  } catch (error) { $('note-status').textContent = error.message + '. Editing is disabled to protect existing notes.'; }
}
$('note-text').addEventListener('input', () => {
  dirty = true;
  $('note-status').textContent = 'Unsaved changes · ' + new TextEncoder().encode($('note-text').value).length.toLocaleString() + ' / 262,144 bytes';
});
$('note-form').addEventListener('submit', async event => {
  event.preventDefault();
  const text = $('note-text').value;
  if (new TextEncoder().encode(text).length > 256 * 1024) {
    $('note-status').textContent = 'Not saved: notebook exceeds the 256 KiB UTF-8 limit.';
    return;
  }
  $('save-note').disabled = true;
  $('note-status').textContent = 'Saving…';
  try {
    await api('/api/notes', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text})});
    // Read back the exact target; an accepted request alone is not confirmation.
    const saved = await api('/api/notes');
    if (saved.text !== text) throw new Error('Saved notebook differs; another window may have changed it');
    $('saved-preview').textContent = saved.text;
    dirty = $('note-text').value !== text;
    $('note-status').textContent = dirty ? 'Saved earlier version; current edits are unsaved.' : 'Saved to configured data directory. Reboot persistence is not verified.';
  } catch (error) { $('note-status').textContent = 'Save not confirmed: ' + error.message; }
  finally { $('save-note').disabled = false; }
});
window.addEventListener('beforeunload', event => {
  if (dirty) { event.preventDefault(); event.returnValue = ''; }
});
loadStatus();
const libraryReady = loadLibrary();
loadNotes();
