from __future__ import annotations
import argparse, json
from .benchmark.b001 import run_b001, prepare_discovery_target_manifest

def main(argv=None):
    p=argparse.ArgumentParser(prog='zme')
    sub=p.add_subparsers(dest='cmd',required=True)
    prep=sub.add_parser('b001-prepare-targets'); prep.add_argument('--old',required=True); prep.add_argument('--later',required=True); prep.add_argument('--out',required=True)
    b=sub.add_parser('b001'); b.add_argument('--old',required=True); b.add_argument('--targets',required=True); b.add_argument('--later',required=True); b.add_argument('--out',required=True); b.add_argument('--seed',type=int,default=0)
    a=p.parse_args(argv)
    if a.cmd=='b001-prepare-targets': print(json.dumps(prepare_discovery_target_manifest(a.old,a.later,a.out),indent=2,sort_keys=True))
    elif a.cmd=='b001': print(json.dumps(run_b001(a.old,a.targets,a.later,a.out,a.seed),indent=2,sort_keys=True))
