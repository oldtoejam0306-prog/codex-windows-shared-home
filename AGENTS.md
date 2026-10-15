# Contributor instructions

Use only synthetic fixtures in tests. Never run migration or startup against a
contributor's real Codex home during tests. Do not commit settings, reports,
SQLite databases, rollouts, credentials or browser/sandbox state.

Preserve sequential-only operation, typed path rewrites, original-data retention
and refusal of unexpected junctions. Do not add SQL row merging across profiles,
credential export, automatic ACL changes or sandbox bypasses.
