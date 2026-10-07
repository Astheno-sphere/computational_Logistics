"""Copy benchmark evidence for publication, removing only operational metadata.

Requests, attempts, model responses and every numeric measurement stay byte for
byte identical. The original report hash and each removed field are recorded.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


def digest(data):
    return hashlib.sha256(data).hexdigest()


def export(source, destination):
    report = json.loads((source / 'report.json').read_bytes())
    hostname = report.get('client_hostname', report.get('runtime', {}).get('hostname'))
    if not isinstance(hostname, str) or not hostname:
        raise ValueError('Original client hostname is required to bind the measurement client')
    workloads = json.loads((source / 'requests.json').read_bytes())['workloads']
    if any(row.get('kind') not in ('demo_request', 'synthetic_scaling') for row in workloads):
        raise ValueError('This exporter only covers the latency suite; other held-out payloads need a separate redistribution review')
    redactions = []
    for path in [('checkpoint',), ('client_hostname',), ('runtime', 'hostname'),
                 ('runtime', 'cuda_visible_devices'), ('configuration', 'checkpoint'),
                 ('configuration', 'requests'), ('configuration', 'output')]:
        parent = report
        for key in path[:-1]:
            parent = parent.get(key, {})
        if path[-1] in parent:
            parent[path[-1]] = '[redacted operational metadata]'
            redactions.append('.'.join(path))
    if report.get('gpu_snapshot_before'):
        report['gpu_snapshot_before'] = re.sub(r'GPU-[0-9a-f-]+', '[redacted GPU UUID]', report['gpu_snapshot_before'])
        redactions.append('gpu_snapshot_before: GPU UUIDs only; occupancy values retained')
    payloads = {'report.json': (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()}
    for name in ('requests.json', 'samples.jsonl', 'payloads.json'):
        path = source / name
        if path.exists():
            payloads[name] = path.read_bytes()
    if not {'requests.json', 'samples.jsonl'} <= payloads.keys():
        raise ValueError('Complete requests and raw samples are required')
    # Token prefixes need a boundary: opaque encrypted reasoning can contain the
    # letters "sk-" in the middle of a base64url string without being an API key.
    blocked = re.compile(rb'/Users/|/data/zefan/|/mnt/localssd/|hf_[A-Za-z0-9]{20,}|(?:ghp_|github_pat_)[A-Za-z0-9_]{20,}|(?<![A-Za-z0-9_-])sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}|-----BEGIN (?:RSA|OPENSSH|EC) PRIVATE KEY-----')
    for name, content in payloads.items():
        if blocked.search(content):
            raise ValueError('Unreviewed operational or credential-like content in ' + name)
    destination.mkdir(parents=True, exist_ok=False)
    files = {}
    for name, content in payloads.items():
        (destination / name).write_bytes(content)
        files[name] = {'original_sha256': digest((source / name).read_bytes()),
                       'public_sha256': digest(content), 'bytes': len(content),
                       'byte_identical_to_original': name != 'report.json'}
    manifest = {'schema_version': 1, 'purpose': 'Public benchmark evidence',
                'client_identity_sha256': digest(hostname.encode()),
                'client_identity_method': 'SHA256 of original client hostname, shared across provider runs; hostname is not published.',
                'redacted_report_fields': redactions, 'files': files,
                'requests_samples_responses_and_numeric_measurements_modified': False,
                'original_internal_files_modified': False}
    (destination / 'publication.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'destination': str(destination), 'files': len(files), 'operational_fields_redacted': len(redactions)}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    export(args.source, args.destination)
