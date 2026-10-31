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
STOPWORDS = frozenset('a an and are as at be by can could do does for from how i in is it me my of on or please should tell that the their them there these they this to us was we what when where which who why will with would you your find help'.split())


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


def command_search(content_dir, query, *, model_url='http://127.0.0.1:8767', timeout: float = 20):
    """Return mechanically sliced search previews, not substantive generated text."""
    if not isinstance(query, str) or len(query) > 2048 or not _query_terms(query):
        return {'query': query if isinstance(query, str) else '', 'mode': 'keyword-only',
                'model_status': 'not-called', 'terms': [], 'expansion_terms': [],
                'results': [], 'warning': PREVIEW_WARNING,
                'message': 'Enter a topic with meaningful search words (maximum 2048 characters). No model was called.'}
    original_terms = _query_terms(query)
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
                'terms': terms, 'expansion_terms': additions, 'results': [], 'warning': PREVIEW_WARNING,
                'message': message + 'Partial keyword matches may be unrelated; matches are not answers. Read the original in full context.'}
    try:
        documents = read_manifest(content_dir)['documents']
    except (OSError, ValueError):
        documents = []
    seen_files = set()
    for doc in documents:
        if doc['file'] in seen_files:
            continue
        seen_files.add(doc['file'])
        try:
            with open_file(content_dir, doc['file']):
                pass
            text = read_text(content_dir, doc.get('text_file'), TEXT_LIMIT)
        except (OSError, ValueError):
            continue
        for page, source in enumerate(text.split('\f'), 1):
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
            response['results'].append({'id': doc['id'], 'title': doc['title'],
                'publisher': doc.get('publisher', ''), 'file': doc['file'], 'page': page,
                'excerpt': source[start:start + 600], 'score': score,
                'matched_terms': [term for term, _ in matches]})
    response['results'].sort(key=lambda hit: -hit['score'])
    response['results'] = response['results'][:10]
    if not response['results']:
        response['message'] += ' Library gap: no matching original-source pages found in the available local library. Coverage is incomplete; no advice is generated.'
    return response
