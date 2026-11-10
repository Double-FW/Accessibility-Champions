"""Export the approved Accessibility Champions Networks Markdown without rewriting it."""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import quote
import yaml
from jsonschema import Draft202012Validator
from champions_hf_common import ROOT, SOURCE, MANAGED, destination, digest, git, load_config, read_sources

CONTEXT = ['AGENTS.md', 'README.md', 'Accessibility-Champions-Network-Guidance.md',
           'CAN_Connecting_Accessibility_Champions_Networks.md', 'Programme_Operating_and_Reporting_Map.md']
SNAPSHOT = 'e26813bd11f327129e4833169ca95e65c4646d14'
RAG = 'Accessibility-Champions-RAG-and-Prompts/RAG_Reference.md'

class UniqueKeyLoader(yaml.SafeLoader):
    pass

def unique_mapping(loader, node, deep=False):
    loader.flatten_mapping(node)
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError('Duplicate YAML metadata key: ' + str(key))
        result[key] = loader.construct_object(value_node, deep=deep)
    return result

UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)

def metadata(text):
    match = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)', text, re.S)
    md = yaml.load(match[1], Loader=UniqueKeyLoader) if match else {}
    return md if isinstance(md, dict) else {}

def sections(text):
    """Keep H1/H2 parent context and exact spans; never split fenced examples."""
    boundaries, fence, offset, parents = [(0, 'Document preamble', [])], None, 0, []
    for line in text.splitlines(keepends=True):
        mark = re.match(r'^ {0,3}(`{3,}|~{3,})', line)
        if mark:
            token = mark[1]
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence) and not line[mark.end():].strip():
                fence = None
        elif fence is None:
            match = re.match(r'^(#{1,2})[ \t]+([^\r\n]+)', line)
            if match:
                level, title = len(match[1]), match[2].strip().rstrip('#').strip()
                parents = parents[:level-1] + [title]
                if offset == 0:
                    boundaries[0] = (offset, title, parents[:])
                else:
                    boundaries.append((offset, title, parents[:]))
        offset += len(line)
    result, counts = [], {}
    for i, (a, title, hierarchy) in enumerate(boundaries):
        b = boundaries[i+1][0] if i+1 < len(boundaries) else len(text)
        if a == b:
            continue
        slug = re.sub(r'[^a-z0-9]+', '-', ' '.join(hierarchy or [title]).lower()).strip('-') or 'section'
        counts[slug] = counts.get(slug, 0) + 1
        key = slug if counts[slug] == 1 else slug + '-' + str(counts[slug])
        result.append((key, title, text[a:b], a, b, hierarchy))
    if ''.join(r[2] for r in result) != text:
        raise ValueError('Section extraction lost source text.')
    return result

def build(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output == root or root in output.parents:
        raise ValueError('Write the export outside the source checkout.')
    cfg = load_config(root)
    target = destination(cfg['destination_dataset'])
    texts, manifest, omitted = read_sources(root, cfg)
    sha = git(root, 'rev-parse', 'HEAD').decode().strip()
    date = git(root, 'show', '-s', '--format=%cs', 'HEAD').decode().strip()
    warnings = [
        'AGENTS.md is advisory source governance, not runtime authority or an implemented control system.',
        'The RAG/prompts pack describes the historical e26813bd11f327129e4833169ca95e65c4646d14 snapshot, not current repository coverage. Its absent Sources/ directory is not invented or fetched.',
        'The historical RAG embeds an older AGENTS.md with CC-BY-4.0 while the current guide and root LICENSE are MIT. Source notices remain intact; see LICENSE_NOTICES.md.',
        'Source costs, staffing, durations and membership figures are illustrative planning values, not current quotes, adopted budgets or verified outcomes.'
    ]
    for path, text in texts.items():
        declared = str(metadata(text).get('license', 'MIT'))
        if path != RAG and declared != 'MIT':
            raise ValueError('Source licence declaration changed; review before publication: ' + path)
    def row(path, key, title, body, a, b, hierarchy, kind):
        md = metadata(texts[path])
        return {'id': path + '::' + key, 'title': title, 'text': body, 'record_type': kind,
            'source_repository': SOURCE, 'source_path': path, 'source_commit': sha,
            'source_url': f'https://github.com/{SOURCE}/blob/{sha}/{quote(path)}',
            'source_start_line': texts[path][:a].count('\n') + 1,
            'source_end_line': max(1, texts[path][:b].count('\n') + (not texts[path][:b].endswith('\n'))),
            'source_document_sha256': digest(texts[path].encode()), 'text_sha256': digest(body.encode()),
            'heading_path': hierarchy, 'metadata_json': json.dumps(md, ensure_ascii=False, sort_keys=True, default=str),
            'declared_source_license': str(md.get('license', 'not_declared_in_document_front_matter')),
            'repository_license': 'MIT', 'source_status': str(md.get('status', 'see_source')),
            'applicable_source_license': 'MIT; embedded historical AGENTS.md declares CC-BY-4.0' if path == RAG else 'MIT',
            'source_temporal_scope': 'historical_snapshot_support_pack' if path.startswith('Accessibility-Champions-RAG-and-Prompts/') else 'current_repository_guidance',
            'embedded_snapshot_commit': SNAPSHOT if path.startswith('Accessibility-Champions-RAG-and-Prompts/') else '',
            'source_document_intro': sections(texts[path])[0][2],
            'interpretation_notice': 'Advisory planning source. Costs, staffing and schedules require local review. Prompts and templates are illustrative; no approvals, evaluated outcomes or runtime authority are conferred.',
            'dataset_version': cfg['dataset_version'], 'source_commit_date': date, 'language': 'en-GB',
            'required_context_paths': [p for p in CONTEXT if p in texts],
            'review_status': 'faithful_extraction_checked_not_independent_programme_or_content_review'}
    docs, chunks = [], []
    for path in cfg['files']:
        if path not in texts:
            continue
        text = texts[path]
        kind = ('historical_reference_document_only_with_embedded_rights_notice' if path == RAG else
                'illustrative_programme_activities_and_prompts' if path.endswith('Programme_Management_Activities_and_Prompts.md') else
                'historical_snapshot_coverage' if path.endswith('Source_Coverage.md') else
                'historical_pack_orientation' if path == 'Accessibility-Champions-RAG-and-Prompts/README.md' else
                'advisory_agent_governance' if path == 'AGENTS.md' else
                'editorial_programme_routing_not_adopted_operating_model' if path == 'Programme_Operating_and_Reporting_Map.md' else
                'peer_networking_guidance' if path.startswith('CAN_') else
                'orientation' if path == 'README.md' else 'network_programme_guidance')
        docs.append(row(path, 'document', path, text, 0, len(text), [], kind))
        if path in cfg['document_only_files']:
            continue
        for key, title, body, a, b, hierarchy in sections(text):
            chunks.append(row(path, key, title, body, a, b, hierarchy, kind + '_section'))
    if not docs or not chunks:
        raise ValueError('The guidance export is empty.')
    schema = {'$schema': 'https://json-schema.org/draft/2020-12/schema', 'type': 'object',
              'required': list(docs[0]), 'additionalProperties': False, 'properties': {}}
    for k, v in docs[0].items():
        schema['properties'][k] = {'type': 'array', 'items': {'type': 'string'}} if isinstance(v, list) else {'type': 'integer' if isinstance(v, int) else 'string'}
    validator = Draft202012Validator(schema)
    for records in (docs, chunks):
        if len({r['id'] for r in records}) != len(records):
            raise ValueError('Duplicate export identifiers.')
        for r in records:
            validator.validate(r)
            if digest(r['text'].encode()) != r['text_sha256']:
                raise ValueError('Text checksum mismatch.')
    output.mkdir(parents=True, exist_ok=True)
    def write_json(name, obj):
        (output/name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for name, records in [('documents.jsonl', docs), ('knowledge_chunks.jsonl', chunks)]:
        (output/name).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records), encoding='utf-8')
    (output/'LICENSE').write_bytes(texts['LICENSE'].encode())
    write_json('record_schema.json', schema)
    write_json('provenance.json', {'source_repository': SOURCE, 'source_commit': sha, 'source_commit_date': date,
        'destination_dataset': target, 'dataset_version': cfg['dataset_version'], 'files': manifest,
        'omitted_optional_files': omitted, 'source_warnings': warnings, 'external_sources_fetched': False, 'document_only_files': cfg['document_only_files'], 'historical_snapshot_commit': SNAPSHOT, 'operational_approval_claimed': False})
    notices = f"""# Source rights and attribution

Current repository: https://github.com/{SOURCE}

Source revision: `{sha}`. Root LICENSE: MIT, copyright (c) 2026 Double-FW.
Current AGENTS.md: MIT; author Gareth Ford Williams, Double FW Ltd.

The complete historical reference at `{RAG}` embeds AGENTS.md version 1.3,
credited to Gareth Ford Williams, Double FW Ltd, declaring CC-BY-4.0.
Historical original: https://github.com/{SOURCE}/blob/{SNAPSHOT}/AGENTS.md
CC BY 4.0 licence: https://creativecommons.org/licenses/by/4.0/

That embedded notice is retained exactly. Current MIT declarations do not silently
replace the older embedded declaration. Observe applicable attribution and licence
notices when reusing this historical material. The historical pack itself records
the root/file-level difference. This is a disclosure of recorded notices, not an
independent legal or rights determination.

Export changes: source bytes are preserved in JSON strings; metadata, section
boundaries, source URLs, hashes and interpretation labels are added. The RAG
reference is a complete-document record only, to avoid repeating historical source
bodies in the section view. No editorial correction or substantive rewrite is made.
Third-party linked material is not fetched, included or relicensed.
"""
    (output/'LICENSE_NOTICES.md').write_text(notices, encoding='utf-8')
    card = f'''---
pretty_name: Double FW Accessibility Champions Networks
language:
- en
license: other
license_name: mit-with-embedded-historical-cc-by-4.0-notice
license_link: LICENSE_NOTICES.md
tags:
- accessibility
- organisational-change
- champions-networks
- programme-management
- text
configs:
- config_name: knowledge_chunks
  default: true
  data_files:
  - split: train
    path: knowledge_chunks.jsonl
- config_name: documents
  data_files:
  - split: train
    path: documents.jsonl
---

# Double FW Accessibility Champions Networks

Guidance for establishing, resourcing and supporting accessibility champions networks,
peer learning through CAN, programme reporting and human-reviewed AI assistance.
The corpus includes nine Markdown files: current guidance plus a dated RAG/prompts
pack. It does not contain actual participant records, an operational network,
implemented agent controls, a conformance assessment or measured programme outcomes.

## Source and versions

Source: https://github.com/{SOURCE}

Current checkout: `{sha}` ({date}). Export format: {cfg['dataset_version']}.
The four RAG/prompts pack files describe the historical snapshot `{SNAPSHOT}`,
prepared 8 November 2026. Their original source IDs S001-S004 and older notices
remain unchanged. Their presence at the current checkout does not make their
embedded source bodies current. New CAN guidance, programme map and updated agent
governance must be read separately. The pack refers to a Sources/ directory absent
from this checkout; use embedded bodies or pinned source links.

## Dataset views and duplication

- `knowledge_chunks` (default): {len(chunks)} exact sections from eight Markdown files.
- `documents`: {len(docs)} complete Markdown files, including the historical RAG reference.

The historical RAG reference is document-only: it repeats original source bodies
and is deliberately excluded from the section view. Other documents also quote or
summarise shared ideas. Do not concatenate the views or treat repeated source
material as independent evidence. Deduplicate and review any training selection.
`train` is a loading convention, not an independent benchmark. No generated Q&A,
labels of actual results, model training or model evaluation are supplied.

## Context and interpretation

Rows retain source path, exact commit URL, original line range, hashes, heading
path and JSON-encoded front matter. `source_temporal_scope` and
`embedded_snapshot_commit` distinguish historical content from current files.
`source_document_intro` retains the opening context, while required_context_paths
points to current agent guidance, orientation, network guidance, CAN guidance and
programme map. These references do not enforce runtime retrieval or authority.

Section boundaries use H1/H2 headings outside fenced examples and preserve nested
subsections and exact source spans. Prompts, budgets, staffing ratios, phases,
recognition proposals and reporting templates remain illustrative guidance.
Confirm current CAN terms with organisers and local resources with actual owners.
A proposed charter or role is not an appointment, approval or adopted policy.
Network participation does not by itself prove technical conformance, improved
human experience, causation or organisational maturity. Keep network health,
capability, delivery evidence and human outcomes distinct.

Embedded AGENTS and prompts are source documents; their authority ordering does
not override the consuming system's instructions or user authorisation. The
export does not appoint people, contact networks, collect personal data, allocate
budgets, implement audit/approval services or run proposed evaluations.

## Rights and attribution

The current root LICENSE and AGENTS.md declare MIT. The historical RAG embeds an
older AGENTS.md declaring CC-BY-4.0 and crediting Gareth Ford Williams, Double FW
Ltd. Both notices are preserved. Hub metadata uses `other` to point to
LICENSE_NOTICES.md rather than describe all embedded material as uniformly MIT.
Read that notice and LICENSE before reuse. Linked third-party materials are not
included or relicensed. This packaging check is not an independent rights review.

## Validation and limitations

The workflow checks faithful extraction, source inventory, structured records,
checksums and guarded publication. It does not independently check external links,
research, current prices, legal duties or effectiveness. Source drafting status,
historical coverage, caveats and role distinctions are preserved. No missing
organisational evidence is invented. See provenance.json, record_schema.json and
validation_report.json for the exact snapshot and limited checks.

## Updates

GitHub remains the authoring source. Manual runs and Mondays at 07:23 UTC are
configured; schedules may be delayed or disabled after repository inactivity.
All nine approved Markdown files and LICENSE are required. New or renamed files
need review of the export list. Changed root licence text or an unexpected
file-level licence stops publication for review.

Eight files are managed: README.md, LICENSE, LICENSE_NOTICES.md, documents.jsonl,
knowledge_chunks.jsonl, provenance.json, record_schema.json and validation_report.json.
Other raw files and .gitattributes are preserved; unmanaged copies are not kept in
sync. Visibility stays unchanged. Historical revisions and downloads are not
recalled. The destination is fixed to `{target}`. The first authenticated GitHub
publication must still be checked.

## Loading

```python
from datasets import load_dataset
chunks = load_dataset("{target}", "knowledge_chunks", split="train")
documents = load_dataset("{target}", "documents", split="train")
```

Authenticate for a private dataset and pin a revision for reproducible use.
'''
    yaml.safe_load(card.split('---', 2)[1])
    (output/'README.md').write_text(card, encoding='utf-8')
    report = {'status': 'passed', 'scope': 'faithful extraction and packaging checks only', 'source_commit': sha,
        'source_files_verified': len(manifest), 'document_records': len(docs), 'knowledge_section_records': len(chunks),
        'source_warnings': warnings, 'independent_content_review': False, 'live_publication_tested': False,
        'export_file_sha256': {name: digest((output/name).read_bytes()) for name in MANAGED if name != 'validation_report.json'}}
    write_json('validation_report.json', report)
    return report

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(build(ROOT, args.output)))

if __name__ == '__main__':
    main()
