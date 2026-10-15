# Validation and limits

## Evidence categories

1. Original machine-specific prototype: sequential real desktop continuation across
   two Windows users and return was observed. Synthetic app-server and sandbox
   write-boundary checks were separate. These do not establish full browser or
   sandbox-state separation.
2. Prototype production activation: primary history and one secondary-only session
   were preserved with content comparison; projects and worktree backlinks were
   migrated with machine-specific review. Formal second-user and return-to-first
   production acceptance remains unverified at release preparation.
3. This generalized public toolkit: synthetic fixtures, Python syntax checks and
   static PowerShell parsing only. No live migration or launcher run is part of
   testing. Prototype evidence is not E2E acceptance of these generalized scripts.

Tests cover component paths, aliases/collisions, global-state slots, private-file
exclusion, existing-output refusal, paginated DB preservation, stale-plan rollback,
and permission/config preservation. CI uses Linux/Windows and Python 3.11/3.12;
Windows only parses the launcher, without executing it.

## Unverified or limited

- Broad version compatibility, schema adaptation, MSIX launching and generalized
  desktop A → B → A acceptance.
- Complete Windows sandbox identity/state separation in a shared home.
- Exclusive private Electron profile use by every browser/native helper.
- Session import across providers or future paginated schemas.
- Automatic catalog migration, secondary merging, Git backlink edits, promotion
  and post-migration history reconciliation.
- Full process inventory: custom/external writers can evade name matching.
- Embedded secret discovery. Name filtering is not a content security scan.
- Crash recovery across config changes and junction routing.

Shared-home writers must be trusted. The lease blocks cooperating launchers, not
direct app starts or malicious writers. Selected links retain the last participant's
targets after exit; they are checked before the next switch. This does not create
a security boundary between participants.
