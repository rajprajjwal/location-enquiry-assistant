"""Keep planning evidence bounded, diverse and traceable to exact retrieved spans."""
import hashlib
import json

from copilot.qualification.evidence import planning_evidence


def passage(url, text, **extra):
    return {'source_url': url, 'relevant_passage': text, **extra}


def serialized_size(value):
    return len(json.dumps(value, ensure_ascii=False, separators=(',', ':')))


def test_projection_preserves_exact_sources_and_original_span_identity():
    original = passage('https://docs.example.test/matrix', '  Matrix request limits depend on origins and destinations.  ')
    result = planning_evidence([original], 'Matrix origin and destination limits')
    assert len(result) == 1
    assert result[0]['source_url'] == original['source_url']
    assert result[0]['passage'] in original['relevant_passage']
    expected = hashlib.sha256((original['source_url'] + '\n' + original['relevant_passage']).encode()).hexdigest()[:20]
    assert result[0]['evidence_id'] == 'evidence_' + expected


def test_same_url_different_spans_keep_distinct_identities_and_exact_duplicates_drop():
    url = 'https://docs.example.test/matrix'
    a, b = passage(url, 'Origins and destinations define elements.'), passage(url, 'Traffic changes departure-time requirements.')
    result = planning_evidence([a, a.copy(), b], 'matrix traffic')
    assert len(result) == 2
    assert len({item['evidence_id'] for item in result}) == 2


def test_provider_diversity_is_preserved_when_ranked_passages_share_a_provider():
    sources = [
        passage('https://developers.google.com/matrix/a', 'Matrix origins and destinations.'),
        passage('https://cloud.google.com/matrix/b', 'Traffic departure-time conditions.'),
        passage('https://developers.google.com/matrix/c', 'Monthly workload limits.'),
        passage('https://docs.mapbox.com/matrix', 'Matrix request dimensions and traffic limits.'),
        passage('https://maps.olakrutrim.com/matrix', 'Matrix traffic-aware ETA support.'),
    ]
    result = planning_evidence(sources, 'Compare matrix dimensions, traffic and workload limits.', max_passages=3)
    urls = {item['source_url'] for item in result}
    assert any('google.com' in url for url in urls)
    assert any('mapbox.com' in url for url in urls)
    assert any('olakrutrim.com' in url for url in urls)


def test_requirement_topics_can_select_a_later_passage_from_the_same_url():
    url = 'https://docs.example.test/matrix'
    sources = [passage(url, 'Matrix origins and destinations define the request.'),
               passage(url, 'Matrix origins and destinations are request fields.'),
               passage(url, 'Traffic changes departure-time conditions.')]
    result = planning_evidence(sources, 'matrix traffic and departure conditions', max_passages=2)
    assert any('Traffic changes' in item['passage'] for item in result)
    assert any('origins and destinations' in item['passage'] for item in result)


def test_relevant_section_is_projected_instead_of_blindly_truncating_the_start():
    text = 'General introduction. ' * 80 + 'Traffic departure conditions require a future departure time.' + ' Reference material.' * 80
    source = passage('https://docs.example.test/matrix', text)
    result = planning_evidence([source], 'traffic departure conditions', max_chars=450)
    assert 'Traffic departure conditions' in result[0]['passage']
    assert result[0]['passage'] in text
    assert serialized_size(result) <= 450


def test_total_serialized_budget_includes_urls_ids_unicode_and_escaped_newlines():
    sources = [passage(f'https://docs.example.test/reference/{i}', ('Traffic\n"limits" भारत. ' * 100)) for i in range(12)]
    result = planning_evidence(sources, 'traffic limits', max_passages=6, max_chars=900)
    assert 0 < len(result) <= 6
    assert serialized_size(result) <= 900
    assert all(any(item['source_url'] == source['source_url'] and item['passage'] in source['relevant_passage'] for source in sources) for item in result)


def test_bad_sources_and_unaffordable_metadata_are_skipped():
    sources = [None, {}, passage('file:///private/docs', 'Local file.'),
               passage('https://docs.example.test/' + 'x' * 1000, 'Too expensive.'),
               passage('https://docs.example.test/ok', 'Traffic limits apply.')]
    result = planning_evidence(sources, 'traffic limits', max_chars=250)
    assert len(result) == 1
    assert result[0]['source_url'].endswith('/ok')
    assert serialized_size(result) <= 250


def test_limits_empty_inputs_and_input_immutability():
    source = passage('https://docs.example.test/api', 'Traffic limits apply.', provider='Example')
    before = source.copy()
    assert planning_evidence([], 'traffic') == []
    assert planning_evidence([source], 'traffic', max_passages=0) == []
    assert planning_evidence([source], 'traffic', max_chars=2) == []
    first = planning_evidence([source], 'traffic')
    assert first == planning_evidence([source], 'traffic')
    assert source == before
