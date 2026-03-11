---
name: connect-instance-replication
description: "Replicate Amazon Connect instance configuration cross-region (hours, queues, contact flows + modules) using primitive Connect APIs (no Global Resiliency)."
user-invocable: true
disable-model-invocation: false
---

# Amazon Connect Instance Replication (Primitive APIs) Skill

Use this skill to **replicate an Amazon Connect instance’s configuration** from a source region (e.g. `us-east-1`) into a target region (e.g. `us-west-2`) in minutes.

This is **best-effort configuration replication** using the suite of **primitive Amazon Connect APIs** (List/Describe/Create/Update). It is **not** Amazon Connect Global Resiliency.

## What this skill replicates (bundle v1)

- Hours of operation
- Queues (STANDARD)
- Contact flow modules
- Contact flows

Import order is dependency-aware:
1) Hours → 2) Queues → 3) Modules → 4) Flows

## What this does NOT replicate (by design)

- Phone numbers / telephony claims
- Users, security profiles, routing profiles
- Quick connects
- Prompts / audio assets
- Lex bots, Lambda functions, S3 assets, or other external dependencies referenced by flows

## Safety rules

- Live creation/import actions require an explicit `--yes` acknowledgement.
- Prefer `--dry-run` first to validate mapping and scope.
- Prefer `--skip-unsupported` to keep runs fast when flows reference external assets.

## Prerequisites

- Python 3 + pip
- AWS credentials available locally (env vars, SSO, or shared config; optional `--profile`)
- The `amazon-connect-replicator` repo is present locally (default expected path):
  - `~/amazon-connect-replicator/tools/connect-instance-replicator/connect_instance_replicate.py`

If your repo is elsewhere, set either:
- `ACR_REPO=/path/to/amazon-connect-replicator`
- `ACR_REPLICATOR_SCRIPT=/full/path/to/connect_instance_replicate.py`

Install deps (one-time):

```bash
pip3 install -r ~/.copilot/skills/connect-instance-replication/requirements.txt
```

## Commands

Helper script:

- `~/.copilot/skills/connect-instance-replication/scripts/connect_instance_replication.py`

### 1) Discover instances in a region

```bash
python3 ~/.copilot/skills/connect-instance-replication/scripts/connect_instance_replication.py discover \
  --region us-east-1
```

### 2) Replicate source → brand new target instance

This is the fastest “from scratch in the other region” path.

```bash
python3 ~/.copilot/skills/connect-instance-replication/scripts/connect_instance_replication.py replicate \
  --source-region us-east-1 \
  --source-alias YOUR_SOURCE_ALIAS \
  --target-region us-west-2 \
  --create-target \
  --target-alias acr-repl-demo-001 \
  --skip-unsupported \
  --continue-on-error \
  --yes
```

### 3) Replicate into an existing target instance

```bash
python3 ~/.copilot/skills/connect-instance-replication/scripts/connect_instance_replication.py replicate \
  --source-region us-east-1 \
  --source-instance-id SOURCE_INSTANCE_ID \
  --target-region us-west-2 \
  --target-instance-id TARGET_INSTANCE_ID \
  --overwrite \
  --skip-unsupported \
  --continue-on-error \
  --yes
```

### 4) Dry-run import (no Create/Update calls)

Note: `--dry-run` cannot be combined with `--create-target` (creating an instance is always a live action).

```bash
python3 ~/.copilot/skills/connect-instance-replication/scripts/connect_instance_replication.py replicate \
  --source-region us-east-1 \
  --source-instance-id SOURCE_INSTANCE_ID \
  --target-region us-west-2 \
  --target-instance-id TARGET_INSTANCE_ID \
  --dry-run
```

## Outputs

Each run creates a timestamped folder (default: `~/Downloads/acr-replication-runs/<runId>/`) containing:

- `bundle.json` (exported configuration)
- `import-report.json` (import results)
- `verify.json` (post-import resource counts)

## Notes on hard problems (already handled)

- Optional fields: SDKs reject `None/null` parameters → importer omits nil keys.
- Flow reference rewriting: replacements are applied **longest-first** (full ARNs before IDs) to avoid corrupting ARNs.
- Cross-flow references: existing target flows are pre-mapped by `type|name` before the first update pass; a second pass handles newly created flow IDs.
