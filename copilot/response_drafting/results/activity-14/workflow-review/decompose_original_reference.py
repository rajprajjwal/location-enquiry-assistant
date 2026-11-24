"""Lock an assistant-authored English decomposition of unchanged working GT questions."""
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent

# Numbering follows first occurrence in the locked original reference, not predictions.
FACTS = {
    1: ['Whether self-hosting is acceptable or a managed API is required.'],
    2: ['Whether Place Details is called after selecting a suggestion.'],
    3: ['Whether keystrokes are debounced.'],
    4: ['The Place Details SKU that terminates the sessions.'],
    5: ['The account ID.'],
    6: ['The exact query submitted.', 'The prediction returned for that query.'],
    7: ['Whether a hard country restriction or a geographic bias is required.'],
    8: ['Whether points of interest are required in addition to addresses.'],
    9: ['The debounce interval currently used.'],
    10: ['Whether a hard restriction or a geographic bias is required.'],
    11: ['The required peak type-ahead request rate.', 'The required type-ahead geographic coverage.'],
    12: ['Who operates the API backend.', 'The result retention rights required.',
         'The result redistribution rights required.', 'The result resale rights required.'],
    13: ['Whether live-traffic ETAs are required or static routes are sufficient.'],
    14: ['The vehicle types to be routed.'],
    15: ['Whether the Google Cloud project is new or existing.'],
    16: ['The expected monthly volume.'],
    17: ['Whether traffic estimates are needed at request time or for future departures.'],
    18: ['Whether instructions must be voice or text.'],
    19: ['Whether hazardous-material restrictions are required.',
         'Whether vehicle-height restrictions are required.', 'Whether vehicle-weight restrictions are required.'],
    20: ['Whether the current account balance is positive.'],
    21: ['The number of route requests per month.'],
    22: ['Whether live-traffic ETAs are required.'],
    23: ['The vehicle types.'],
    24: ['The number of stops per route.'],
    25: ['Whether an existing Google project is available.', 'Whether an Ola contract is available.'],
    26: ['Whether calls use the REST web service or an SDK.'],
    27: ['The signing certificate used by the build.'],
    28: ['The actual via coordinate.'],
    29: ['The endpoint being called.', 'The overview parameter value being sent.'],
    30: ['When the key was exposed.'],
    31: ['Whether unusual usage spikes occurred.'],
    32: ['The exact returned status string.'],
    33: ['Whether the commercial arrangement is a contract or prepaid.'],
    34: ['Whether live traffic is required or historical/typical ETAs are sufficient.'],
    35: ['Whether the load is spread across several API keys or tokens.'],
    36: ['The peak number of Directions requests per minute.'],
    37: ['The expected request rate.'],
    38: ['Whether live traffic is essential or typical ETAs are acceptable.'],
    39: ['Whether the Google Cloud project is new.'],
    40: ['The vehicle models that must be supported.', 'The charger networks that must be supported.'],
    41: ['Whether origins are provided as coordinates or addresses.',
         'Whether destinations are provided as coordinates or addresses.'],
    42: ['Whether traffic is required.', 'Whether a travel mode other than driving is required.'],
    43: ['Whether inputs are coordinates or addresses.'],
    44: ['Whether traffic is needed for all matrices.'],
    45: ['The start date.'],
    46: ['The SLA requirements.'],
    47: ['The usage export.'],
    48: ['The Nepal cities that must be supported.'],
    49: ['The number of origins in each matrix.', 'The number of destinations in each matrix.'],
    50: ['Whether there is operational capacity to host the routing engine.',
         'Whether there is operational capacity to update the routing engine.'],
    51: ['The matrix size sent per request.'],
    52: ['The number of origins per request.', 'The number of destinations per request.',
         'Whether traffic-aware ETAs are required.'],
    53: ['The requested cost-comparison basis: pairs, elements or requests.'],
    54: ['Whether Mapbox driving-traffic will be used.'],
    55: ['The approximate number of requests per minute currently being sent.'],
    56: ['Whether the commercial arrangement is a contract or prepaid credits.'],
    57: ['Whether results must be stored.'],
    58: ['Whether lookups are user-triggered or periodic tracking.'],
    59: ['Sample input points.'],
    60: ['Whether full street addresses or only locality names are required in the requested language.'],
    61: ['Whether traffic spiked.', 'Whether a deployment used a new server or domain.'],
    62: ['Whether results must be stored long-term.'],
    63: ['The required peak request rate.', 'The required monthly volume.'],
    64: ['The required result language, including whether Hindi is required.'],
    65: ['Whether results will be stored.', 'Whether public Nominatim is acceptable.',
         'Whether Mapbox temporary geocoding is acceptable.'],
    66: ['Whether street-address/rooftop precision is a hard filter.',
         'Whether an address-element breakdown is required.'],
    67: ['The providers being considered besides Google and Nominatim.'],
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = OUT / 'original-working-reference.json'
    original = json.loads(path.read_text())
    unique = list(dict.fromkeys(question['question'] for row in original['cases'] for question in row['questions']))
    assert len(unique) == len(FACTS) == 67
    mapping = {text: FACTS[index] for index, text in enumerate(unique, 1)}
    if any(question.get('facts') for row in original['cases'] for question in row['questions']):
        assert all(question.get('facts') == mapping[question['question']] for row in original['cases'] for question in row['questions'])
    review = {'review_kind': 'Assistant-authored and independently cross-checked by a second agent before candidate generation. Baseline generation began in parallel; neither reviewer used predictions for decomposition. Not independent human review.',
             'policy': 'Original question text and grouping remain unchanged. Alternatives for one decision are one fact; independently requested values or checks are separate facts. No prediction-derived labels or supplied-fact contradiction correction.',
             'questions': [{'question': text, 'facts': mapping[text]} for text in unique]}
    original['status'] = 'original_gt_question_text_locked_atomic_decomposition_assistant_reviewed'
    original['atomic_fact_policy'] = review['policy']
    original['atomic_fact_review'] = review['review_kind']
    for row in original['cases']:
        for question in row['questions']:
            question['facts'] = mapping[question['question']]
    path.write_text(json.dumps(original, indent=2, ensure_ascii=False) + '\n')
    review_path = OUT / 'original-atomic-decomposition.json'
    review_path.write_text(json.dumps(review, indent=2, ensure_ascii=False) + '\n')
    manifest_path = OUT / 'original-reference-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['reference_sha256'] = digest(path)
    manifest['atomic_decomposition_sha256'] = digest(review_path)
    manifest['gold_atomic_facts'] = sum(len(q['facts']) for row in original['cases'] for q in row['questions'])
    manifest['unique_question_texts'] = len(unique)
    manifest['atomic_decomposition_review'] = review['review_kind']
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({key: manifest[key] for key in ['cases', 'gold_question_groups', 'gold_atomic_facts', 'unique_question_texts', 'reference_sha256', 'atomic_decomposition_sha256']}, indent=2))


if __name__ == '__main__':
    main()
