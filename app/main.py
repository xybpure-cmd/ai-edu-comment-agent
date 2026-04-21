from __future__ import annotations
import argparse,json
from app.config import ensure_directories
from app.services import build_comment_pack,build_news_item,evaluate_candidate,export_outputs,run_scan,run_weekly_review

def cmd_scan(_:argparse.Namespace)->None:
    r=run_scan(); print(f"scan complete: brief={r['brief']} candidates={r['candidates']} topics={r['topics']} dashboard={r['dashboard']} items={r['count']}")
def cmd_evaluate(args:argparse.Namespace)->None:
    c=evaluate_candidate(build_news_item(args.input)); print(json.dumps(c.__dict__,ensure_ascii=False,indent=2))
def cmd_build(args:argparse.Namespace)->None:
    n=build_news_item(args.input); c=evaluate_candidate(n); p=build_comment_pack(n,c); export_outputs(p); print(f"Built comment pack: {p.id} status={p.status}")
def cmd_trigger(args:argparse.Namespace)->None: print(f"trigger: major event workflow placeholder for keyword={args.keyword}")
def cmd_weekly(_:argparse.Namespace)->None: print(f"weekly review generated: {run_weekly_review()}")

def build_parser()->argparse.ArgumentParser:
    p=argparse.ArgumentParser(prog='ai-edu-comment-agent'); s=p.add_subparsers(dest='command',required=True)
    s.add_parser('scan').set_defaults(func=cmd_scan)
    e=s.add_parser('evaluate'); e.add_argument('input'); e.set_defaults(func=cmd_evaluate)
    b=s.add_parser('build'); b.add_argument('input'); b.set_defaults(func=cmd_build)
    t=s.add_parser('trigger'); t.add_argument('keyword'); t.set_defaults(func=cmd_trigger)
    s.add_parser('weekly').set_defaults(func=cmd_weekly)
    return p

def main()->None:
    ensure_directories(); a=build_parser().parse_args(); a.func(a)
if __name__=='__main__': main()
