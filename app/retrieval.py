"""Original-source retrieval; a local model may propose keywords, never answers."""
import re
import http.client
import ipaddress
import json
import socket
import os
import threading
import time
from urllib.parse import urlsplit

from . import PREVIEW_WARNING, read_manifest, read_text, open_file

TEXT_LIMIT = 16 * 1024 * 1024
STOPWORDS = frozenset('a an and are as at be by can could do does for from how i in is it me my of on or please should tell that the their them there these they this to us was we what when where which who why will with would you your find help guidance'.split())


def _query_terms(query):
    return list(dict.fromkeys(word.lower() for word in re.findall(r'[^\W_]+', query)
                              if 1 < len(word) <= 48 and word.lower() not in STOPWORDS))[:16]


def _parse_terms(completion, query):
    if not isinstance(completion, str) or len(completion) > 16384:
        raise ValueError('Invalid completion')
    completion = re.sub(r'<think>.*?</think>', '', completion, flags=re.I | re.S).strip()
    if completion.startswith('```'):
        fenced = re.fullmatch(r'```(?:json)?\s*(.*?)\s*```', completion, re.S | re.I)
        if not fenced:
            raise ValueError('Invalid JSON fence')
        completion = fenced.group(1)
    data = json.loads(completion)
    if not isinstance(data, dict) or not isinstance(data.get('terms'), list):
        raise ValueError('Invalid keyword JSON')
    generic = STOPWORDS | {'emergency', 'survival', 'safe', 'safety', 'guide', 'information', 'preparedness'}
    seen = set(_query_terms(query))
    terms = []
    for value in data['terms'][:128]:
        if not isinstance(value, str):
            continue
        term = value.strip(' ').lower()
        if (len(term) > 48 or not re.fullmatch(r'[^\W\d_]+', term)
                or any(word in generic for word in term.replace('-', ' ').split())
                or len(term) < 2 or term in seen):
            continue
        terms.append(term)
        seen.add(term)
        if len(terms) == 4:
            break
    return terms


def _model_terms(query, model_url, timeout):
    try:
        url = urlsplit(model_url)
        host = url.hostname
        if (url.scheme != 'http' or url.username is not None or url.password is not None
                or url.path not in ('', '/') or url.query or url.fragment):
            return [], 'invalid-url'
        host = '127.0.0.1' if host == 'localhost' else host
        if not ipaddress.ip_address(host).is_loopback:
            return [], 'invalid-url'
        port = url.port or 80
    except (ValueError, TypeError):
        return [], 'invalid-url'
    payload = {'messages': [
        {'role': 'system', 'content': 'Return JSON only: {"terms":["keyword"]}. Propose at most 4 close single-word search synonyms (individual nouns, no phrases) for the query; no advice, no answers, no commands. /no_think'},
        {'role': 'user', 'content': query + '\n/no_think'}],
        'temperature': 0, 'max_tokens': 128,
        'response_format': {'type': 'json_object'},
        'chat_template_kwargs': {'enable_thinking': False}}
    budget = max(0.01, min(float(timeout), 20))
    deadline = time.monotonic() + budget
    connection = http.client.HTTPConnection(str(host), port, timeout=budget)
    response = connected_socket = timer = None

    def remaining():
        seconds = deadline - time.monotonic()
        if seconds <= 0:
            raise TimeoutError('Local model deadline exceeded')
        return seconds

    def interrupt(sock):
        # Capture the socket BEFORE getresponse(): Connection: close detaches
        # connection.sock, but the response can still be blocked in recv().
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    try:
        # Numeric loopback only: connect has its own bounded timeout; the same
        # monotonic budget then covers request, headers, body and decoding.
        connection.connect()
        connected_socket = connection.sock
        connected_socket.settimeout(remaining())
        timer = threading.Timer(remaining(), interrupt, args=(connected_socket,))
        timer.start()
        connection.request('POST', '/v1/chat/completions', json.dumps(payload).encode(),
                           {'Content-Type': 'application/json', 'Accept': 'application/json'})
        remaining()
        response = connection.getresponse()
        remaining()
        if response.status != 200:
            return [], 'unavailable'
        raw = response.read(32769)
        remaining()
        if len(raw) > 32768:
            return [], 'invalid-response'
        completion = json.loads(raw)['choices'][0]['message']['content']
        terms = _parse_terms(completion, query)
        remaining()
        return terms, 'available'
    except (TimeoutError, socket.timeout):
        return [], 'timeout'
    except (OSError, ValueError, TypeError, KeyError, IndexError, RecursionError, http.client.HTTPException):
        # shutdown may surface as EOF, incomplete JSON, or a socket error.
        return [], 'timeout' if time.monotonic() >= deadline else 'invalid-response'
    finally:
        if timer is not None:
            timer.cancel()
            timer.join()  # No outstanding callback or per-request thread.
        if response is not None:
            response.close()
        connection.close()
        if connected_socket is not None:
            connected_socket.close()


def _best_passage(source, original_terms):
    """Find maximum distinct local coverage, then its shortest physical span.

    All occurrences matter: first occurrences can be far from the best cluster.
    The sliding window is bounded by the same 600 characters we actually show.
    """
    occurrences = sorted((match.start(), match.end(), term)
                         for term in original_terms
                         for match in re.finditer(r'(?<!\w)' + re.escape(term) + r'(?!\w)',
                                                  source, re.I))
    counts = {}
    left = 0
    best = None
    for right, (_, end, term) in enumerate(occurrences):
        counts[term] = counts.get(term, 0) + 1
        while end - occurrences[left][0] > 600:
            old = occurrences[left][2]
            counts[old] -= 1
            if not counts[old]:
                del counts[old]
            left += 1
        # Discard redundant leading occurrences to measure the tightest cluster.
        while left < right and counts[occurrences[left][2]] > 1:
            counts[occurrences[left][2]] -= 1
            left += 1
        first = occurrences[left][0]
        # PDF layout whitespace is not semantic distance. Normalize only for
        # scoring; the returned preview is still an untouched physical slice.
        span = len(re.sub(r'\s+', ' ', source[first:end]))
        key = (len(counts), -span, -first)
        if best is None or key > best[0]:
            best = (key, max(0, end - 600, first - 100), len(counts), span)
    assert best is not None  # Caller admits only pages anchored by original terms.
    return best[1:]


def _page_roles(doc, page_count):
    """Read optional editorial physical-page ranges; invalid metadata is neutral.

    These are inspected publisher-structure labels, never inferred from keywords
    or page positions. Mixed pages with safety warnings/emergency caveats must be
    main or safety, not frontmatter/reference/endmatter. Missing labels are neutral.
    """
    ranges = doc.get('page_roles')
    note = doc.get('page_roles_note')
    if (not isinstance(ranges, list) or not ranges or len(ranges) > page_count
            or not isinstance(note, str) or not note.strip() or len(note) > 4096
            or type(doc.get('pages')) is not int or doc['pages'] != page_count):
        return {}
    roles = {}
    previous_end = 0
    for item in ranges:
        if not isinstance(item, dict):
            return {}
        start, end, role = (item.get(key) for key in ('start', 'end', 'role'))
        if (type(start) is not int or type(end) is not int
                or not previous_end < start <= end <= page_count
                or role not in ('main', 'safety', 'frontmatter', 'reference', 'endmatter')):
            return {}  # No partial application of a malformed/overlapping overlay.
        roles.update((page, role) for page in range(start, end + 1))
        previous_end = end
    return roles


def command_search(content_dir, query, *, model_url='http://127.0.0.1:8767', timeout: float = 20, personal=None):
    """Return mechanically sliced search previews, not substantive generated text."""
    if not isinstance(query, str) or len(query) > 2048 or not _query_terms(query):
        return {'query': query if isinstance(query, str) else '', 'mode': 'keyword-only',
                'model_status': 'not-called', 'terms': [], 'expansion_terms': [],
                'results': [], 'related_results': [],
                'coverage': {'status': 'invalid-query', 'required_terms': []},
                'warning': PREVIEW_WARNING,
                'message': 'Enter a topic with meaningful search words (maximum 2048 characters). No model was called.'}
    original_terms = _query_terms(query)
    # Short topics need every subject/action word: "engine repair" must never
    # become a repair-only hit. Longer questions may retain a strongly anchored
    # passage with one absent qualifier, disclosed explicitly rather than lost.
    minimum_local_terms = len(original_terms) - (len(original_terms) >= 4)
    if model_url == 'http://127.0.0.1:8767':
        model_url = os.environ.get('GRAVESTONE_MODEL_URL', model_url)
    additions, status = _model_terms(query, model_url, timeout)
    terms = list(dict.fromkeys(original_terms + additions))
    if additions:
        message = 'Local model supplied search keywords. '
    elif status == 'available':
        message = 'Keyword-only search; local model responded but supplied no accepted new keywords. '
    else:
        message = 'Keyword-only search; local model not available or response unusable. '
    response = {'query': query, 'mode': 'ai-assisted' if additions else 'keyword-only', 'model_status': status,
                'terms': terms, 'expansion_terms': additions, 'results': [], 'related_results': [],
                'coverage': {'status': 'no-local-coverage', 'required_terms': original_terms,
                             'minimum_local_terms': minimum_local_terms},
                'warning': PREVIEW_WARNING,
                'message': message + 'Primary results require all query words together for short topics, or all but one for queries of four or more words. Missing query words are listed; keyword overlap is not proof of topic coverage or relevance. Partial keyword matches below that threshold are separate and may be unrelated. Matches are not answers. Read the original in full context.'}
    try:
        documents = read_manifest(content_dir)['documents']
    except (OSError, ValueError):
        documents = []
    if personal is not None:
        documents.extend(personal.documents())
    seen_files = set()
    for doc in documents:
        if doc['file'] in seen_files:
            continue
        seen_files.add(doc['file'])
        root = personal.root.parent if personal is not None and doc.get('personal') else content_dir
        try:
            with open_file(root, doc['file']):
                pass
            text = read_text(root, doc.get('text_file'), TEXT_LIMIT)
        except (OSError, ValueError):
            continue
        pages = text.split('\f')
        page_roles = _page_roles(doc, len(pages))
        for page, source in enumerate(pages, 1):
            matches = [(term, re.search(r'(?<!\w)' + re.escape(term) + r'(?!\w)', source, re.I))
                       for term in terms]
            matches = [(term, match) for term, match in matches if match]
            original_matches = [(term, match) for term, match in matches if term in original_terms]
            if not original_matches:
                continue  # AI keywords can refine ranking, never admit an unanchored page.
            phrase = re.search(r'(?<!\w)' + r'\s+'.join(map(re.escape, original_terms)) + r'(?!\w)', source, re.I)
            start, local_coverage, span = _best_passage(source, original_terms)
            # Local original-query coverage dominates phrase/proximity bonuses.
            # Whole-page incidental matches and AI additions only break close ties.
            score = (1000 * local_coverage + 600 - span + len(original_matches)
                     + min(4, len(matches) - len(original_matches)))
            if phrase and len(original_terms) > 1:
                score += 200
            # A match anywhere on a page is insufficient: distinct query
            # subjects must be present together in the actual displayed slice.
            # Keep broad retrieval available without presenting partials as
            # primary evidence for an unsupported multiword intent.
            bucket = 'results' if local_coverage >= minimum_local_terms else 'related_results'
            end = min(len(source), start + 600)
            # Artificial slice edges must not turn a suffix/prefix of a longer
            # source word into a whole query word. Trim inward, never rewrite.
            while start > 0 and re.fullmatch(r'\w{2}', source[start - 1:start + 1]):
                start += 1
            while end < len(source) and re.fullmatch(r'\w{2}', source[end - 1:end + 1]):
                end -= 1
            excerpt = source[start:end]
            local_terms = [term for term in original_terms
                           if re.search(r'(?<!\w)' + re.escape(term) + r'(?!\w)', excerpt, re.I)]
            response[bucket].append({'id': doc['id'], 'title': doc['title'],
                'publisher': doc.get('publisher', ''), 'file': doc['file'], 'page': page,
                'excerpt': excerpt, 'score': score,
                'matched_terms': [term for term, _ in matches],
                'local_matched_terms': local_terms,
                'missing_terms': [term for term in original_terms if term not in local_terms]})
            if page in page_roles:
                # Metadata stays outside the untouched publisher excerpt. Surface
                # the scope/currency caveat even when introductory pages rank later.
                hit = response[bucket][-1]
                hit['page_role'] = page_roles[page]
                hit['page_role_note'] = 'Editorial manifest metadata: ' + doc['page_roles_note']
                if isinstance(doc.get('source_caveat'), str):
                    hit['source_caveat'] = doc['source_caveat']
    for bucket in ('results', 'related_results'):
        # Structure is only a tiebreak at equal original-query local coverage;
        # never prefer an incomplete procedure over a fully anchored warning.
        # Main, safety and unannotated pages are equally eligible. Existing
        # phrase/proximity scoring and stable manifest order break remaining ties.
        response[bucket].sort(key=lambda hit: (
            -len(hit['local_matched_terms']),
            hit.get('page_role') in ('frontmatter', 'reference', 'endmatter'),
            -hit['score']))
        response[bucket] = response[bucket][:10]
    if any('page_role' in hit for bucket in ('results', 'related_results')
           for hit in response[bucket]):
        response['message'] += (' Editorial page-role metadata orders equally covered '
                                'previews before phrase/proximity scoring; scope, contents '
                                'and references may rank later; roles do not exclude pages '
                                '(normal result limits still apply). Read the '
                                'complete original scope, warnings and caveats; structural '
                                'labels are not publisher text or safety review.')
    if response['results']:
        response['coverage']['status'] = ('local-query-match' if any(
            not hit['missing_terms'] for hit in response['results']) else 'partial-query-match')
    else:
        response['message'] += ' Library gap: no original-source preview meets the minimum local query-word coverage in the available local library. Coverage is incomplete; no advice is generated.'
    return response
