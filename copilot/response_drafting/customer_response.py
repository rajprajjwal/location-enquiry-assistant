"""Present verified workflow results without changing their decisions or claims."""
import re
from urllib.parse import quote, urlsplit


def _unique(values):
    return list(dict.fromkeys(value.strip() for value in values if isinstance(value, str) and value.strip()))


class _References:
    def __init__(self, citations):
        self.sources = []
        self.indexes = {}
        self.original = {}
        for number, citation in enumerate(citations, 1):
            url = citation.get('url', '')
            try:
                parsed = urlsplit(url)
            except ValueError:
                continue
            if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password:
                continue
            if url not in self.indexes:
                self.indexes[url] = len(self.sources) + 1
                self.sources.append(url)
            self.original[number] = url

    def link(self, url):
        if url not in self.indexes:
            return ''
        safe = quote(url, safe=":/?#[]@!$&'*+,;=%~-._")
        return f'[{self.indexes[url]}]({safe})'

    def text(self, text, citations=()):
        # Remap existing citation numbers before adding missing claim references.
        parts = re.split(r'(```[\s\S]*?```|`[^`\n]*`)', text)
        for index in range(0, len(parts), 2):
            part = re.sub(r'(?<!\S)(?<!: )\[(\d+)\](?!\()',
                          lambda m: self.link(self.original.get(int(m[1]))) or m[0], parts[index])
            for citation in citations:
                link = self.link(citation.get('url'))
                claim = citation.get('supports_claim') or citation.get('span')
                if link and claim and claim in part and claim + ' ' + link not in part:
                    part = part.replace(claim, claim + ' ' + link, 1)
            parts[index] = part
        return ''.join(parts)

    def links(self, findings):
        return ' '.join(_unique(self.link(item.get('url')) for item in findings))

    def markdown(self):
        return '\n'.join(f'- {self.link(url)} {urlsplit(url).hostname}' for url in self.sources)


def _cell(text):
    return str(text).replace('|', '\\|').replace('\n', '; ')


def _comparison_table(comparison, refs, original):
    rows = comparison.get('provider_results') or []
    if len(rows) < 2:
        return None
    dimensions = [d for d in ('pricing', 'capabilities', 'limits', 'coverage') if d in comparison.get('dimensions', [])]
    labels = {'pricing': 'Estimated monthly cost', 'capabilities': 'Capabilities', 'limits': 'Limits', 'coverage': 'Coverage'}
    lines = ['| Provider | ' + ' | '.join(labels[d] for d in dimensions) + ' |',
             '| --- | ' + ' | '.join('---' for _ in dimensions) + ' |']
    headlines = []
    for row in rows:
        cells = [row['provider']]
        for dimension in dimensions:
            value = row.get(dimension) or {}
            if value.get('status') == 'missing_evidence' or not value:
                content = 'Unverified: ' + (value.get('reason') or 'Supporting evidence is unavailable.')
            elif dimension == 'pricing':
                estimates = []
                for estimate in value.get('estimates', []):
                    amount = ('Vendor quote required' if estimate.get('monthly_cost') is None
                              else f"{estimate['currency']} {estimate['monthly_cost']} per month")
                    if (estimate.get('monthly_cost_inr') is not None and estimate.get('currency') == 'USD'
                            and re.search(r'\bINR\s+[\d,]', original)):
                        amount += f" (approximately INR {estimate['monthly_cost_inr']})"
                    estimates.append(f"{estimate['scenario']}: {amount} {refs.links(estimate.get('source_references', []))}".strip())
                    headlines.append(f"- {row['provider']} ({estimate['scenario']}): {amount} {refs.links(estimate.get('source_references', []))}".strip())
                content = '; '.join(estimates)
                if value.get('reason'):
                    content += '; ' + value['reason']
            else:
                content = value.get('summary') or '; '.join(item['span'] for item in value.get('findings', []))
                content += ' ' + refs.links(value.get('findings', []))
            cells.append(content.strip())
        lines.append('| ' + ' | '.join(_cell(cell) for cell in cells) + ' |')
    context = [block for block in original.split('\n\n') if block.startswith(('Each matrix ', 'Each autocomplete '))]
    heading = 'Estimated monthly costs:\n' + '\n'.join(headlines) if headlines else original.split('\n\n')[0]
    return (heading, '\n\n'.join([*context, '\n'.join(lines)])) if dimensions else None


def _price_table(text, comparison):
    if comparison.get('dimensions') != ['pricing'] or len(comparison.get('providers', [])) < 2:
        return None
    prefixes = [name.split()[0].casefold() for name in comparison['providers']]
    rows, extra, headlines = [], [], []
    for line in text.splitlines():
        match = re.match(r'^- ([^:]+): (.*)', line)
        if match and any(match[1].casefold().startswith(prefix) for prefix in prefixes):
            rows.append([match[1], match[2]])
            amount = re.search(r'\b(?:USD|INR)\s+[\d,]+(?:\.\d+)?', match[2])
            links = ' '.join(re.findall(r'\[\d+\]\([^)]+\)', match[2]))
            value = amount[0] + (' ' + links if links else '') if amount else match[2]
            headlines.append(f'- {match[1]}: {value}')
        elif rows and line.startswith('  '):
            rows[-1][1] += '; ' + line.strip()
        elif line.strip():
            extra.append(line)
    if len(rows) < 2:
        return None
    table = '| Provider / scenario | Estimated monthly cost and calculation |\n| --- | --- |\n'
    table += '\n'.join('| ' + ' | '.join(_cell(cell) for cell in row) + ' |' for row in rows)
    return ('Estimated monthly costs:\n' + '\n'.join(headlines),
            '\n\n'.join(part for part in ('\n'.join(extra), table) if part))


def _proposal_text(action):
    subject = 'handoff' if action.get('action_type') == 'propose_escalation' else 'record change'
    if action.get('executed') and action.get('approval_status') == 'approved':
        return f'The approved {subject} has been completed.'
    status = action.get('approval_status')
    if status == 'approved':
        return f'The {subject} has been approved and is awaiting application.'
    if status == 'rejected':
        return f'The proposed {subject} was not approved and has not been carried out.'
    return f'The proposed {subject} is awaiting review. It has not been carried out.'


def _render(sections):
    return {'format_version': '1.0', 'sections': sections,
            'markdown': '\n\n'.join(f"### {s['heading']}\n\n{s['content']}" for s in sections)}


def format_customer_response(result):
    """Return ordered Markdown sections using accepted content and active questions."""
    if result.get('output_validation_errors') or result.get('final_validation', {}).get('valid') is False:
        return _render([
            {'heading': 'Answer', 'content': 'I could not verify a complete answer from the available information.'},
            {'heading': 'Next step', 'content': 'Please have this enquiry reviewed before acting on an unverified answer.'},
        ])
    outputs = result.get('outputs') or {}
    action = outputs.get('next_action') or {}
    draft = result.get('response_draft') or {}
    comparison = outputs.get('comparison') or {}
    active = result.get('clarifying_questions') or {}
    questions = _unique(q['text'] for q in active.get('questions', []) if active.get('needed'))
    citations = draft.get('citations') or []
    refs = _References(citations)
    sections = []

    def add(heading, content):
        if content and content.strip():
            sections.append({'heading': heading, 'content': content.strip()})

    assumptions = list(comparison.get('assumptions') or [])
    if comparison.get('notes'):
        assumptions.append(comparison['notes'])
    for row in comparison.get('provider_results') or []:
        for estimate in row.get('pricing', {}).get('estimates', []):
            assumptions.extend(f"{row['provider']} — {estimate['scenario']}: {note}" for note in estimate.get('assumptions', []))

    kind = action.get('action_type')
    if result.get('status') == 'clarification_needed':
        field = (active.get('questions') or [{}])[0].get('field')
        answer = {'monthly_volume': 'I need your expected monthly request volume to calculate an estimate.',
                  'provider': 'The integration guidance depends on the map provider.',
                  'current_provider': 'The integration guidance depends on the map provider.'}.get(
                      field, 'I need the following information before I can complete your enquiry.')
        add('Answer', answer)
    elif kind in {'propose_escalation', 'propose_record_update'}:
        add('Answer', 'Your enquiry needs specialist review.' if kind == 'propose_escalation'
            else 'A change has been proposed for your record.')
        update = outputs.get('proposed_record_update') or {}
        proposal = update.get('proposal') or {}
        if kind == 'propose_record_update' and proposal:
            add('Key details', '\n'.join([f"Record: {proposal.get('record_id', '')}",
                *(f'- {key.replace("_", " ").capitalize()}: {value}' for key, value in (proposal.get('fields') or {}).items())]))
    elif draft and not draft.get('is_refusal'):
        text = draft.get('draft_text', '').strip()
        for assumption in _unique(assumptions):
            text = re.sub(r'(?m)^[ \t]*(?:[-*] )?' + re.escape(assumption) + r'[ \t]*$', '', text).strip()
        text = refs.text(text, citations)
        table = _comparison_table(comparison, refs, text) or _price_table(text, comparison)
        if table:
            answer, details = table
            add('Answer', answer)
            add('Key details', details)
        else:
            blocks = re.split(r'\n\s*\n', text, maxsplit=1)
            if blocks and re.match(r'^\s*(?:#{1,6}\s|```|\||[-*]\s|\d+\.\s)', blocks[0]):
                add('Answer', 'Here are the verified details for your enquiry.')
                add('Key details', text)
            else:
                add('Answer', blocks[0] if blocks else text)
                add('Key details', blocks[1] if len(blocks) > 1 else '')
        # A calculation can use evidence whose exact excerpt is not in the answer.
        missing = [refs.link(url) for url in refs.sources if refs.link(url) not in '\n'.join(s['content'] for s in sections)]
        if missing and sections:
            sections[-1]['content'] += '\n\n' + ' '.join(missing)
    else:
        add('Answer', 'I could not verify a complete answer from the available information.')

    gaps = [f'- {note}' for note in _unique(assumptions)] + [f'- {question}' for question in questions]
    add('Assumptions / missing information', '\n'.join(gaps))
    if kind in {'propose_escalation', 'propose_record_update'}:
        add('Next step', _proposal_text(action))
    elif questions:
        add('Next step', 'Share the requested information so I can continue with your enquiry.')
    elif not draft or draft.get('is_refusal') or kind == 'refuse':
        add('Next step', 'Please have this enquiry reviewed before acting on an unverified answer.')
    add('Sources', refs.markdown())
    return _render(sections)
