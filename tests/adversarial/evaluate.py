#!/usr/bin/env python3
"""Score supplied routing observations; never runs a model or verifies its claims.

The frozen corpus is authored, not sampled production traffic. --responses must
say whether each observation is a manual policy review or an actual engine run.
A route match is NOT proof of demand validity, independent oracles, safe shipping,
or good product outcomes. No skill-text keyword check is a semantic guarantee.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys
import tempfile
from typing import Any

HERE = Path(__file__).resolve().parent
PATHS = {'feature-lifecycle','coding','planning','design','research','quality','operation','clarify','proposal'}
class EvaluationError(ValueError):
    pass

def load_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        return [json.loads(s) for s in path.read_text(encoding='utf-8').splitlines() if s.strip()]
    except (OSError, ValueError) as exc:
        raise EvaluationError(f'EVAL_INPUT: {path}: {exc}') from exc

def validate_cases(cases: list[dict[str, Any]]) -> None:
    if len(cases) < 80 or sum(c.get('boundary_ambiguous') is True for c in cases) < len(cases)/2:
        raise EvaluationError('EVAL_MINIMUM: >=80 requests and >=half boundary cases required')
    if len({c.get('id') for c in cases}) != len(cases):
        raise EvaluationError('EVAL_IDS: request IDs must be unique')
    required = {'id','request','expected_heavy','expected_path','reason','alternative_path','misrouting_cost','trigger_flags'}
    if any(not required <= c.keys() or c['expected_path'] not in PATHS or len(c['trigger_flags']) != 6 for c in cases):
        raise EvaluationError('EVAL_SCHEMA: incomplete request contract or six-factor encoding')

def check_freeze(root: Path) -> None:
    manifest = json.loads((root/'freeze.json').read_text())
    for name, digest in manifest['files'].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest() != digest:
            raise EvaluationError(f'EVAL_FREEZE: pre-change file changed: {name}')
    manifest = json.loads((root/'scenario-freeze.json').read_text())
    if hashlib.sha256((root/'scenarios.jsonl').read_bytes()).hexdigest() != manifest['sha256']:
        raise EvaluationError('EVAL_FREEZE: pre-change scenarios changed')

def matrix(cases: list[dict[str, Any]], values: dict[str, bool]) -> dict[str,int]:
    out = dict(TP=0, FP=0, FN=0, TN=0)
    for c in cases:
        pred, gold = values[c['id']], c['expected_heavy']
        out[('T' if pred == gold else 'F') + ('P' if pred else 'N')] += 1
    return out

def score(cases: list[dict[str, Any]], observations: list[dict[str, Any]]) -> dict[str,Any]:
    by_id = {o.get('id'):o for o in observations}
    if len(by_id) != len(observations) or set(by_id) != {c['id'] for c in cases}:
        raise EvaluationError('EVAL_IDS: observations must contain each request exactly once')
    failures=[]
    for c in cases:
        o=by_id[c['id']]
        if o.get('method') not in {'manual-policy-review','engine-execution'}:
            raise EvaluationError('EVAL_PROVENANCE: observations must name their method')
        if o['method']=='engine-execution' and not all(o.get(k) for k in ['engine','model','version','run_artifact']):
            raise EvaluationError('EVAL_PROVENANCE: engine execution needs engine/model/version/artifact; existence and truth still require review')
        if not isinstance(o.get('heavy_eligible'), bool) or o.get('path') not in PATHS:
            raise EvaluationError('EVAL_SCHEMA: observation must name path and Boolean eligibility')
        if o['heavy_eligible'] != c['expected_heavy'] or o['path'] != c['expected_path']:
            failures.append({'rule':'EVAL_ROUTE','id':c['id'],'expected':c['expected_path'],'got':o['path']})
        if c['id'] in {'R73','R74','R76'} and o.get('launch') not in {'proposal-only','not-lifecycle'}:
            failures.append({'rule':'EVAL_AUTH','id':c['id'],'reason':'no grant for lifecycle launch'})
        if c['id'] in {'R75','R78'} and o.get('extra_routine_approvals') != 0:
            failures.append({'rule':'EVAL_AUTH','id':c['id'],'reason':'complete grant must not add routine approval'})
    return {'method_counts':dict(Counter(o['method'] for o in observations)),
            'confusion_matrix':matrix(cases,{k:v['heavy_eligible'] for k,v in by_id.items()}),
            'failures':failures,'scope':'Structured routing/authorization scoring only. Not an executed-agent or product-safety guarantee.'}

def selftest(cases: list[dict[str,Any]]) -> None:
    tests=0
    def broken(name: str, fn: Any) -> None:
        nonlocal tests
        try: fn()
        except EvaluationError as exc:
            if name not in str(exc):raise AssertionError(f'{name}: masked by {exc}')
            print(f'PASS {name}: intentional mutation named');tests+=1
        else: raise AssertionError(f'{name}: mutation did not fail')
    validate_cases(cases)
    broken('EVAL_MINIMUM',lambda:validate_cases(cases[:79]))
    dup=copy.deepcopy(cases);dup[1]['id']=dup[0]['id'];broken('EVAL_IDS',lambda:validate_cases(dup))
    bad=copy.deepcopy(cases);bad[0].pop('reason');broken('EVAL_SCHEMA',lambda:validate_cases(bad))
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        for name in ['requests.jsonl','predictions.md','freeze.json','scenarios.jsonl','scenario-freeze.json']:
            (root/name).write_bytes((HERE/name).read_bytes())
        check_freeze(root)
        with (root/'predictions.md').open('a') as f:f.write('\nmutation\n')
        broken('EVAL_FREEZE',lambda:check_freeze(root))
    # A constructed all-matching response is only a grader unit fixture, NOT an agent result.
    obs=[dict(id=c['id'],heavy_eligible=c['expected_heavy'],path=c['expected_path'],
              method='manual-policy-review',launch='proposal-only' if c['expected_path']=='proposal' else 'not-lifecycle',extra_routine_approvals=0) for c in cases]
    assert not score(cases,obs)['failures']
    bad=copy.deepcopy(obs);bad[0].pop('method');broken('EVAL_PROVENANCE',lambda:score(cases,bad))
    bad=copy.deepcopy(obs);bad[0].update(method='engine-execution');broken('EVAL_PROVENANCE',lambda:score(cases,bad))
    for rid,field,value,rule in [('R09','heavy_eligible',False,'EVAL_ROUTE'),('R73','launch','execute','EVAL_AUTH'),('R75','extra_routine_approvals',1,'EVAL_AUTH')]:
        bad=copy.deepcopy(obs);next(o for o in bad if o['id']==rid)[field]=value
        assert any(f['rule']==rule and f['id']==rid for f in score(cases,bad)['failures']),rule
        print(f'PASS {rule}: intentional {rid} mutation named');tests+=1
    print(f'{tests}/{tests} grader mutation tests passed; no engine was executed')

def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--responses',type=Path)
    p.add_argument('--export-prompts',type=Path,help='Export requests WITHOUT golden labels for a separately configured runner')
    p.add_argument('--selftest',action='store_true')
    args=p.parse_args()
    try:
        check_freeze(HERE);cases=load_jsonl(HERE/'requests.jsonl');validate_cases(cases)
        if args.selftest:selftest(cases)
        if args.export_prompts:
            args.export_prompts.write_text(''.join(json.dumps({'id':c['id'],'request':c['request']},ensure_ascii=False)+'\n' for c in cases),encoding='utf-8')
        if args.responses:
            result=score(cases,load_jsonl(args.responses));print(json.dumps(result,ensure_ascii=False,indent=2));return bool(result['failures'])
        print('Frozen 80-request corpus and scenario hashes verified. No model/CLI was run.')
        return 0
    except (EvaluationError,OSError,ValueError) as exc:
        print(str(exc),file=sys.stderr);return 1
if __name__=='__main__':raise SystemExit(main())
