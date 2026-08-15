#!/usr/bin/env python3
from pathlib import Path
import json, re, subprocess, sys, tempfile, os
ROOT=Path(__file__).resolve().parents[1]

def fail(msg):
    print('FAIL:',msg); raise SystemExit(1)

# 1. JSON files parse.
for p in ROOT.rglob('*.json'):
    try: json.loads(p.read_text(encoding='utf-8'))
    except Exception as e: fail(f'JSON parse {p.relative_to(ROOT)}: {e}')

# 2. Markdown fences are balanced.
for p in list((ROOT/'docs').glob('*.md'))+list((ROOT/'agents').glob('*.md'))+[ROOT/'README.md']:
    text=p.read_text(encoding='utf-8')
    if text.count('```') % 2: fail(f'unbalanced code fences: {p.relative_to(ROOT)}')

# 3. Normative math docs have ASCII text blocks.
for rel in ['README.md','docs/legacy/01_ZME_V0.2_ENGINEERING_SPEC.md','docs/legacy/05_ZME_B001_HISTORICAL_MASS_PREDICTION.md','docs/08_MATH_READABILITY_STANDARD.md']:
    text=(ROOT/rel).read_text(encoding='utf-8')
    blocks=re.findall(r'```text\n(.*?)```',text,re.S)
    if not blocks: fail(f'no ASCII text blocks in {rel}')
    for b in blocks:
        try: b.encode('ascii')
        except UnicodeEncodeError as e: fail(f'non-ASCII normative block in {rel}: {e}')

# 4. Task instruction paths exist.
man=json.loads((ROOT/'agents/task_manifest.json').read_text())
for t in man['tasks']:
    if not (ROOT/t['instruction_file']).exists(): fail(f"missing task file {t['instruction_file']}")

# 5. Run scaffold tests using source trees directly.
env=dict(os.environ)
env['PYTHONPATH']=os.pathsep.join([str(ROOT/'scaffold/physics-evidence-core/src'),str(ROOT/'scaffold/zero-mass-element/src'),env.get('PYTHONPATH','')])
for project in ['scaffold/physics-evidence-core','scaffold/zero-mass-element']:
    proc=subprocess.run([sys.executable,'-m','pytest','-q'],cwd=ROOT/project,env=env,text=True,capture_output=True)
    if proc.returncode:
        print(proc.stdout); print(proc.stderr); fail(f'tests failed: {project}')

# 6. Ensure unknown-territory production command is absent.
cli=(ROOT/'scaffold/zero-mass-element/src/zero_mass_element/cli.py').read_text()
if '154' in cli or 'hyperheavy' in cli.lower(): fail('unknown-territory command found in v0.2 CLI')
print('BUNDLE_VALIDATION: PASS')
