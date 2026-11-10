"""Publish the Accessibility Champions Networks export to one user-configured, existing dataset."""
import argparse
import json
import os
from pathlib import Path
import sys

from champions_hf_common import ROOT, SOURCE, MANAGED, destination, digest, load_config, public_source

def changes_between(old, new):
    a = {r['id']: r for r in old}
    b = {r['id']: r for r in new}
    def content(record):
        return {k: v for k, v in record.items() if k not in ('source_commit', 'source_commit_date', 'source_url')}
    return {'added': sorted(b.keys() - a.keys()), 'removed': sorted(a.keys() - b.keys()),
            'updated': sorted(k for k in a.keys() & b.keys() if content(a[k]) != content(b[k]))}

def publish(folder, token, dataset_id=None, *, api=None, download=None, check_public=public_source):
    cfg = load_config()
    target = destination(cfg['destination_dataset'] if dataset_id is None else dataset_id)
    if not token:
        raise ValueError('Add HF_TOKEN to this Accessibility Champions Networks repository under Actions secrets.')
    check_public()
    folder = Path(folder)
    report = json.loads((folder/'validation_report.json').read_text('utf-8'))
    provenance = json.loads((folder/'provenance.json').read_text('utf-8'))
    if (report.get('status') != 'passed' or provenance.get('source_repository') != SOURCE or
            report.get('source_commit') != provenance.get('source_commit')):
        raise ValueError('The validated export must come from the approved Accessibility Champions Networks source.')
    for name, checksum in report['export_file_sha256'].items():
        if name not in MANAGED or digest((folder/name).read_bytes()) != checksum:
            raise ValueError('The export has changed after validation: ' + name)
    if set(report['export_file_sha256']) != set(MANAGED) - {'validation_report.json'}:
        raise ValueError('The export checksum inventory is incomplete.')
    from huggingface_hub import CommitOperationAdd, HfApi, hf_hub_download
    from huggingface_hub.errors import EntryNotFoundError
    if api is None:
        api = HfApi(token=token)
        download = hf_hub_download
    info = api.repo_info(repo_id=target, repo_type='dataset')
    parent = info.sha
    old = {}
    for name in MANAGED:
        try:
            path = download(repo_id=target, filename=name, repo_type='dataset', revision=parent, token=token)
            old[name] = Path(path).read_bytes()
        except EntryNotFoundError:
            old[name] = None
    if old['provenance.json'] is not None:
        previous = json.loads(old['provenance.json'])
        if previous.get('source_repository') not in (None, SOURCE, 'https://github.com/' + SOURCE):
            raise ValueError('Destination provenance belongs to another source; refusing to overwrite it.')
    else:
        previous = {}
    payload = {name: (folder/name).read_bytes() for name in MANAGED}
    # The old change report is historical. Do not create a second commit just to clear it.
    if all(old[name] == payload[name] for name in MANAGED if name != 'validation_report.json'):
        return 'No changes; the Accessibility Champions Networks dataset is already up to date.'
    deltas = {}
    for name in ('documents.jsonl', 'knowledge_chunks.jsonl'):
        before = [json.loads(line) for line in (old[name] or b'').decode().splitlines() if line.strip()]
        after = [json.loads(line) for line in payload[name].decode().splitlines() if line.strip()]
        deltas[name] = changes_between(before, after)
    report['previous_source_commit'] = previous.get('source_commit')
    report['destination_dataset'] = target
    report['record_changes'] = deltas
    report['live_publication_tested'] = False
    payload['validation_report.json'] = (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode()
    operations = [CommitOperationAdd(path_in_repo=name, path_or_fileobj=payload[name])
                  for name in MANAGED if old[name] != payload[name]]
    api.create_commit(repo_id=target, repo_type='dataset', operations=operations,
        parent_commit=parent, commit_message='Update Double FW Accessibility Champions Networks knowledge dataset',
        commit_description='GitHub source revision: ' + provenance['source_commit'])
    return f'Updated {len(operations)} Accessibility Champions Networks dataset files. Existing raw files and dataset visibility were preserved.'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', required=True)
    args = parser.parse_args()
    try:
        result = publish(args.folder, os.environ.get('HF_TOKEN'))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print('Accessibility Champions Networks publishing failed (' + type(exc).__name__ + '). Check the token permissions, source visibility and dataset access. No credential or HTTP body is logged.', file=sys.stderr)
        return 1
    print(result)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as f:
            f.write('## Accessibility Champions Networks dataset update\n\n' + result + '\n')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
