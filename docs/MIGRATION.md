# Operator-reviewed migration

This is a recipe for a disposable candidate, not an unattended installer.
Keep original homes intact. The toolkit does not grant access, elevate permissions,
export authentication, disable sandboxing or merge SQLite rows across profiles.

## 1. Inventory

Audit each Windows user under that user's identity. Resolve actual home and SQLite
overrides, app/CLI versions, projects, history counts and updates, Git/Node/Python
executables, plugin/MCP paths and worktree links. Separate historical prompt text
from operational paths. Select primary history/project state; identify secondary-only
thread IDs without publishing contents. Establish a per-user authentication strategy.

Participant SIDs and paths belong in ignored local.settings.json. Check storage
and existing access first. Network shares and redirected ancestors are unsupported
by the launcher, which requires a local non-root drive directory.

## 2. Cold consistency and rollback

Exit the desktop in BOTH Windows sessions, CLI/app-server, MCP, automations,
computer-use/node runtime hosts and sandbox setup/workers that can write state.
A disconnected session can still run processes. Identify exact executables and
owners before stopping anything; do not terminate unrelated Git/Node/Python jobs.

The name-based process guard does not prove every external writer is stopped.
Keep a maintenance window with no new launches. Record startup commands, environment
and ACL metadata. Make restricted consistent local backups of each user's state
without exposing credential payloads. The filtered snapshot command is an additional
core snapshot, not a credential backup. Keep DB/WAL/SHM together from the same stopped
interval. Do not copy only the DB main file or checkpoint originals. Verify source
and backup manifests and copied DB integrity.

## 3. Disposable candidate and typed paths

Copy primary core into a separate candidate. Do not launch production or overwrite
originals. Keep exact typed plans and journals:

| State | Handling |
| --- | --- |
| threads.rollout_path | Map each home prefix per row; verify destination file and session identity. Preserve old strings. |
| threads.cwd and project directories | Decide each dependency: retain shared code, move a specific directory, or mark unavailable. Never replace all profile strings. |
| Global state | Review known path arrays, archives and host maps. transform_global covers only code-listed slots; do not rewrite prompt history. |
| Desktop DB/catalog/membership | Inspect installed schema; preserve primary IDs, memberships, pins/order. No generic transformer is included. Project existence is not proof of chat membership. |
| Attachment identity | Preserve slash/long-path aliases where UNIQUE identities depend on them. Stop collisions; never delete rows merely to permit updates. |
| Worktree junctions | Resolve each target and distinguish physical destination from identity alias. Do not follow unknown links recursively. |
| Git backlinks | Inspect each worktree .git and repository .git/worktrees/*/gitdir pair. Archive exact old bytes, verify reciprocity and current bytes before edits. No automatic repair is included. |
| Config/Skills/plugins | Change operational fields only; preserve custom providers and permissions. Resolve tools for both users and refresh generated runtime slots. |

plan-paths is read-only. apply_thread_plan is a library primitive that updates only
threads.rollout_path/cwd in an existing DB, asserting old values in one transaction.
It cannot establish that callers chose a disposable path; callers must enforce that.
It is not a secondary-history importer.

Counts are specific to an inventory. Account for every planned edit and verify
that unrelated strings remain unchanged.

## 4. Secondary-only sessions

Do not concatenate JSON databases, INSERT another user's threads table, or assume
JSONL contains complete history: paginated history may be in separate databases.
Retain the complete secondary snapshot even if import is unavailable.

The machine-specific prototype used experimental app-server thread/resume path
import on a disposable copy. No generalized importer is included because fields and
storage behavior change. Inspect the installed schema, prove import with synthetic
data, then compare complete turns/items, model/provider metadata and project
membership. Do not substitute a cloud-only history parameter. Stop if unique
content cannot be retained exactly.

## 5. Private bindings and launch

After explicit consent, route secrets/browser/computer-use/node_repl junctions
to each enrolled user's Local AppData. Never point secrets at another user's
private directory. The launcher refuses unknown links and existing real state
directories; it creates selected private directories but never copies login
data or modifies ACLs.

OS credential stores and identity state remain per user. keyring does not prove
all auth is external; encrypted files may exist. A requested Electron profile
does not prove every native helper uses it. Shared-core sandbox state remains
a version-sensitive unresolved boundary.

prepare-config is an internal launcher operation: do not run it concurrently
with a launcher or app. It refreshes known generated runtime slots and preserves
permissions. Never lower protection to bypass setup.

Review candidate, then separately authorize stopped-app promotion. Create
SHARED-HOME-READY.json only after review. Use the guarded launcher; normal shortcuts
do not inherit its child-only CODEX_HOME.

## 6. Acceptance and rollback

Use A → B → A, stopping every previous-user writer each time. Verify:

- Same complete history, project membership, pins and order.
- A designated real conversation continues and survives the return.
- A dedicated test project reads/writes its test file at the intended permission level.
- Ordinary config/Skills load and tools resolve; both users log in independently
  without shared auth files or decryption failures.
- Browser/helper and Windows setup observations are recorded separately. Synthetic
  app-server success is not desktop or sandbox acceptance.
- Original homes receive no new writes; exact app/CLI versions are recorded.

On mismatch, stop all writers and restore original startup/environment settings to
untouched homes. Restore reviewed Git backlinks from byte journals only after
checking for subsequent Git edits. Remove known junction entries only, never target
trees. Preserve candidate and newly shared conversations for reconciliation; never
automatically merge DBs back or delete failed copies.

Abrupt launcher death can release its lease while the app lives: stop that app
before any further launch. This toolkit does not provide crash-atomic promotion.
