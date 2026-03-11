# Amazon Connect Replicator (Primitive APIs)

A **best-effort** exporter/importer to replicate Amazon Connect configuration from a source instance (e.g., `us-east-1`) into a **pre-existing** target instance (e.g., `us-west-2`) using Connect's primitive APIs (`List*`/`Describe*` → `Create*`/`Update*`).

This repo is intentionally scoped to what Connect exposes as CRUD-style APIs; it is **not** Amazon Connect Global Resiliency.

## 🤖 NEW: Interactive AI Agent

Use the **GitHub Copilot AI Agent** for guided, interactive replication:

```bash
# Install the agent skill
cp -r copilot-skills/connect-replication-agent ~/.copilot/skills/

# Then in Copilot CLI:
Use the connect-replication-agent skill to replicate my Connect instance
```

The agent will:
- 🔍 Discover instances in your regions
- ❓ Ask clarifying questions (source, target, options)
- 🚀 Execute replication with your choices
- 🔧 Troubleshoot any issues
- 📊 Provide detailed summaries
- 💬 Support follow-up commands

See: [Copilot AI Agent](#copilot-ai-agent-interactive-replication)

---

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

| Directory | Description |
|-----------|-------------|
| `packages/api` | Express API that calls the Connect APIs |
| `packages/ui` | React UI wizard to pick regions/instances, export a bundle, and import it |
| `tools/connect-instance-replicator` | Python CLI (boto3) to export/import bundles (recommended for automation) |
| `copilot-skills/connect-instance-replication` | Copilot Skill wrapper for on-demand replication |
| `copilot-skills/connect-replication-agent` | **NEW:** Interactive AI Agent for guided replication |

## Supported resources (bundle v3.2 — 19 resource types)

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
| 18 | **Lambda Functions** | `ListLambdaFunctions` | `AssociateLambdaFunction` + ARN rewrite |
| 19 | **Lex Bots (V1/V2)** | `ListBots` / `ListLexBots` | `AssociateBot` + ARN rewrite |

Matching is **by name** (and for flows: `type|name`) and then upserted.

Import order is dependency-aware:
1. Hours → 2. Agent Statuses → 3. Security Profiles → 4. Hierarchy Groups → 5. Queues → 6. Routing Profiles → 7. Quick Connects → 7a. **Prompts** → 8. Modules → 9. Flows → 10. Instance Attrs → 11. Predefined Attrs → 12. Task Templates → 13. Views → 14. Rules → 15. Eval Forms → 16. Vocabularies → 17. Lambda Associations → 18. Lex Associations

**Note:** Prompts are processed at step 7a (before flows) to ensure prompt ARN replacements are available when processing flow content.

## What this does NOT do (by design / API reality)

Amazon Connect does **not** offer a single API to "clone an instance" end-to-end (telephony, identity management, storage config, phone numbers, etc.).

Resources that are **not** replicated:
- Phone numbers / telephony claims (region-specific)
- Users (require identity provider setup)
- Lex bots, Lambda functions (external AWS resources — but ARNs are rewritten and associations are created)

## Lambda & Lex Handling

The replicator **discovers** Lambda functions and Lex bots associated with the source instance and:

1. **Rewrites ARNs** in flow content from source region to target region:
   ```
   arn:aws:lambda:us-east-1:123456789012:function:MyFunc
                   ↓
   arn:aws:lambda:us-west-2:123456789012:function:MyFunc
   ```

2. **Associates** Lambda/Lex with the target instance so they appear in flow designer dropdowns

3. **(Optional)** Copies Lambda functions and Lex V2 bots to the target region with `--copy-lambda` and `--copy-lex` flags

**Prerequisite:** Lambda functions and Lex bots must exist in the target region with the same name/ID.

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

---

## Copilot AI Agent (Interactive Replication)

The **connect-replication-agent** provides an interactive, conversational interface for Connect instance replication.

### Installation

```bash
# Copy the agent skill to your Copilot skills directory
cp -r copilot-skills/connect-replication-agent ~/.copilot/skills/

# Also install the underlying replication skill (if not already installed)
cp -r copilot-skills/connect-instance-replication ~/.copilot/skills/
```

### Usage Examples

#### Basic Replication (Guided)
```
User: Use the connect-replication-agent skill to replicate my Connect instance

Agent: Let me discover the available Connect instances...

Found in us-east-1:
  1. my-prod-connect (ACTIVE)
  2. my-test-connect (ACTIVE)

Which region contains your SOURCE instance?
> us-east-1

Which instance should be the SOURCE?
> my-prod-connect

Which region contains your TARGET instance?
> us-west-2

[Agent discovers instances in us-west-2...]
```

#### Direct Replication
```
User: Replicate Connect from my-prod-connect in us-east-1 to my-dr-connect in us-west-2

Agent: I'll replicate from my-prod-connect (us-east-1) to my-dr-connect (us-west-2).

Should I overwrite existing resources in the target? (Yes/No)
> Yes

Should I skip flows with unsupported dependencies (Lambda/Lex/prompts not in target)? (Yes/No)
> Yes

Proceeding with replication...
```

#### Dry Run Preview
```
User: Do a dry run replication from us-east-1 to us-west-2

Agent: Running in dry-run mode (no changes will be made)...
[Shows what would be created/updated without making changes]
```

#### Discovery Only
```
User: List all Connect instances in us-east-1 and us-west-2

Agent: 
us-east-1:
  - my-prod-connect (ACTIVE) - abc-123-def
  - my-test-connect (ACTIVE) - xyz-789-uvw

us-west-2:
  - my-dr-connect (ACTIVE) - 111-222-333
```

#### Verification
```
User: Verify resource counts in my-dr-connect

Agent: Resource counts for my-dr-connect (us-west-2):

| Resource Type         | Count |
|-----------------------|-------|
| Hours of Operation    | 3     |
| Agent Statuses        | 2     |
| Security Profiles     | 4     |
| Queues                | 9     |
| Routing Profiles      | 4     |
| Contact Flows         | 22    |
| Prompts               | 7     |
| Task Templates        | 1     |
| Views                 | 5     |
...
```

### Agent Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     INTERACTIVE WORKFLOW                             │
├─────────────────────────────────────────────────────────────────────┤
│  1. User invokes agent with replication request                      │
│  2. Agent discovers instances in source/target regions               │
│  3. Agent asks clarifying questions:                                 │
│     • Confirm source and target instances                            │
│     • Overwrite existing resources?                                  │
│     • Skip unsupported flows?                                        │
│     • Continue on errors?                                            │
│  4. Agent executes replication with user's choices                   │
│  5. Agent monitors progress and handles errors                       │
│  6. Agent provides detailed summary of results                       │
│  7. Agent offers follow-up options                                   │
└─────────────────────────────────────────────────────────────────────┘
```

### Example Replication Summary

After replication, the agent provides a detailed summary:

```
✅ Replication Complete!

Source: my-prod-connect (us-east-1)
Target: my-dr-connect (us-west-2)

| Resource Type           | Source | Target | Status |
|-------------------------|--------|--------|--------|
| Hours of Operation      | 2      | 3      | ✅ +1 pre-existing |
| Agent Statuses          | 2      | 2      | ✅ system statuses |
| Security Profiles       | 4      | 4      | ✅     |
| User Hierarchy Groups   | 0      | 0      | ✅     |
| Queues                  | 4      | 9      | ✅ +5 pre-existing |
| Routing Profiles        | 4      | 4      | ✅     |
| Quick Connects          | 0      | 0      | ✅     |
| Flow Modules            | 0      | 0      | ✅     |
| Contact Flows           | 20     | 22     | ✅ +2 pre-existing |
| Instance Attributes     | 10     | 10     | ✅     |
| Predefined Attributes   | 14     | 14     | ✅ system attrs |
| Prompts                 | 7      | 7      | ✅ mapped |
| Task Templates          | 1      | 1      | ✅     |
| Views                   | 5      | 5      | ✅     |
| Rules                   | 0      | 0      | ✅     |
| Evaluation Forms        | 0      | 0      | ✅     |
| Vocabularies            | 0      | 0      | ✅     |
| Lambda Functions        | 0      | 0      | ✅     |
| Lex Bots                | 0      | 0      | ✅     |

Skipped: 5 flows with unsupported dependencies
Failures: 0

Artifacts saved to: ~/Downloads/acr-replication-runs/20260311T211921Z-abc123/
  • bundle.json - exported configuration
  • import-report.json - detailed results
  • verify.json - post-import counts

What would you like to do next?
1. View detailed import report
2. Replicate to another instance
3. Ask a question about the results
```

### Troubleshooting

The agent handles common issues:

| Issue | Agent Response |
|-------|----------------|
| Instance not found | Lists available instances, asks user to select |
| Permission denied | Checks credentials, suggests IAM permissions |
| Resource creation failed | Explains error, suggests workarounds |
| Unsupported dependencies | Explains which flows have Lambda/Lex, offers to skip |
| JSON parsing error | Handles automatically (fixed in v2.0) |

---

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
