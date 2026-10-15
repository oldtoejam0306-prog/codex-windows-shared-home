"""Audits are read-only; snapshot/config writes require --apply and stopped Codex."""
import argparse
import json
import os
from pathlib import Path
import sys
import tomllib
from .core import active_codex_processes, audit_home, load_settings, snapshot_core, sql_path_plan, ordinary_directory, reparse
from .configuration import prepare_config, dump_toml

def under(path, root):
    return path.resolve().is_relative_to(root.resolve())

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", required=True, type=Path)
    sub = parser.add_subparsers(dest="action", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--home", required=True, type=Path)
    snapshot = sub.add_parser("snapshot")
    snapshot.add_argument("--home", required=True, type=Path)
    snapshot.add_argument("--output", required=True, type=Path)
    snapshot.add_argument("--apply", action="store_true")
    plan = sub.add_parser("plan-paths")
    plan.add_argument("--home", required=True, type=Path)
    config = sub.add_parser("prepare-config")
    config.add_argument("--profile", required=True)
    config.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    cfg = load_settings(args.settings)
    shared_root = Path(cfg["shared_root"])
    if args.action == "audit":
        print(json.dumps(audit_home(args.home), ensure_ascii=False, indent=2))
    elif args.action == "plan-paths":
        print(json.dumps(sql_path_plan(args.home, cfg.get("path_mappings", [])), ensure_ascii=False, indent=2))
    elif args.action == "snapshot":
        sources = {Path(p["source_home"]).resolve() for p in cfg["participants"]}
        if args.home.resolve() not in sources:
            raise ValueError("Snapshot source must be explicitly configured")
        if not under(args.output, shared_root / "snapshots"):
            raise ValueError("Output must stay under shared_root/snapshots")
        if any(under(args.output, src) or under(src, args.output) for src in sources):
            raise ValueError("Snapshot and source trees must be separate")
        if not args.apply:
            print(json.dumps({"result": "DRY_RUN", "summary": audit_home(args.home)}))
            return
        if active_codex_processes():
            raise RuntimeError("Close Codex in ALL Windows sessions")
        report = snapshot_core(args.home, args.output)
        if active_codex_processes():
            raise RuntimeError("Codex started during snapshot; do not accept output")
        report["result"] = "CORE_SNAPSHOT_READY_NOT_ACTIVATED"
        (args.output.parent / (args.output.name + ".report.json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({"result": report["result"], "files": len(report["files"])}))
    elif args.action == "prepare-config":
        if args.profile not in {p["profile"] for p in cfg["participants"]}:
            raise ValueError("Unknown participant")
        home = shared_root / "home"
        for directory in (home, *home.parents):
            ordinary_directory(directory)
        if not (home / "SHARED-HOME-READY.json").is_file():
            raise ValueError("Reviewed shared-home marker missing")
        path = home / "config.toml"
        if reparse(path):
            raise ValueError("Config must not be a redirected file")
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        prepared = prepare_config(data, cfg, args.profile)
        if args.apply:
            if active_codex_processes():
                raise RuntimeError("Close Codex in ALL Windows sessions")
            temp = path.with_name("config.toml.shared-home.tmp")
            with temp.open("x", encoding="utf-8") as f:
                f.write(dump_toml(prepared))
            os.replace(temp, path)
        print(json.dumps({"result": "CONFIG_PREPARED" if args.apply else "CONFIG_DRY_RUN_PASS",
                          "sandbox_mode_unchanged": data.get("sandbox_mode") == prepared.get("sandbox_mode")}))
if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"result": "STOPPED", "error": str(error)}), file=sys.stderr)
        sys.exit(1)
