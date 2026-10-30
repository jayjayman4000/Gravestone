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
  if (typeof path !== 'string' || !path || path.includes('\\') || path.includes('\0')) return null;
  const parts = path.split('/');
  if (parts.some(part => !part || part === '.' || part === '..')) return null;
  return '/content/' + parts.map(encodeURIComponent).join('/');
}
function localLink(path, title) {
  const link = element('a', title, 'button');
  const url = contentURL(path);
  if (url) {
    link.href = url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.setAttribute('aria-label', title + ' (opens original in a new tab)');
  } else {
    link.textContent = 'Original file unavailable';
    link.removeAttribute('href');
  }
  return link;
}
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
      const card = element('article', undefined, 'document');
      card.append(element('span', doc.publisher || 'Publisher not supplied', 'eyebrow'),
                  element('h3', doc.title), element('p', 'Locally stored original document', 'muted'),
                  localLink(doc.file, 'Open original ↗'));
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
    if (version !== searchVersion) return;
    $('search-results').replaceChildren(element('p', `${data.results.length} preview matches (maximum 50). Missing or unextractable text is not searched.`, 'muted'));
    for (const hit of data.results) {
      const card = element('article', undefined, 'search-hit');
      card.append(element('h3', hit.title), element('p', PREVIEW_WARNING, 'warning'),
                  element('pre', hit.excerpt), localLink(hit.file, 'Read original in full ↗'));
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
