---
name: connect-instance-replication
description: "Replicate Amazon Connect instance configuration cross-region using primitive Connect APIs (no Global Resiliency). Always updates a pre-existing target instance."
user-invocable: true
disable-model-invocation: false
---

# Amazon Connect Instance Replication (Primitive APIs) Skill

Use this skill to **replicate an Amazon Connect instance's configuration** from a source region (e.g. `us-east-1`) into a **pre-existing** target instance in another region (e.g. `us-west-2`) in minutes.

This is **best-effort configuration replication** using the suite of **primitive Amazon Connect APIs** (List/Describe/Create/Update). It is **not** Amazon Connect Global Resiliency.

## Design Philosophy: Pre-Existing Target Instance

This skill **always replicates into a pre-existing target instance**. It does **not** create new instances on-the-fly.

**Why?** Enterprises need predictable instance IDs for:
- CloudWatch alarms and dashboards
- Cost allocation tags and billing
- IAM policies scoped to specific instance ARNs
- Integration endpoints (Lambda, Lex, Kinesis)
- Compliance/audit trails

Provision your target instance in advance (via Console, CLI, or IaC), then use this skill to sync configuration.

## What this skill replicates (bundle v2)

1. **Hours of Operation**
2. **Agent Statuses** (custom availability states)
3. **Security Profiles** (permissions)
4. **User Hierarchy Groups** (org structure)
5. **Queues** (STANDARD)
6. **Routing Profiles** (skill-based routing)
7. **Quick Connects** (queue + phone types; user-type skipped)
8. **Contact Flow Modules**
9. **Contact Flows**
10. **Instance Attributes** (feature flags like Contact Lens, flow logs)

Import order is dependency-aware:
Hours → Agent Statuses → Security Profiles → Hierarchy Groups → Queues → Routing Profiles → Quick Connects → Modules → Flows → Instance Attributes

## What this does NOT replicate (by design)

- Phone numbers / telephony claims (region-specific)
- Users (require identity provider setup)
- Prompts / audio assets (require S3 migration)
- Lex bots, Lambda functions, S3 assets (must exist in target region)

## Safety rules

- Live import actions require an explicit `--yes` acknowledgement.
- Prefer `--dry-run` first to validate mapping and scope.
- Prefer `--skip-unsupported` to skip flows with external dependencies.

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

### 2) Replicate into an existing target instance

```bash
python3 ~/.copilot/skills/connect-instance-replication/scripts/connect_instance_replication.py replicate \
  --source-region us-east-1 \
  --source-alias my-prod-connect \
  --target-region us-west-2 \
  --target-alias my-dr-connect \
  --overwrite \
  --skip-unsupported \
  --continue-on-error \
  --yes
```

### 3) Replicate using instance IDs

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
