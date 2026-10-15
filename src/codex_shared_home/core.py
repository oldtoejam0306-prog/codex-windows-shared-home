"""Local-only data primitives. No credential reads or hosted API requests."""
from __future__ import annotations
import copy
import hashlib
import json
import ntpath
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess

CORE_DIRS = {
    "sessions", "archived_sessions", "attachments", "automations", "memories",
    "memories_v2", "skills", "plugins", "rules", "visualizations", "vendor_imports",
    "rollout-migrations", "sqlite",
}
CORE_FILES = {"AGENTS.md", "config.toml", ".codex-global-state.json",
              ".codex-global-state.json.bak", "session_index.jsonl", "history.jsonl"}
PRIVATE_NAMES = {
    "auth.json", "secrets", ".sandbox", ".sandbox-secrets", ".sandbox-bin",
    "cookies", "login data", "web data", "credentials", "credential", "local state",
    ".git-credentials", ".npmrc", ".pypirc", ".netrc", ".ssh", ".aws", ".azure",
    ".kube", "id_rsa", "id_ed25519", "application_default_credentials.json", ".env",
    "mcp-oauth-locks",
}
PROCESS_NAMES = {
    "chatgpt.exe", "codex.exe", "codex-code-mode-host.exe", "node_repl.exe",
    "codex-computer-use.exe", "codex-computer-use-swift.exe",
    "codex-windows-sandbox.exe", "codex-windows-sandbox-setup.exe",
}

def private_name(name):
    n = name.lower()
    return n in PRIVATE_NAMES or n.startswith(".env.") or n.endswith((".age", ".pem", ".key", ".pfx", ".p12"))

def reparse(path):
    return path.is_symlink() or bool(getattr(path.lstat(), "st_file_attributes", 0) & 0x400)

def ordinary_directory(path):
    if not path.is_dir() or reparse(path):
        raise ValueError("Missing or redirected directory")

def load_settings(path):
    cfg = json.loads(path.read_text(encoding="utf-8"))
    root = cfg.get("shared_root", "")
    if not ntpath.isabs(root) or not re.fullmatch(r"[A-Za-z]:", ntpath.splitdrive(root)[0]) or ntpath.splitdrive(root)[1] in ("\\", "/"):
        raise ValueError("shared_root must be an explicit non-root absolute Windows directory")
    people = cfg.get("participants", [])
    if len(people) < 2 or len({p["sid"] for p in people}) != len(people):
        raise ValueError("Configure at least two distinct Windows SIDs")
    for p in people:
        if not re.fullmatch(r"S-1-5-21-\d+-\d+-\d+-\d+", p["sid"]):
            raise ValueError("Invalid SID")
        if not ntpath.isabs(p["profile"]) or not ntpath.isabs(p["source_home"]):
            raise ValueError("Participant paths must be absolute")
    rel = cfg.get("private_relative", r"CodexShared\home-v1")
    if ntpath.isabs(rel) or ".." in rel.replace("/", "\\").split("\\"):
        raise ValueError("private_relative escapes Local AppData")
    cfg["private_relative"] = rel
    return cfg

def normal(path):
    raw = path[4:] if path.startswith("\\\\?\\") else path
    return ntpath.normcase(ntpath.normpath(raw))

def within(path, root):
    return normal(path) == normal(root) or normal(path).startswith(normal(root).rstrip("\\") + "\\")

def map_path(path, mappings, lexical=False):
    """Whole typed paths and component boundaries; never arbitrary text."""
    if not path:
        return path
    matches = [m for m in mappings if within(path, m["source"])]
    if not matches:
        return path
    m = max(matches, key=lambda v: len(normal(v["source"])))
    raw = path[4:] if path.startswith("\\\\?\\") else path
    src = m["source"][4:] if m["source"].startswith("\\\\?\\") else m["source"]
    dest = m.get("identity_destination", m["destination"]) if lexical else m["destination"]
    result = ntpath.normpath(ntpath.join(dest, ntpath.relpath(raw, src)))
    if lexical and len(raw) > 2 and raw[2] == "/":
        result = result.replace("\\", "/")
    elif lexical and path.startswith("\\\\?\\"):
        result = "\\\\?\\" + result
    return result

def ro(path):
    c = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    c.execute("PRAGMA query_only=ON")
    return c

def selected_files(home):
    ordinary_directory(home)
    selected, skipped = [], []
    def visit(p):
        if private_name(p.name) or reparse(p):
            skipped.append(str(p.relative_to(home)))
        elif p.is_dir():
            for child in sorted(p.iterdir()):
                visit(child)
        else:
            selected.append(p)
    for p in sorted(home.iterdir()):
        if p.name in CORE_DIRS or p.name in CORE_FILES or (
            re.fullmatch(r"[A-Za-z0-9_]+\.sqlite(?:-(?:wal|shm))?", p.name)
            and not p.name.startswith("logs_")
        ):
            visit(p)
    return selected, skipped

def digest_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

def active_codex_processes():
    if os.name != "nt":
        raise RuntimeError("Live process/launch operations require Windows")
    raw = subprocess.check_output(
        ["powershell.exe", "-NoLogo", "-NoProfile", "-Command",
         "Get-CimInstance Win32_Process | Select-Object Name,ProcessId,SessionId | ConvertTo-Json -Compress"],
        text=True, encoding="utf-8", creationflags=0x08000000,
    )
    rows = json.loads(raw or "[]")
    if isinstance(rows, dict):
        rows = [rows]
    return [r for r in rows if r["Name"].lower() in PROCESS_NAMES]

def audit_home(home):
    files, skipped = selected_files(home)
    result = {"files": len(files), "bytes": sum(p.stat().st_size for p in files), "skipped": skipped}
    state = home / "state_5.sqlite"
    if state.is_file():
        c = ro(state)
        try:
            tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for table in ("threads", "projects", "thread_attachments"):
                if table in tables:
                    result[table] = c.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
            if "threads" in tables:
                result["missing_rollouts"] = sum(bool(p) and not Path(p).is_file() for p, in c.execute("SELECT rollout_path FROM threads"))
        finally:
            c.close()
    history = home / "thread_history_1.sqlite"
    if history.is_file():
        c = ro(history)
        try:
            for table in ("thread_turns", "thread_items"):
                result[table] = c.execute("SELECT COUNT(*) FROM " + table).fetchone()[0]
        finally:
            c.close()
    return result

def snapshot_core(home, output):
    """Caller must stop every source writer. Never checkpoint original DBs."""
    files, skipped = selected_files(home)
    if output.exists():
        raise FileExistsError("Snapshot target already exists")
    before = {str(p.relative_to(home)): (p.stat().st_size, p.stat().st_mtime_ns) for p in files}
    output.mkdir(parents=True)
    records = []
    for p in files:
        relative = str(p.relative_to(home))
        dest = output / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        with p.open("rb") as reader, dest.open("xb") as writer:
            shutil.copyfileobj(reader, writer, 1024 * 1024)
        shutil.copystat(p, dest)
        digest = digest_file(dest)
        if digest_file(p) != digest:
            raise RuntimeError("Source changed or copy verification failed")
        records.append({"relative": relative, "sha256": digest, "bytes": dest.stat().st_size})
    after_files, _ = selected_files(home)
    after = {str(p.relative_to(home)): (p.stat().st_size, p.stat().st_mtime_ns) for p in after_files}
    if before != after:
        raise RuntimeError("Source changed; output is not accepted")
    checks = {}
    for p in list(output.glob("*.sqlite")) + [output / "sqlite/codex-dev.db"]:
        if not p.is_file():
            continue
        c = ro(p)
        try:
            if [r[0] for r in c.execute("PRAGMA quick_check")] != ["ok"]:
                raise RuntimeError("Copied DB integrity check failed")
            checks[str(p.relative_to(output))] = "ok"
        finally:
            c.close()
    return {"files": records, "excluded": skipped, "database_checks": checks}

def sql_path_plan(home, mappings):
    changes = []
    c = ro(home / "state_5.sqlite")
    try:
        for tid, rollout, cwd in c.execute("SELECT id,rollout_path,cwd FROM threads"):
            for field, old in (("rollout_path", rollout), ("cwd", cwd)):
                new = map_path(old, mappings)
                if old != new:
                    changes.append({"table": "threads", "id": tid, "field": field, "old": old, "new": new})
    finally:
        c.close()
    return changes

def apply_thread_plan(candidate, plan):
    """Library primitive for a disposable candidate only; never a SQL merger."""
    ordinary_directory(candidate)
    if not (candidate / "state_5.sqlite").is_file():
        raise FileNotFoundError("Candidate state database missing")
    c = sqlite3.connect(candidate / "state_5.sqlite")
    try:
        with c:
            for change in plan:
                if change["table"] != "threads" or change["field"] not in {"rollout_path", "cwd"}:
                    raise ValueError("Unsupported plan entry")
                field = change["field"]
                row = c.execute("SELECT " + field + " FROM threads WHERE id=?", (change["id"],)).fetchone()
                if row is None or row[0] != change["old"]:
                    raise RuntimeError("Stale plan; transaction rolled back")
                c.execute("UPDATE threads SET " + field + "=? WHERE id=?", (change["new"], change["id"]))
    finally:
        c.close()

def attachment_identity_plan(rows, mappings):
    output, seen = [], set()
    for thread, kind, old in rows:
        new = map_path(old, mappings, lexical=True)
        key = (thread, kind, new)
        if key in seen:
            raise ValueError("Attachment collision; nothing merged")
        seen.add(key)
        output.append((thread, kind, old, new))
    return output

def transform_global(data, mappings, old_home, new_home):
    data = copy.deepcopy(data)
    for key in ("thread-projectless-output-directories", "thread-workspace-root-hints"):
        for tid, value in data.get(key, {}).items():
            data[key][tid] = map_path(value, mappings)
    for tid, values in data.get("thread-writable-roots", {}).items():
        data["thread-writable-roots"][tid] = [map_path(v, mappings) for v in values]
    for item in data.get("electron-managed-worktree-archives", []):
        for key in ("root", "cwd", "workspaceRoot", "workspaceDirectory"):
            if key in item:
                item[key] = map_path(item[key], mappings, lexical=True)
    for key in ("app-server-projects-migration-by-host", "app-server-project-id-by-legacy-project-id-by-host",
                "app-server-migrated-pinned-thread-ids-by-host"):
        values = data.get(key, {})
        old, new = "local:" + old_home, "local:" + new_home
        if old in values and old != new:
            if new in values:
                raise ValueError("Host-key collision")
            values[new] = values.pop(old)
    return data
