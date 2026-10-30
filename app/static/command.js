'use strict';
// Retrieval UI only. Publisher excerpts are displayed verbatim, never rewritten.
(() => {
  const state = $('model-state');
  const status = $('command-status');
  const results = $('command-results');
  const cancel = $('command-cancel');
  let searched = false;
  let version = 0;
  let controller = null;

  api('/api/status').then(() => {
    if (!searched) state.textContent = 'Model status shown after search';
  }).catch(() => {
    if (!searched) state.textContent = 'Model status shown after search';
  });

  api('/content/coverage.json').then(data => {
    if (!Array.isArray(data.topics)) throw new Error('Coverage list unavailable');
    $('coverage-description').textContent = (typeof data.description === 'string' ? data.description + ' ' : '') + 'Requests only — not installed instructions.';
    $('coverage-topics').replaceChildren();
    for (const topic of data.topics) {
      if (typeof topic.title === 'string') $('coverage-topics').append(element('li', topic.title + ' — not installed; source acquisition pending'));
    }
    if (!data.topics.length) $('coverage-topics').append(element('li', 'No coverage requests listed.'));
  }).catch(() => {
    $('coverage-topics').replaceChildren(element('li', 'Requested coverage list unavailable. This does not change the installed source library.'));
  });

  async function search(event) {
    event.preventDefault();
    const current = ++version;
    if (controller) controller.abort();
    controller = null;
    cancel.hidden = true;
    searched = true;
    results.replaceChildren();
    const query = $('command-query').value.trim();
    if (!query || query.length > 200) {
      state.textContent = 'Model status shown after search';
      status.textContent = query ? 'Use at most 200 characters per question.' : 'Enter a question to search the installed library.';
      $('command-query').focus();
      return;
    }
    controller = new AbortController();
    cancel.hidden = false;
    state.textContent = 'Local model: checking';
    status.textContent = 'Searching installed source text…';
    results.setAttribute('aria-busy', 'true');
    try {
      const data = await api('/api/command?q=' + encodeURIComponent(query), {signal: controller.signal});
      await libraryReady; // Retain full publisher URL and rights from the manifest.
      if (current !== version) return;
      state.textContent = (data.mode === 'ai-assisted' ? 'Locally powered by Qwen · keyword assistance' : 'Keyword search') + ' · ' + (data.model_status || 'Status not supplied');
      status.textContent = data.results.length + ' source preview matches. Read the originals before relying on any excerpt.';
      results.append(element('p', 'Question: ' + data.query, 'query-echo'),
                     element('p', 'Search terms: ' + data.terms.join(', '), 'terms'),
                     element('p', data.warning || PREVIEW_WARNING, 'warning'));
      if (data.message) results.append(element('p', data.message, 'retrieval-message'));
      if (!data.results.length) results.append(element('p', 'Collection gap: no matching source previews in this search. Coverage is incomplete; browse the original library or obtain an identified publisher source. No answer is generated.', 'warning'));
      for (const hit of data.results) {
        const source = {...hit, ...documentsByFile.get(hit.file)};
        const card = element('article', undefined, 'search-hit');
        card.append(element('h3', hit.title),
                    element('p', (hit.publisher || 'Publisher not supplied') + ' · ' + (hit.page ? 'Page ' + hit.page : 'Page not available'), 'source-meta'),
                    element('p', data.warning || PREVIEW_WARNING, 'warning'),
                    element('pre', hit.excerpt),
                    element('p', 'Matched terms: ' + (hit.matched_terms || []).join(', '), 'small'),
                    localLink(source, 'Read original in full'));
        results.append(card);
      }
    } catch (error) {
      if (current !== version) return;
      state.textContent = 'Search unavailable · model state not confirmed';
      results.replaceChildren();
      status.textContent = 'Search failed: ' + error.message + '. Retry or use the source library below.';
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
    state.textContent = 'Model status shown after search';
    status.textContent = 'Search cancelled. No results retained.';
    results.replaceChildren();
    $('command-query').focus();
  });
  for (const id of ['example-water', 'example-power']) {
    $(id).addEventListener('click', () => {
      $('command-query').value = id === 'example-water' ? 'Find safe drinking water guidance' : 'Find power outage guidance';
      $('command-query').focus();
      return search({preventDefault() {}});
    });
  }
})();
