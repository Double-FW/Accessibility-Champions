"""Shared Accessibility Champions Networks export configuration and source integrity checks."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import urllib.request

SOURCE = 'Double-FW/Accessibility-Champions'
ROOT = Path(__file__).resolve().parents[1]
MANAGED = ('README.md', 'LICENSE', 'documents.jsonl', 'knowledge_chunks.jsonl',
           'provenance.json', 'record_schema.json', 'LICENSE_NOTICES.md',
           'validation_report.json')

def digest(data):
    return hashlib.sha256(data).hexdigest()

def load_config(root=ROOT):
    cfg = json.loads((Path(root)/'huggingface/export-config.json').read_text('utf-8'))
    if cfg['source_repository'] != SOURCE:
        raise ValueError('The source must be the approved Accessibility Champions Networks repository.')
    paths = cfg['files']
    if not paths or len(set(paths)) != len(paths):
        raise ValueError('Approved paths are missing or duplicated.')
    for path in paths + ['LICENSE']:
        p = PurePosixPath(path)
        if p.is_absolute() or '..' in p.parts or any(x.startswith('.') for x in p.parts):
            raise ValueError('Unsafe source path: ' + path)
        if path != 'LICENSE' and p.suffix not in ('.md', '.yaml', '.yml', '.json'):
            raise ValueError('Only approved documentation and reference data may be exported.')
    if not set(cfg['required_files']) <= set(paths + ['LICENSE']):
        raise ValueError('Required files must also be approved.')
    if not set(cfg.get('document_only_files', [])) <= set(paths):
        raise ValueError('Document-only sources must be approved.')
    return cfg

def destination(value):
    if value != 'GarethFW/Accessibility_Champions_Networks':
        raise ValueError('The destination must be GarethFW/Accessibility_Champions_Networks.')
    return value

def public_source():
    request = urllib.request.Request('https://api.github.com/repos/' + SOURCE,
        headers={'User-Agent': 'Double-FW-Accessibility Champions Networks-dataset-export'})
    with urllib.request.urlopen(request, timeout=30) as response:
        info = json.load(response)
    if info.get('full_name') != SOURCE or info.get('private') is not False or info.get('visibility') != 'public':
        raise ValueError('Publishing requires the approved public Accessibility Champions Networks GitHub source.')

def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])

def read_sources(root, cfg):
    root = Path(root)
    tree = {}
    for line in git(root, 'ls-tree', '-rz', '--full-tree', 'HEAD').split(b'\0'):
        if not line:
            continue
        attrs, raw_path = line.split(b'\t', 1)
        mode, kind, sha = attrs.decode().split()
        tree[raw_path.decode('utf-8')] = (mode, kind, sha)
    sources, manifest, omitted = {}, [], []
    for path in cfg['files'] + ['LICENSE']:
        if path not in tree:
            if path in cfg['required_files']:
                raise ValueError('Required source is missing: ' + path)
            omitted.append(path)
            continue
        mode, kind, sha = tree[path]
        if mode != '100644' or kind != 'blob':
            raise ValueError('Source must be a committed regular file: ' + path)
        data = git(root, 'cat-file', 'blob', sha)
        check = hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()
        if check != sha:
            raise ValueError('Git blob integrity failed: ' + path)
        sources[path] = data.decode('utf-8')
        manifest.append({'path': path, 'git_blob_sha': sha, 'sha256': digest(data), 'size_bytes': len(data)})
    if digest(sources['LICENSE'].encode()) != cfg['approved_license_sha256']:
        raise ValueError('Licence text changed. Review the licence, metadata and approved checksum together.')
    return sources, manifest, omitted
