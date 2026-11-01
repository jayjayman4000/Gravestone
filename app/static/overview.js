'use strict';
// Generated material stays outside the original renderer and page Copy path.
(() => {
  let source = null, version = 0, controller = null, ready = false;
  const results = $('overview-results'), status = $('overview-status');
  const generate = $('overview-generate'), cancel = $('overview-cancel');
  const availability = value => { ready = value; generate.disabled = !ready || !source?.doc.id || !!controller; };
  function stop() {
    ++version;
    controller?.abort();
    controller = null;
    cancel.hidden = true;
    availability(ready);
  }
  function clear() {
    stop();
    source = null;
    availability(false);
    results.replaceChildren();
    status.textContent = '';
    $('overview-query').value = '';
    $('reader-overview').open = false;
  }
  window.readerOverview = {
    availability, clear,
    reset(doc, getPage, goPage) {
      clear();
      source = {doc, getPage, goPage};
      $('overview-query').value = ($('command-query').value || $('search-query').value || '').slice(0, 200);
      status.textContent = 'No overview generated. Original PDF is unchanged.';
    }
  };
  generate.addEventListener('click', async () => {
    if (!source || !ready || controller) return;
    const active = source;
    const query = $('overview-query').value.trim();
    if (query.length > 200) { status.textContent = 'Use at most 200 characters.'; return; }
    stop();
    const token = version;
    controller = new AbortController();
    cancel.hidden = false;
    availability(ready);
    results.replaceChildren();
    status.textContent = 'Generating locally from selected source fragments; may take up to 2 minutes. You can keep reading or cancel the display.';
    const current = () => version === token && source === active && $('reader').open;
    try {
      const data = await api('/api/overview', {method: 'POST', redirect: 'error', credentials: 'same-origin',
        headers: {'Content-Type': 'application/json'}, signal: controller.signal,
        body: JSON.stringify({id: active.doc.id, query, page: active.getPage()})});
      if (!current()) return;
      if (data.status === 'disabled') {
        status.textContent = data.message || 'Experimental overview withheld pending quality validation. Read the original PDF.';
        return;
      }
      if (data.status !== 'available' || data.file !== active.doc.file || !Array.isArray(data.bullets) || !data.bullets.length) {
        status.textContent = 'Overview unavailable or no relevant extracted text. Read the original; no substitute advice is generated.';
        return;
      }
      results.append(element('p', data.warning, 'small'), element('p', data.scope, 'small'),
        element('p', 'Selected physical PDF pages: ' + data.selected_pages.join(', '), 'small'));
      for (const bullet of data.bullets) {
        const card = element('article');
        const citation = element('button', 'Read original · physical PDF page ' + bullet.page, 'button');
        citation.type = 'button';
        citation.addEventListener('click', () => {
          if (!current()) return;
          $('reader-overview').open = false;
          return active.goPage(bullet.page);
        });
        card.append(element('p', bullet.text), element('blockquote', bullet.quote), citation);
        results.append(card);
      }
      status.textContent = 'AI overview generated — unverified. Check quoted evidence against the original.';
    } catch (_) {
      if (current()) { results.replaceChildren(); status.textContent = 'Overview unavailable. Continue reading the unchanged original.'; }
    } finally {
      if (current()) { controller = null; cancel.hidden = true; availability(ready); }
    }
  });
  cancel.addEventListener('click', () => { stop(); results.replaceChildren(); status.textContent = 'Overview display cancelled; model may still finish locally. Original PDF unchanged.'; });
})();
