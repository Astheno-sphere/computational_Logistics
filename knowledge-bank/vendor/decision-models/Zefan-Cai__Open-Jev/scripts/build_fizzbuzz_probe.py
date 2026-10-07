"""Freeze an original 1..100 FizzBuzz probe; no upstream prompt is assumed."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from jev.api import compile_request
from scripts.benchmark_inference_latency import digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    base = json.loads((Path(__file__).resolve().parents[1]/'configs/probes/fizzbuzz.json').read_text())
    workloads, golds = [], []
    for n in range(1, 101):
        request = copy.deepcopy(base)
        request['state']['integer'] = n
        wid = f'fizzbuzz-{n:03d}'
        workloads.append({'id':wid, 'kind':'original_arithmetic_control', 'request':request,
                          'request_sha256':digest(request)})
        for record in compile_request(request['state'], request['questions']):
            if record['id'] == 'divisible_by_three':
                target = int(n % 3 == 0)
            elif record['id'] == 'divisible_by_five':
                target = int(n % 5 == 0)
            else:
                label = 'fizzbuzz' if n % 15 == 0 else 'fizz' if n % 3 == 0 else 'buzz' if n % 5 == 0 else 'number'
                target = record['answer_keys'].index(label)
            golds.append({'request_id':wid, 'question_id':record['id'], 'kind':record['kind'],
                          'target':target, 'answer_keys':record['answer_keys'],
                          'source':'arithmetic-fizzbuzz-control-v1', 'split':'evaluation_only',
                          'group_id':str(n), 'request_sha256':digest(request)})
    for name, value in [('requests.json', {'schema_version':1, 'workloads':workloads}),
                        ('gold.json', {'schema_version':1, 'rows':golds})]:
        (args.output/name).write_text(json.dumps(value, indent=2)+'\n')
    manifest = {'schema_version':1, 'license':'CC0-1.0', 'requests':100, 'typed_decisions':300,
                'source_lead':'https://x.com/aaronbatilo/status/2101795933465772520',
                'scope':'Original independently specified FizzBuzz probe; not reproduction of the undisclosed upstream prompt or its 10000-repeat result. Evaluation only; no training data modified.',
                'integers':'Every integer1..100, inclusive; no filtering by model outcomes.',
                'gold_rule':'Exact integer divisibility; Noul is P(yes), threshold0.5; ties use first category.',
                'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in args.output.iterdir()}}
    (args.output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({'requests':len(workloads), 'typed_decisions':len(golds), 'output':str(args.output)}))


if __name__ == '__main__':
    main()
