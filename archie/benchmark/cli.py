# archie/benchmark/cli.py
import argparse
import sys
from pathlib import Path

from .config import load_config, parse_config
from .orchestrator import run_benchmark, prepare_branches


def _print_summary(result):
    agg = result["aggregate"]
    print("\n=== Benchmark summary ===")
    for arm in ("treatment", "control"):
        a = agg[arm]
        print(f"[{arm}] n={a['n']} attempted={a['attempted_n']} completed={a['completed_n']} "
              f"cost=${_fmt(a['cost_usd_mean'])} tools={_fmt(a['tool_calls_mean'])} "
              f"dur={_fmt(a['duration_ms_mean'])}ms quality={_fmt(a['quality_mean'])}")
    s = agg["savings"]
    print(f"[savings] cost={_fmt(s['cost_pct'])}%  tools={_fmt(s['tool_calls_pct'])}%  "
          f"time={_fmt(s['duration_pct'])}%")
    print(f"[store] {result['store']}")


def _fmt(v):
    return "n/a" if v is None else (f"{v:.2f}" if isinstance(v, float) else str(v))


def _cmd_run(args):
    cfg = load_config(args.config)
    result = run_benchmark(cfg)
    _print_summary(result)


def _cmd_prep(args):
    cfg = load_config(args.config)
    status = prepare_branches(cfg)
    if status["needs_deep_scan"]:
        _interactive_deep_scan(cfg)
    print(f"Branches ready: {cfg.branches}")


def _cmd_auto(args):
    if args.config:
        cfg = load_config(args.config)
    else:
        cfg = parse_config({"name": Path(args.repo).name, "repo": args.repo,
                            "task_prompt": args.prompt, "model": args.model})
    status = prepare_branches(cfg)
    if status["needs_deep_scan"]:
        _interactive_deep_scan(cfg)
    result = run_benchmark(cfg)
    _print_summary(result)


def _interactive_deep_scan(cfg):
    treatment = cfg.branches["treatment"]
    print("\n" + "=" * 70)
    print("Archie not found in this repo. Semi-automatic prep:")
    print(f"  1. In a terminal: git checkout {treatment}")
    print(f"  2. Install Archie:  npx @bitraptors/archie {cfg.repo}")
    print("  3. In Claude Code on that branch, run:  /archie-deep-scan")
    print("  4. Commit the generated files.")
    print("This deep-scan is NOT counted in the benchmark metrics.")
    print("=" * 70)
    input("Press Enter once the treatment branch has committed Archie files... ")
    # verify
    from .orchestrator import _git_out, _archie_present  # local import to avoid cycle noise
    current = _git_out(["rev-parse", "--abbrev-ref", "HEAD"], cfg.repo)
    _git_out(["checkout", treatment], cfg.repo)
    present = _archie_present(cfg.repo)
    _git_out(["checkout", current], cfg.repo)
    if not present:
        print("ERROR: no Archie files found on the treatment branch. Aborting.", file=sys.stderr)
        sys.exit(1)


def _cmd_verify(args):
    from .store import verify
    result = verify()
    for name, ok, detail in result["checks"]:
        mark = "OK " if ok else "FAIL"
        print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))
    if result["ok"]:
        print("Supabase store ready — benchmark runs will be stored online.")
    else:
        print("Supabase store NOT ready — runs would fall back to offline JSON.",
              file=sys.stderr)
        sys.exit(1)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="archie-benchmark",
                                     description="Measure Archie effectiveness (control vs treatment).")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run benchmark on existing branches")
    p_run.add_argument("config", help="path to benchmark config JSON")
    p_run.set_defaults(func=_cmd_run)

    p_prep = sub.add_parser("prep", help="create/refresh benchmark branches only")
    p_prep.add_argument("config", help="path to benchmark config JSON")
    p_prep.set_defaults(func=_cmd_prep)

    p_auto = sub.add_parser("auto", help="prep branches then run, from a plain repo")
    p_auto.add_argument("repo", nargs="?", help="repo path (when no --config)")
    p_auto.add_argument("--config", help="path to benchmark config JSON")
    p_auto.add_argument("--prompt", help="task prompt (when no --config)")
    p_auto.add_argument("--model", default="claude-sonnet-4-6")
    p_auto.set_defaults(func=_cmd_auto)

    p_verify = sub.add_parser("verify", help="self-test the Supabase store connection")
    p_verify.set_defaults(func=_cmd_verify)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
