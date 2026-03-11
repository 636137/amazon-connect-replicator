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

## Supported resources (bundle v3)

Export (source) → import (target):

| # | Resource | Export APIs | Import APIs |
|---|----------|-------------|-------------|
| 1 | **Hours of Operation** | `ListHoursOfOperations` + `DescribeHoursOfOperation` | `Create/Update` |
| 2 | **Agent Statuses** | `ListAgentStatuses` + `DescribeAgentStatus` | `Create/Update` |
| 3 | **Security Profiles** | `ListSecurityProfiles` + `DescribeSecurityProfile` | `Create/Update` |
| 4 | **User Hierarchy Groups** | `ListUserHierarchyGroups` + `DescribeUserHierarchyGroup` | `Create/Update` |
| 5 | **Queues (STANDARD)** | `ListQueues` + `DescribeQueue` | `CreateQueue` + `UpdateQueue*` |
| 6 | **Routing Profiles** | `ListRoutingProfiles` + `DescribeRoutingProfile` | `Create/Update*` |
| 7 | **Quick Connects** | `ListQuickConnects` + `DescribeQuickConnect` | `Create/Update*` |
| 8 | **Contact Flow Modules** | `ListContactFlowModules` + `DescribeContactFlowModule` | `Create/UpdateContent` |
| 9 | **Contact Flows** | `ListContactFlows` + `DescribeContactFlow` | `Create/UpdateContent` |
| 10 | **Instance Attributes** | `DescribeInstanceAttribute` | `UpdateInstanceAttribute` |
| 11 | **Predefined Attributes** | `ListPredefinedAttributes` + `Describe` | `Create/Update` |
| 12 | **Prompts** | `ListPrompts` + `DescribePrompt` | `CreatePrompt` (with S3 copy) |
| 13 | **Task Templates** | `ListTaskTemplates` + `GetTaskTemplate` | `Create/Update` |
| 14 | **Views** | `ListViews` + `DescribeView` | `CreateView/UpdateViewContent` |
| 15 | **Rules** | `ListRules` + `DescribeRule` | `Create/Update` |
| 16 | **Evaluation Forms** | `ListEvaluationForms` + `DescribeEvaluationForm` | `CreateEvaluationForm` |
| 17 | **Vocabularies** | `SearchVocabularies` + `DescribeVocabulary` | `CreateVocabulary` |

Matching is **by name** (and for flows: `type|name`) and then upserted.

Import order is dependency-aware:
1. Hours → 2. Agent Statuses → 3. Security Profiles → 4. Hierarchy Groups → 5. Queues → 6. Routing Profiles → 7. Quick Connects → 8. Modules → 9. Flows → 10. Instance Attrs → 11. Predefined Attrs → 12. Prompts → 13. Task Templates → 14. Views → 15. Rules → 16. Eval Forms → 17. Vocabularies

## What this does NOT do (by design / API reality)

Amazon Connect does **not** offer a single API to "clone an instance" end-to-end (telephony, identity management, storage config, phone numbers, etc.).

Resources that are **not** replicated:
- Phone numbers / telephony claims (region-specific)
- Users (require identity provider setup)
- Lex bots, Lambda functions (external AWS resources)

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

```bash
# Export
python3 tools/connect-instance-replicator/connect_instance_replicate.py export \
  --region us-east-1 --instance-id SOURCE_ID --out bundle.json

# Import (with prompts)
python3 tools/connect-instance-replicator/connect_instance_replicate.py import \
  --region us-west-2 --instance-id TARGET_ID --in bundle.json \
  --overwrite --continue-on-error --skip-unsupported \
  --prompt-s3-bucket my-bucket-us-west-2
```

See: [`tools/connect-instance-replicator/README.md`](tools/connect-instance-replicator/README.md)

## Copilot Skill

See: [`copilot-skills/connect-instance-replication/SKILL.md`](copilot-skills/connect-instance-replication/SKILL.md)

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
