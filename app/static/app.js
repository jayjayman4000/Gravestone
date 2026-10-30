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
  if (typeof path !== 'string' || !path || /^[a-z][a-z0-9+.-]*:/i.test(path) || path.includes('\\') || path.includes('\0')) return null;
  const parts = path.split('/');
  if (parts.some(part => !part || part === '.' || part === '..')) return null;
  return '/content/' + parts.map(encodeURIComponent).join('/');
}
const documentsByFile = new Map();
let readerOpener = null;
let readerVersion = 0;
async function openReader(doc, opener) {
  const version = ++readerVersion;
  readerOpener = opener;
  $('reader-title').textContent = doc.title;
  $('reader-source').replaceChildren(
    element('p', 'Unmodified local publisher original · ' + (doc.publisher || 'Publisher not supplied')),
    element('p', doc.rights || 'Rights information not supplied. Consult collection provenance.'),
    element('p', 'Publisher URL (requires network): ' + (doc.url || 'Not supplied'))
  );
  if (/cdc|centers for disease control/i.test((doc.publisher || '') + ' ' + (doc.url || ''))) {
    $('reader-source').append(element('p', 'Source: Centers for Disease Control and Prevention (CDC). This material is available free from CDC. Reference to CDC does not imply endorsement by CDC, ATSDR, HHS, or the United States Government of Gravestone or any product or service.'));
  }
  const url = contentURL(doc.file);
  $('reader-body').replaceChildren();
  $('reader-status').textContent = 'Checking local original…';
  $('reader-download').hidden = true;
  $('reader-download').removeAttribute('href');
  $('reader').showModal();
  $('reader-back').focus();
  try {
    const response = await fetch(url, {method: 'HEAD', redirect: 'error', credentials: 'same-origin'});
    if (version !== readerVersion || !$('reader').open) return;
    if (!response.ok || response.headers.get('Content-Type') !== 'application/pdf') {
      throw new Error('Local PDF original unavailable or not a PDF.');
    }
    $('reader-download').href = url;
    $('reader-download').download = doc.file.split('/').pop();
    $('reader-download').hidden = false;
    $('reader-status').textContent = 'If the PDF is blank or cannot display, download the original for a PDF-capable viewer, or use Back to library. Downloading does not save your notebook.';
    const frame = element('iframe');
    frame.title = doc.title;
    frame.addEventListener('error', () => {
      if (version === readerVersion) $('reader-status').textContent = 'PDF could not display. Download the original or use Back to library.';
    });
    frame.src = url;
    $('reader-body').replaceChildren(frame);
  } catch (_) {
    if (version === readerVersion && $('reader').open) {
      $('reader-status').textContent = 'Local PDF original unavailable or could not be opened. Use Back to library and check the installed collection.';
    }
  }
}
$('reader-back').addEventListener('click', () => $('reader').close());
$('reader').addEventListener('close', () => {
  ++readerVersion;
  $('reader-body').replaceChildren();
  if (readerOpener && readerOpener.isConnected) readerOpener.focus();
  readerOpener = null;
});
function localLink(doc, title) {
  const link = element('button', title, 'button');
  link.type = 'button';
  if (contentURL(doc.file) && /\.pdf$/i.test(doc.file)) {
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
      card.append(element('h3', hit.title), element('p', PREVIEW_WARNING, 'warning'),
                  element('pre', hit.excerpt), localLink(documentsByFile.get(hit.file) || hit, 'Read original in full'));
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
