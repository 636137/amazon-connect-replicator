# Amazon Connect Replicator (Primitive APIs)

A **best-effort** exporter/importer to replicate *selected* Amazon Connect configuration from a source instance (e.g., `us-east-1`) into a target instance (e.g., `us-west-2`) using Connect’s primitive APIs (`List*`/`Describe*` → `Create*`/`Update*`).

This repo is intentionally scoped to what Connect exposes as CRUD-style APIs; it is **not** Amazon Connect Global Resiliency.

## What’s in this repo
- `packages/api`: Express API that calls the Connect APIs
- `packages/ui`: React UI wizard to pick regions/instances, export a bundle, and import it
- `tools/connect-instance-replicator`: Python CLI (boto3) to export/import bundles (useful for automation and live testing)

## Supported resources (bundle v1)
Export (source) → import (target):
- **Hours of operation** (`ListHoursOfOperations`/`DescribeHoursOfOperation` → `CreateHoursOfOperation`/`UpdateHoursOfOperation`)
- **Queues (STANDARD)** (`ListQueues`/`DescribeQueue` → `CreateQueue` + `UpdateQueue*`)
- **Contact flow modules** (`ListContactFlowModules`/`DescribeContactFlowModule` → `CreateContactFlowModule`/`UpdateContactFlowModuleContent`)
- **Contact flows** (`ListContactFlows`/`DescribeContactFlow` → `CreateContactFlow`/`UpdateContactFlowContent`)

Matching is **by name** (and for flows: `type|name`) and then upserted.

## What this does NOT do (by design / API reality)
Amazon Connect does **not** offer a single API to “clone an instance” end-to-end (telephony, identity management, storage config, phone numbers, etc.).

Common dependencies that frequently appear inside flow JSON but are **not yet migrated** by this project:
- Prompts + prompt audio assets
- Lex bots
- Lambda functions
- S3 assets referenced by flows
- Phone numbers
- Quick connects, routing profiles, security profiles, users, etc.

## Reliability notes (lessons learned from live replication)
Connect flow/module JSON embeds references as both **IDs** and full **ARN strings**, and import can fail if any source references leak into the target.

Key hardening that makes the importer much more reliable:
1. **Omit nils:** the AWS SDKs reject `null` for optional fields; we must omit keys instead of sending `null`.
2. **Replace longest-first:** if you replace an ID before replacing its containing ARN, you can accidentally corrupt the ARN (e.g., `.../queue/<sourceId>` becomes `.../queue/<targetId>` but still points at the *source instance*). The importer applies replacements sorted by source-string length so full ARNs are rewritten before IDs.
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

## Example: live us-east-1 → us-west-2 replication
A live test was performed by exporting from a real `us-east-1` instance and importing into a newly created `us-west-2` instance.

Results (best-effort, with `--overwrite --continue-on-error --skip-unsupported`):
- Hours: updated=2
- Queues: updated=6
- Flows: updated=15, created=1
- Skipped unsupported flows: 6
- Failures: 0

That is “as close as possible” to a fast clone using only primitive APIs, while safely skipping flows that require external dependencies.

## References
- Admin guide (flow import/export): https://docs.aws.amazon.com/connect/latest/adminguide/contact-flow-import-export.html
- API `DescribeContactFlow`: https://docs.aws.amazon.com/connect/latest/APIReference/API_DescribeContactFlow.html
- API `CreateContactFlow`: https://docs.aws.amazon.com/connect/latest/APIReference/API_CreateContactFlow.html
- API `UpdateContactFlowContent`: https://docs.aws.amazon.com/connect/latest/APIReference/API_UpdateContactFlowContent.html
