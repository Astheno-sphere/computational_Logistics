"""Prove a context bound for every adaptive window of the frozen TREC input.

This finite-corpus proof checks the actual pinned NFC normalizer, all escaped
passage/query strings, byte-level BPE, added tokens, and the reviewed single-user
chat-template branch. It loads tokenizers only; networking and CUDA are disabled.
An unsupported condition produces a failure report, never an assumed bound.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--code-root', type=Path, required=True)
    parser.add_argument('--cache', type=Path, default=Path('/mnt/localssd/open-jev/hf-cache'))
    parser.add_argument('--probe-sha256', help='Required only when executing this source through stdin')
    parser.add_argument('--prior-failure-report', type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), 'Refuse to overwrite context-bound evidence')
    if Path(__file__).is_file():
        actual_source = sha(Path(__file__).read_bytes())
        require(args.probe_sha256 in (None, actual_source), 'Probe source hash differs')
        args.probe_sha256 = actual_source
    require(isinstance(args.probe_sha256, str) and len(args.probe_sha256) == 64, 'Missing exact probe source hash')
    os.environ.update(CUDA_VISIBLE_DEVICES='', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
                      HF_HUB_CACHE=str(args.cache), TOKENIZERS_PARALLELISM='false')

    def deny_network(event, event_args):
        if event in {'socket.connect', 'socket.getaddrinfo', 'socket.bind'}:
            raise RuntimeError('Network operation prohibited during tokenizer-only preflight')
    sys.addaudithook(deny_network)
    sys.path.insert(0, str(args.code_root))
    from jev import api, ir_eval
    from scripts import evaluate_trec_provider as loader
    from transformers import AutoTokenizer
    from tokenizers.pre_tokenizers import ByteLevel
    import tokenizers
    import transformers

    expected_input = 'cc7bc949dbc269dacb61bdb61fc8982db14bc4df3698f9d32f5f1c8b6795eb83'
    document, raw = loader.load_input(args.input, expected_input)
    max_length = 16384
    report = {'schema_version': 1, 'status': 'preparing', 'created_at': datetime.now(timezone.utc).isoformat(),
              'input_sha256': sha(raw), 'protocol': loader.PROTOCOL, 'queries': len(document['queries']),
              'max_length': max_length, 'model_weights_loaded': False, 'gpu_allocations': 0,
              'network_calls': 0, 'local_files_only': True, 'qrels_read': False,
              'source_sha256': {'probe': args.probe_sha256,
                                'input_loader': sha(Path(loader.__file__).read_bytes()),
                                'ir_eval': sha(Path(ir_eval.__file__).read_bytes()),
                                'api': sha(Path(api.__file__).read_bytes())},
              'versions': {'transformers': transformers.__version__, 'tokenizers': tokenizers.__version__},
              'bound_rule': 'All9700 JSON-escaped passages, all97 escaped queries and the empty/static candidate frames must be stable under the actual NFC normalizer. ASCII JSON quotes and separators isolate these pieces under any20-passage permutation. Choose the20 largest escaped UTF8 passage strings per query and compile all80Score candidates; a reviewed fixed ASCII chat envelope adds constant bytes. Nonempty ASCII unnormalized added tokens consume at least one byte each; extraction partitions NFC-stable substrings. One terminal ByteLevel stage, complete256-symbol byte alphabet and BPE without affixes or fallback yield at most one token per byte; merges only reduce count. The ByteLevel postprocessor preserves the sequence. Bound includes num_special_tokens_to_add.',
              'models': {}}
    if args.prior_failure_report:
        prior_raw = args.prior_failure_report.read_bytes()
        prior = json.loads(prior_raw)
        require(prior['status'] == 'bound_not_established' and prior['input_sha256'] == expected_input,
                'Prior failure does not belong to this frozen input')
        report['prior_attempt'] = {'status': prior['status'], 'report_sha256': sha(prior_raw),
                                  'probe_sha256': prior['source_sha256']['probe'],
                                  'error_type': prior.get('error_type'), 'error': prior.get('error'),
                                  'diagnosis': 'The initial sufficient proof required normalizer=None; actual pinned tokenizers use NFC. That proof was refused. This revised proof checks stability of every frozen text piece under the actual NFC normalizer.'}
    selections = []
    for query in document['queries']:
        measured = [(len(json.dumps(doc['text'], ensure_ascii=False).encode()), index, doc)
                    for index, doc in enumerate(query['documents'])]
        chosen = sorted(measured, key=lambda row: (-row[0], row[1]))[:20]
        request = ir_eval._request(query['query'], [row[2]['text'] for row in chosen], 'listwise_score', 'general-ir-v1')
        empty_request = ir_eval._request(query['query'], [''] * 20, 'listwise_score', 'general-ir-v1')
        rows = api.compile_request(request['state'], request['questions'])
        empty_rows = api.compile_request(empty_request['state'], empty_request['questions'])
        prompts = [prompt for row in rows for prompt in api.candidate_prompts(row)]
        empty_prompts = [prompt for row in empty_rows for prompt in api.candidate_prompts(row)]
        require(len(rows) == 20 and len(prompts) == len(empty_prompts) == 80, 'Expected20heads and80candidate prompts')
        delta = sum(row[0] for row in chosen) - 40
        require(all(len(prompt.encode()) - len(empty.encode()) == delta
                    for prompt, empty in zip(prompts, empty_prompts)), 'Candidate serialization is not additive in escaped passage bytes')
        selections.append((query, prompts, empty_prompts, delta))

    try:
        for tag, model, revision, template_sha in (
                ('2b', 'Qwen/Qwen3.5-2B', '15852e8c16360a2fea060d615a32b45270f8a8fc',
                 '273d8e0e683b885071fb17e08d71e5f2a5ddfb5309756181681de4f5a1822d80'),
                ('9b', 'Qwen/Qwen3.5-9B', 'c202236235762e1c871ad0ccb60c8ee5ba337b9a',
                 'a4aee8afcf2e0711942cf848899be66016f8d14a889ff9ede07bca099c28f715')):
            snapshot = args.cache / ('models--' + model.replace('/', '--')) / 'snapshots' / revision
            require(snapshot.is_dir(), 'Pinned tokenizer snapshot is not available locally: ' + tag)
            files = {name: sha((snapshot / name).read_bytes()) for name in (
                'config.json', 'tokenizer.json', 'tokenizer_config.json', 'chat_template.jinja')}
            tokenizer = AutoTokenizer.from_pretrained(str(snapshot), local_files_only=True, use_fast=True, token=False)
            require(tokenizer.is_fast, 'A fast BPE tokenizer is required')
            backend = json.loads(tokenizer.backend_tokenizer.to_str())
            require(files['chat_template.jinja'] == template_sha and isinstance(tokenizer.chat_template, str)
                    and sha(tokenizer.chat_template.encode()) == template_sha, 'Effective chat template differs from reviewed source')
            require(files['tokenizer.json'] == '5f9e4d4901a92b997e463c1f46055088b6cca5ca61a6522d1b9f64c4bb81cb42',
                    'Frozen tokenizer definition differs')
            normalizer = tokenizer.backend_tokenizer.normalizer
            require(backend.get('normalizer') == {'type': 'NFC'} and normalizer is not None,
                    'Only the pinned NFC normalizer is supported by this finite-corpus proof')
            pieces = [(query['benchmark'], query['id'], doc['id'], json.dumps(doc['text'], ensure_ascii=False))
                      for query in document['queries'] for doc in query['documents']]
            changed_passages = [(benchmark, qid, did) for benchmark, qid, did, text in pieces
                                if normalizer.normalize_str(text) != text]
            changed_queries = [(query['benchmark'], query['id']) for query in document['queries']
                               if normalizer.normalize_str(json.dumps(query['query'], ensure_ascii=False))
                               != json.dumps(query['query'], ensure_ascii=False)]

            def flatten(stage):
                if stage.get('type') == 'Sequence':
                    return [child for entry in stage['pretokenizers'] for child in flatten(entry)]
                return [stage]
            stages = flatten(backend['pre_tokenizer'])
            model_config = backend['model']
            alphabet = set(ByteLevel.alphabet())
            conditions = {'normalizer_is_pinned_nfc': backend.get('normalizer') == {'type': 'NFC'},
                          'all_frozen_passage_strings_nfc_stable': not changed_passages,
                          'all_frozen_query_strings_nfc_stable': not changed_queries,
                          'bpe_model': model_config.get('type') == 'BPE',
                          'no_continuing_subword_prefix': model_config.get('continuing_subword_prefix') in (None, ''),
                          'no_end_of_word_suffix': model_config.get('end_of_word_suffix') in (None, ''),
                          'no_byte_fallback': model_config.get('byte_fallback') is False,
                          'one_terminal_bytelevel': bool(stages) and stages[-1].get('type') == 'ByteLevel'
                              and sum(stage.get('type') == 'ByteLevel' for stage in stages) == 1,
                          'only_split_before_bytelevel': all(stage.get('type') == 'Split' for stage in stages[:-1]),
                          'bytelevel_no_added_prefix_space': all(stage.get('add_prefix_space') is False
                              for stage in stages if stage.get('type') == 'ByteLevel'),
                          'all256_byte_symbols_in_vocab': len(alphabet) == 256 and alphabet <= set(model_config['vocab']),
                          'added_tokens_consume_nonempty_text': all(isinstance(token.get('content'), str) and token['content']
                              for token in backend.get('added_tokens', [])),
                          'added_tokens_ascii_unnormalized_unstripped': all(token['content'].isascii() and
                              token.get('normalized') is False and token.get('lstrip') is False and token.get('rstrip') is False
                              for token in backend.get('added_tokens', [])),
                          'postprocessor_preserves_token_sequence': backend.get('post_processor') is None
                              or backend['post_processor'].get('type') == 'ByteLevel'}
            report['models'][tag] = {'model': model, 'revision': revision, 'tokenizer_files_sha256': files,
                                    'conditions': conditions, 'normalizer': backend['normalizer'],
                                    'nfc_checked_passages': len(pieces), 'nfc_checked_queries': len(document['queries']),
                                    'changed_passage_identities': changed_passages, 'changed_query_identities': changed_queries,
                                    'added_token_count': len(backend.get('added_tokens', [])),
                                    'effective_chat_template_sha256': template_sha}
            require(all(conditions.values()), 'Tokenizer byte-bound conditions are unsupported: ' + tag)
            specials = tokenizer.num_special_tokens_to_add(pair=False)
            require(type(specials) is int and specials >= 0, 'Invalid postprocessor special-token count')
            results, actual_inputs, envelope = [], [], None
            for query, prompts, empty_prompts, delta in selections:
                # These guards select the reviewed single-user template branch:
                # |trim is a no-op and the tool-response content branch cannot run.
                require(all(prompt.startswith('Context:\n') and prompt.endswith('Answer Yes or No.')
                            for prompt in prompts + empty_prompts), 'Candidate prompt framing differs')
                rendered = [tokenizer.apply_chat_template([{'role': 'user', 'content': prompt}], tokenize=False,
                            add_generation_prompt=True, enable_thinking=False) for prompt in prompts]
                empty_rendered = [tokenizer.apply_chat_template([{'role': 'user', 'content': prompt}], tokenize=False,
                                  add_generation_prompt=True, enable_thinking=False) for prompt in empty_prompts]
                for prompt, text in zip(prompts + empty_prompts, rendered + empty_rendered):
                    require(text.count(prompt) == 1, 'Chat template does not insert user content exactly once')
                    before, after = text.split(prompt)
                    if envelope is None:
                        envelope = (before, after)
                    require((before, after) == envelope, 'Single-user chat template envelope depends on request content')
                    require(before.isascii() and after.isascii(), 'Chat envelope must be ASCII for the NFC boundary proof')
                    require(normalizer.normalize_str(text) == text, 'Static or rendered candidate is not NFC-stable')
                require(all(len(text.encode()) - len(empty.encode()) == delta
                            for text, empty in zip(rendered, empty_rendered)), 'Chat rendering violates additive byte bound')
                index = max(range(80), key=lambda i: len(rendered[i].encode()))
                size = len(rendered[index].encode())
                actual_inputs.append(rendered[index])
                results.append({'benchmark': query['benchmark'], 'query_id': query['id'],
                                'candidate_prompts_checked': 80, 'max_rendered_utf8_bytes': size,
                                'token_upper_bound': size + specials})
            encoded = tokenizer(actual_inputs, padding=False, truncation=False, add_special_tokens=True)['input_ids']
            require(len(encoded) == len(results), 'Tokenizer result count differs')
            for row, tokens in zip(results, encoded):
                require(len(tokens) <= row['token_upper_bound'], 'Actual tokenization exceeds proposed byte bound')
                row['actual_tokens_for_max_byte_candidate'] = len(tokens)
            report['models'][tag].update({
                'backend_tokenizer_sha256': sha(tokenizer.backend_tokenizer.to_str().encode()),
                'conditions': conditions, 'pretokenizer_types': [stage['type'] for stage in stages],
                'postprocessor_type': (backend.get('post_processor') or {}).get('type'),
                'added_special_tokens': specials, 'fixed_chat_envelope_utf8_bytes': sum(len(text.encode()) for text in envelope),
                'fixed_chat_envelope_verified': True, 'serialized_byte_additivity_verified': True,
                'rendered_candidate_prompts': 80 * len(results), 'query_bounds': results,
                'max_token_upper_bound': max(row['token_upper_bound'] for row in results),
                'max_actual_tokens_for_checked_candidates': max(map(len, encoded)),
                'all_adaptive20_windows_fit': all(row['token_upper_bound'] <= max_length for row in results)})
        report['status'] = ('verified_all_adaptive_windows_fit' if all(row['all_adaptive20_windows_fit'] for row in report['models'].values())
                            else 'verified_bound_exceeds_context_limit')
    except Exception as error:
        report.update(status='bound_not_established', error_type=type(error).__name__, error=str(error))
        raise
    finally:
        with args.output.open('x') as stream:
            stream.write(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'status': report['status'], 'models': {key: {name: row[name] for name in (
        'max_token_upper_bound', 'max_actual_tokens_for_checked_candidates', 'all_adaptive20_windows_fit')}
        for key, row in report['models'].items()}, 'output_sha256': sha(args.output.read_bytes())}))


if __name__ == '__main__':
    main()
