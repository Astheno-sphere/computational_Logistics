"""Prepare the exact downloaded TREC candidate subsets for evaluation only."""
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = Path.cwd()  # Run from the code checkout; runs/ may be a shared symlink.
if not (REPO / 'jev/ir_eval.py').is_file():
    raise ValueError('Run preparation from the Open-Jev code checkout')
sys.path.insert(0, str(REPO))
from jev.ir_eval import load_external_holdout, ndcg_at_k

REVISION = '39db0a25a552dd2a12012df22029686bf7fdc050'
EXPECTED = {
    2019: {'file': 'retrieve_results_dl19_top100.jsonl', 'sha256': 'ec396c5725d0cec98739de9aff9fd6785da09e56fd21bee5b52dc19806f06899', 'qrels_md5': '2f4be390198da108f6845c822e5ada14', 'queries_md5': 'eda71eccbe4d251af83150abe065368c', 'queries': 43},
    2020: {'file': 'retrieve_results_dl20_top100.jsonl', 'sha256': 'ab556a0cf16f868759c77db68eed99da42345e3298fd423850b8c6e0f518e0ed', 'qrels_md5': '0355ccee7509ac0463e8278186cdd8d1', 'queries_md5': '00a406fb0d14ed3752d70d1e4eb98600', 'queries': 54},
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(year):
    expected = EXPECTED[year]
    source = ROOT / 'raw' / expected['file']
    qrel_path = ROOT / 'raw' / f'{year}qrels-pass.txt'
    query_path = ROOT / 'raw' / f'{year}queries.tsv.gz'
    if sha(source) != expected['sha256'] or hashlib.md5(qrel_path.read_bytes()).hexdigest() != expected['qrels_md5'] or hashlib.md5(query_path.read_bytes()).hexdigest() != expected['queries_md5']:
        raise ValueError('Pinned source checksum differs')
    official_queries = dict(line.split('\t', 1) for line in gzip.decompress(query_path.read_bytes()).decode().splitlines())
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    qrels = {}
    for line in qrel_path.read_text().splitlines():
        qid, iteration, docid, grade = line.split()
        if docid in qrels.setdefault(qid, {}):
            raise ValueError('Duplicate qrel')
        qrels[qid][docid] = int(grade)
    if len(rows) != expected['queries'] or {str(row['query']['qid']) for row in rows} != set(qrels):
        raise ValueError('Judged query set differs')
    candidates, unique_texts, normalized_count = [], {}, 0
    for row in rows:
        qid, query = str(row['query']['qid']), row['query']['text']
        if query != official_queries[qid]:
            raise ValueError('Candidate query text differs from official queries')
        documents, last = [], float('inf')
        if len(row['candidates']) != 100:
            raise ValueError('Expected exact top 100')
        for rank, candidate in enumerate(row['candidates'], 1):
            docid, score, doc = str(candidate['docid']), candidate['score'], candidate['doc']
            if set(doc) != {'contents'} or type(score) not in (int, float) or not math.isfinite(score) or score > last:
                raise ValueError('Unexpected passage fields or BM25 order')
            last = score
            original = doc['contents']
            text = ' '.join(original.split())
            normalized_count += text != original
            if not text or unique_texts.setdefault(docid, text) != text:
                raise ValueError('Empty or inconsistent repeated passage')
            documents.append({'id': docid, 'text': text, 'bm25_rank': rank, 'bm25_score': score})
        if len({doc['id'] for doc in documents}) != 100:
            raise ValueError('Duplicate candidate within query')
        candidates.append({'id': qid, 'query': query, 'documents': documents})
    output = ROOT / 'prepared' / f'dl{str(year)[2:]}'
    output.mkdir(parents=True, exist_ok=False)
    (output / 'candidates.jsonl').write_text(''.join(json.dumps(row, ensure_ascii=False, separators=(',', ':')) + '\n' for row in candidates))
    (output / 'qrels.txt').write_bytes(qrel_path.read_bytes())
    manifest = {
        'schema_version': 1, 'usage': 'evaluation_only', 'benchmark': f'TREC-DL{str(year)[2:]}',
        'retriever': {'name': 'BM25', 'top_k': 100, 'k1': .9, 'b': .4},
        'files_sha256': {name: sha(output / name) for name in ('candidates.jsonl', 'qrels.txt')},
        'candidate_source': {'repository': 'castorini/rank_llm_data', 'revision': REVISION,
            'file': 'retrieve_results/BM25/' + expected['file'],
            'url': f'https://huggingface.co/datasets/castorini/rank_llm_data/resolve/{REVISION}/retrieve_results/BM25/' + expected['file'],
            'bytes': source.stat().st_size, 'sha256': sha(source), 'matches_hf_lfs_oid': True,
            'acquisition': 'Downloaded published BM25 candidates with real passage text; retrieval was not rerun.'},
        'qrel_source': {'official_url': f'https://trec.nist.gov/data/deep/{year}qrels-pass.txt',
            'download_url': 'https://mirror.ir-datasets.com/' + expected['qrels_md5'],
            'official_endpoint_observation': 'HTTP 403; used public IRDS mirror whose content matches its expected official-file MD5.',
            'sha256': sha(qrel_path), 'md5': expected['qrels_md5'], 'bytes': qrel_path.stat().st_size},
        'query_source': {'url': f'https://msmarco.z22.web.core.windows.net/msmarcoranking/msmarco-test{year}-queries.tsv.gz',
            'sha256_compressed': sha(query_path), 'md5_compressed': expected['queries_md5'],
            'official_unfiltered_query_count': len(official_queries), 'selected_query_texts_match_exactly': True},
        'ird_expected_checksums_source': {'revision': '99d81800b2819b89ed536e21455cb3a57050ab7b',
            'url': 'https://github.com/allenai/ir_datasets/blob/99d81800b2819b89ed536e21455cb3a57050ab7b/ir_datasets/etc/downloads.json',
            'sha256': sha(ROOT / 'sources/ird-downloads-pinned.json')},
        'license_and_reuse': {'msmarco_terms_url': 'https://microsoft.github.io/msmarco/',
            'terms_revision': '21b4ece9f4fc10fa4cec2028bb74287629945df6',
            'terms_sha256': sha(ROOT / 'sources/msmarco-terms-pinned.html'),
            'terms_summary': 'Intended for non-commercial research only. Made available without extending a license or underlying intellectual-property rights; Microsoft notes it may not own underlying document rights.',
            'hf_dataset_license_declaration': None,
            'code_license_does_not_relicense_passages': True,
            'raw_data_republication_authorized_or_performed': False,
            'local_use': 'Isolated research evaluation only; no training export, public repository payload, or Hugging Face upload.'},
        'author_alignment': {'commit': 'ac843ed63a302900d76722b83be926fdb84a3936',
            'prepare_script_sha256': sha(ROOT / 'sources/author-prepare-initial.sh'),
            'converter_sha256': sha(ROOT / 'sources/author-converter.py'),
            'same_candidate_repository_and_file_paths': True,
            'original_author_revision_was_pinned': False,
            'original_author_exact_file_bytes_known': False,
            'retrieval_parameters_evidence': 'Author prepare_data.sh and converter document pyserini msmarco-v1-passage BM25 k1=0.9 b=0.4. This preparation preserves downloaded ranks/scores, checks nonincreasing scores, and does not independently reconstruct the index or retrieval.',
            'query_selection': 'All and only judged query IDs; matches the author ir_datasets .../judged selection.',
            'preprocessing': 'Whitespace collapsed in candidate text exactly as author converter; official query strings unchanged. No token truncation applied in stored candidates.',
            'runtime_limits_not_applied_here': {'query_tokens': 32, 'passage_tokens': 128, 'encoding': 'cl100k_base', 'author_tiktoken_version': 'not pinned'},
            'provider_difference': 'Author used Vercel typesafe-ai/jev. No provider was called during preparation.'},
        'query_count': len(candidates), 'candidate_count': sum(len(row['documents']) for row in candidates),
        'unique_passages': len(unique_texts), 'qrel_count': sum(map(len, qrels.values())),
        'qrel_query_count': len(qrels), 'normalized_passage_occurrences': normalized_count,
        'synthetic_text_added': False, 'training_performed': False, 'model_evaluation_performed': False,
        'preparation_script_sha256': sha(__file__),
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    loaded = load_external_holdout(output / 'manifest.json')
    if loaded['missing_candidate_queries']:
        raise ValueError('A judged query is missing from candidates')
    # This is arithmetic on the downloaded BM25 run, not a new retrieval or model run.
    baseline = ndcg_at_k({qid: [doc['id'] for doc in row['documents']] for qid, row in loaded['queries'].items()}, loaded['qrels'], 10)
    verification = {'status': 'verified_external_inputs_only', 'benchmark': manifest['benchmark'],
        'queries': len(loaded['queries']), 'candidates': manifest['candidate_count'], 'qrels': manifest['qrel_count'],
        'missing_candidate_queries': loaded['missing_candidate_queries'], 'manifest_sha256': loaded['manifest_sha256'],
        'downloaded_bm25_ndcg_at_10': baseline, 'retrieval_rerun': False, 'model_evaluation_performed': False,
        'interpretation': 'Structural/hash/isolation checks and downloaded baseline arithmetic passed. No model/API ranking or reproduction of the original Jev result was performed.'}
    (output / 'verification.json').write_text(json.dumps(verification, ensure_ascii=False, indent=2) + '\n')
    return {key: verification[key] for key in ('status', 'benchmark', 'queries', 'candidates', 'qrels', 'manifest_sha256')} | {'downloaded_bm25_ndcg_at_10': baseline['value']}


if __name__ == '__main__':
    print(json.dumps([prepare(year) for year in EXPECTED], indent=2))
