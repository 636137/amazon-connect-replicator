# Amazon Connect Replicator (Primitive APIs)

A **best-effort** exporter/importer to replicate Amazon Connect configuration from a source instance (e.g., `us-east-1`) into a **pre-existing** target instance (e.g., `us-west-2`) using Connect's primitive APIs (`List*`/`Describe*` → `Create*`/`Update*`).

This repo is intentionally scoped to what Connect exposes as CRUD-style APIs; it is **not** Amazon Connect Global Resiliency.

## Design Philosophy: Pre-Existing Target Instance

This tool **always replicates into a pre-existing target instance**. It does **not** create new instances on-the-fly.

**Why?** Enterprises need predictable instance IDs for:
- CloudWatch alarms and dashboards
- Cost allocation tags and billing
- IAM policies scoped to specific instance ARNs
- Integration endpoints (Lambda, Lex, Kinesis)
- Compliance/audit trails

Provision your target instance in advance (via Console, CLI, or IaC), then use this tool to sync configuration.

## What's in this repo
- `packages/api`: Express API that calls the Connect APIs
- `packages/ui`: React UI wizard to pick regions/instances, export a bundle, and import it
- `tools/connect-instance-replicator`: Python CLI (boto3) to export/import bundles (recommended for automation)
- `copilot-skills/connect-instance-replication`: a vendored **Copilot Skill** (plus helper script) to run replication on-demand

## Supported resources (bundle v2)

Export (source) → import (target):

| Resource | Export APIs | Import APIs |
|----------|-------------|-------------|
| **Hours of Operation** | `ListHoursOfOperations` + `DescribeHoursOfOperation` | `CreateHoursOfOperation` / `UpdateHoursOfOperation` |
| **Agent Statuses** | `ListAgentStatuses` + `DescribeAgentStatus` | `CreateAgentStatus` / `UpdateAgentStatus` |
| **Security Profiles** | `ListSecurityProfiles` + `DescribeSecurityProfile` | `CreateSecurityProfile` / `UpdateSecurityProfile` |
| **User Hierarchy Groups** | `ListUserHierarchyGroups` + `DescribeUserHierarchyGroup` | `CreateUserHierarchyGroup` / `UpdateUserHierarchyGroup*` |
| **Queues (STANDARD)** | `ListQueues` + `DescribeQueue` | `CreateQueue` + `UpdateQueue*` |
| **Routing Profiles** | `ListRoutingProfiles` + `DescribeRoutingProfile` | `CreateRoutingProfile` / `UpdateRoutingProfile*` |
| **Quick Connects** | `ListQuickConnects` + `DescribeQuickConnect` | `CreateQuickConnect` / `UpdateQuickConnect*` |
| **Contact Flow Modules** | `ListContactFlowModules` + `DescribeContactFlowModule` | `CreateContactFlowModule` / `UpdateContactFlowModuleContent` |
| **Contact Flows** | `ListContactFlows` + `DescribeContactFlow` | `CreateContactFlow` / `UpdateContactFlowContent` |
| **Instance Attributes** | `DescribeInstanceAttribute` | `UpdateInstanceAttribute` |

Matching is **by name** (and for flows: `type|name`) and then upserted.

Import order is dependency-aware:
1. Hours → 2. Agent Statuses → 3. Security Profiles → 4. Hierarchy Groups → 5. Queues → 6. Routing Profiles → 7. Quick Connects → 8. Modules → 9. Flows → 10. Instance Attributes

## What this does NOT do (by design / API reality)

Amazon Connect does **not** offer a single API to "clone an instance" end-to-end (telephony, identity management, storage config, phone numbers, etc.).

Resources that are **not** replicated:
- Phone numbers / telephony claims (region-specific)
- Users (require identity provider setup)
- Prompts / audio assets (require S3 migration)
- Lex bots, Lambda functions, S3 assets (must exist in target region)

## Reliability notes (lessons learned from live replication)

Connect flow/module JSON embeds references as both **IDs** and full **ARN strings**, and import can fail if any source references leak into the target.

Key hardening that makes the importer much more reliable:
1. **Omit nils:** the AWS SDKs reject `null` for optional fields; we must omit keys instead of sending `null`.
2. **Replace longest-first:** if you replace an ID before replacing its containing ARN, you can accidentally corrupt the ARN. The importer applies replacements sorted by source-string length so full ARNs are rewritten before IDs.
3. **Pre-map existing flows:** on overwrite imports, we pre-populate a flow rewrite map for flows that already exist in the target instance (matched by `type|name`) so cross-flow references can be rewritten on the first pass.
4. **Two-pass flow update:** we still do a second pass to catch references to flows created during the same import run.

## Quickstart (UI + API)
```bash
npm install
npm run dev
```
- UI: http://localhost:3000
- API: http://localhost:3001

## API endpoints (used by the UI)
- `GET /api/connect/regions`
- `GET /api/connect/instances?region=us-east-1`
- `POST /api/connect/export` → `{ region, instanceId }`
- `POST /api/connect/import` → `{ region, instanceId, overwrite?, dryRun?, bundle }`

## Python CLI (recommended for automation)
See: [`tools/connect-instance-replicator/README.md`](tools/connect-instance-replicator/README.md)

## Copilot Skill: connect-instance-replication (run on demand)

This repo vendors a Copilot skill you can install into your local Copilot CLI so you can run:

- instance discovery (list instances by region)
- export → import into existing target → verify counts

…with the same proven importer hardening (omit nils, longest-first replacements, two-pass flow rewrites).

### Skill location in this repo

- `copilot-skills/connect-instance-replication/SKILL.md`
- `copilot-skills/connect-instance-replication/scripts/connect_instance_replication.py`

### Install the skill locally

1) Copy the skill folder into your Copilot skills directory:

```bash
mkdir -p ~/.copilot/skills
cp -R ./copilot-skills/connect-instance-replication ~/.copilot/skills/connect-instance-replication
```

2) Install Python deps for the helper script:

```bash
pip3 install -r ~/.copilot/skills/connect-instance-replication/requirements.txt
```

### How the skill works

The helper script is a thin wrapper around the repo's replicator CLI:

- `tools/connect-instance-replicator/connect_instance_replicate.py`

It uses primitive Amazon Connect APIs (via boto3) to:

1) resolve instance IDs (by alias) using `ListInstances`
2) export a bundle from the source instance (all v2 resources)
3) import the bundle into the pre-existing target instance (create/update)
4) verify counts and write a small report set

### Safety guardrails

- Any live action that can change AWS state requires `--yes`.
- `--dry-run` is supported for import (no Create/Update calls).

### Where artifacts are written

Each run writes a timestamped directory (by default):

- `~/Downloads/acr-replication-runs/<runId>/`

Containing:

- `bundle.json` (exported configuration)
- `import-report.json` (import results from the underlying replicator)
- `verify.json` (post-import resource counts)

The script prints a final JSON summary to stdout with the runId, artifact paths, and verification counts.

### Usage examples

#### 1) Discover instances in a region

```bash
python3 ~/.copilot/skills/connect-instance-replication/scripts/connect_instance_replication.py discover \
  --region us-east-1
```

Expected result (shape):

```json
{
  "region": "us-east-1",
  "instances": [
    {
      "alias": "my-prod-connect",
      "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      "arn": "arn:aws:connect:us-east-1:123456789012:instance/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      "status": "ACTIVE",
      "created": "2026-03-01T12:34:56+00:00"
    }
  ]
}
```

#### 2) Replicate into an existing target instance

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

Expected results:
- A bundle is exported from the source instance.
- The bundle is imported into the target instance.
- A summary JSON is printed and artifacts are written to the run folder.

Example summary output (shape):

```json
{
  "runId": "20260311T190000Z-abc123",
  "workdir": "/Users/you/Downloads/acr-replication-runs/20260311T190000Z-abc123",
  "source": { "region": "us-east-1", "instanceId": "..." },
  "target": { "region": "us-west-2", "instanceId": "..." },
  "paths": {
    "bundle": ".../bundle.json",
    "importReport": ".../import-report.json",
    "verify": ".../verify.json"
  },
  "verifyCounts": { "hours": 2, "queues": 6, "modules": 0, "flows": 21 }
}
```

#### 3) Dry-run import (no Create/Update calls)

```bash
python3 ~/.copilot/skills/connect-instance-replication/scripts/connect_instance_replication.py replicate \
  --source-region us-east-1 \
  --source-instance-id SOURCE_INSTANCE_ID \
  --target-region us-west-2 \
  --target-instance-id TARGET_INSTANCE_ID \
  --dry-run
```

### Environment variables

If your repo is not in `~/amazon-connect-replicator`, set one of:

- `ACR_REPO=/path/to/amazon-connect-replicator`
- `ACR_REPLICATOR_SCRIPT=/full/path/to/connect_instance_replicate.py`

## Example: live us-east-1 → us-west-2 replication

A live test was performed by exporting from a real `us-east-1` instance and importing into a pre-existing `us-west-2` instance.

Results (best-effort, with `--overwrite --continue-on-error --skip-unsupported`):
- Hours: updated=2
- Queues: updated=6
- Flows: updated=15, created=1
- Skipped unsupported flows: 6
- Failures: 0

That is "as close as possible" to a fast configuration sync using only primitive APIs, while safely skipping flows that require external dependencies.

## References
- Admin guide (flow import/export): https://docs.aws.amazon.com/connect/latest/adminguide/contact-flow-import-export.html
- API Operations list: https://docs.aws.amazon.com/connect/latest/APIReference/API_Operations_Amazon_Connect_Service.html
- Best practices for using Amazon Connect APIs: https://docs.aws.amazon.com/connect/latest/APIReference/best-practices-connect-apis.html
