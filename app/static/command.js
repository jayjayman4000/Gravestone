'use strict';
// Retrieval UI: exact publisher excerpts, never generated procedures.
(() => {
  const state = $('model-state');
  const status = $('command-status');
  const results = $('command-results');
  const cancel = $('command-cancel');
  let version = 0;
  let controller = null;

  async function search(event) {
    event.preventDefault();
    const current = ++version;
    if (controller) controller.abort();
    controller = null;
    cancel.hidden = true;
    results.replaceChildren();
    const query = $('command-query').value.trim();
    if (!query || query.length > 200) {
      state.textContent = '';
      status.textContent = query ? 'Use at most 200 characters per search.' : 'Enter a search term or choose a topic.';
      $('command-query').focus();
      return;
    }
    controller = new AbortController();
    cancel.hidden = false;
    state.textContent = 'Searching…';
    status.textContent = 'Searching installed source text…';
    results.setAttribute('aria-busy', 'true');
    try {
      const data = await api('/api/command?q=' + encodeURIComponent(query), {signal: controller.signal});
      await libraryReady;
      if (current !== version) return;
      state.textContent = data.mode === 'ai-assisted' ? 'Keyword assistance' : 'Keyword search';
      status.textContent = data.results.length ? data.results.length + ' source excerpts for “' + query + '”' : 'No matching installed source for “' + query + '”. Try another term or browse Source Documents.';
      if (data.message) results.append(element('p', data.message, 'coverage-note'));
      if (data.warning && (data.results.length || data.related_results?.length)) {
        results.append(element('p', data.warning, 'coverage-note'));
      }
      const renderHit = hit => {
        // Provenance comes from the manifest; the physical page belongs to this hit.
        const source = {...hit, ...documentsByFile.get(hit.file), page: hit.page};
        const card = element('article', undefined, 'search-hit');
        const open = localLink(source, hit.title);
        open.className = 'source-open';
        open.setAttribute('aria-label', hit.title + ' — ' + (hit.page ? 'open PDF page ' + hit.page : 'open original'));
        card.append(open,
          element('p', (hit.publisher || source.publisher || 'Publisher not supplied') + ' · ' + (hit.page ? 'PDF page ' + hit.page : 'Page not indexed'), 'source-meta'));
        if (source.edition) card.append(element('p', source.edition, 'source-meta'));
        if (hit.missing_terms?.length) {
          card.append(element('p', 'Partial keyword match · Missing query words: ' + hit.missing_terms.join(', '), 'coverage-note'));
        }
        card.append(element('pre', hit.excerpt, 'snippet'));
        return card;
      };
      for (const hit of data.results) results.append(renderHit(hit));
      if (data.related_results?.length) {
        const related = element('details');
        related.append(element('summary', 'Partial keyword matches · may be unrelated (' + data.related_results.length + ')'),
          element('p', 'These passages do not meet the query-word threshold. They are not evidence that this topic is covered.', 'coverage-note'));
        for (const hit of data.related_results) related.append(renderHit(hit));
        results.append(related);
      }
    } catch (error) {
      if (current !== version) return;
      state.textContent = 'Search unavailable';
      results.replaceChildren();
      status.textContent = 'Search failed: ' + error.message + '. Retry or browse Source Documents.';
    } finally {
      if (current === version) {
        controller = null;
        cancel.hidden = true;
        results.setAttribute('aria-busy', 'false');
      }
    }
  }
  $('command-form').addEventListener('submit', search);
  cancel.addEventListener('click', () => {
    ++version;
    if (controller) controller.abort();
    controller = null;
    cancel.hidden = true;
    results.setAttribute('aria-busy', 'false');
    state.textContent = '';
    status.textContent = 'Search cancelled.';
    results.replaceChildren();
    $('command-query').focus();
  });
  const topics = {
    'first-aid': 'first aid trauma', water: 'water food', repair: 'engine repair',
    power: 'generator radio', shelter: 'shelter heating'
  };
  for (const [topic, query] of Object.entries(topics)) {
    $('topic-' + topic).addEventListener('click', () => {
      $('command-query').value = query;
      $('command-query').focus();
      return search({preventDefault() {}});
    });
  }
  libraryReady.then(library => {
    if (!library) return;
    const titles = library.documents.map(doc => doc.title).join(' ');
    // These labels describe title-level coverage, not source safety verification.
    $('coverage-first-aid').textContent = /first aid|trauma/i.test(titles) ? 'Search installed sources' : 'Trauma manual: Not installed';
    $('coverage-repair').textContent = /repair|maintenance/i.test(titles) ? 'Search installed sources' : 'Repair manual: Not installed';
    $('coverage-water').textContent = /water|food/i.test(titles) ? 'Water & food sources · foraging not installed' : 'Dedicated sources: Not installed';
    $('coverage-power').textContent = /generator/i.test(titles) ? 'Generator safety · radio manual not installed' : 'Dedicated sources: Not installed';
    $('coverage-shelter').textContent = /preparedness/i.test(titles) ? 'Preparedness · defense manual not installed' : 'Dedicated sources: Not installed';
  });
})();
