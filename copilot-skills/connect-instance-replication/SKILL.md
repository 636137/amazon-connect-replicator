---
name: connect-instance-replication
description: Replicate Amazon Connect instance configuration across regions using primitive APIs. Exports/imports 17 resource types into pre-existing target instances with selective resource control.
user-invocable: true
disable-model-invocation: false
---

# Amazon Connect Instance Replication Skill

Replicate Amazon Connect configuration from a source instance to a **pre-existing** target instance using primitive Connect APIs (not Global Resiliency).

## Design Philosophy

This skill **always replicates into a pre-existing target instance**. It does NOT create new instances on-the-fly.

**Why?** Enterprises need predictable instance IDs for:
- CloudWatch alarms and dashboards
- Cost allocation tags and billing
- IAM policies scoped to specific instance ARNs
- Integration endpoints (Lambda, Lex, Kinesis)
- Compliance/audit trails

Provision your target instance in advance, then use this skill to sync configuration.

## Bundle v3 Scope (17 resource types)

The replicator exports and imports these resource types in dependency-aware order:

| # | Resource Type | Description | API Used |
|---|---------------|-------------|----------|
| 1 | Hours of Operation | Business hours schedules | CreateHoursOfOperation / UpdateHoursOfOperation |
| 2 | Agent Statuses | Custom agent availability states | CreateAgentStatus / UpdateAgentStatus |
| 3 | Security Profiles | Permission sets for agents | CreateSecurityProfile / UpdateSecurityProfile |
| 4 | User Hierarchy Groups | Agent organizational hierarchy | CreateUserHierarchyGroup |
| 5 | Queues (STANDARD) | Call/chat routing queues | CreateQueue / UpdateQueueHoursOfOperation |
| 6 | Routing Profiles | Queue priority assignments | CreateRoutingProfile / UpdateRoutingProfileQueues |
| 7 | Quick Connects | One-click transfer destinations | CreateQuickConnect / UpdateQuickConnectConfig |
| 8 | Contact Flow Modules | Reusable flow components | CreateContactFlowModule / UpdateContactFlowModuleContent |
| 9 | Contact Flows | IVR and routing logic | CreateContactFlow / UpdateContactFlowContent |
| 10 | Instance Attributes | Instance-level settings | UpdateInstanceAttribute |
| 11 | Predefined Attributes | Contact attribute definitions | CreatePredefinedAttribute / UpdatePredefinedAttribute |
| 12 | Prompts | Audio prompts (with S3 copy) | CreatePrompt |
| 13 | Task Templates | Structured task definitions | CreateTaskTemplate / UpdateTaskTemplate |
| 14 | Views | Custom agent UI views | CreateView / UpdateViewContent |
| 15 | Rules | Automation rules and triggers | CreateRule / UpdateRule |
| 16 | Evaluation Forms | Quality management forms | CreateEvaluationForm |
| 17 | Vocabularies | Custom speech recognition | CreateVocabulary |

## Key Features

### Selective Resource Replication
Choose which resource types to replicate - all, one, or many. The UI provides checkboxes for each type; the CLI can filter via code.

### ARN/ID Replacement
Automatically replaces source instance ARNs and IDs with target equivalents in flow content, ensuring cross-references work correctly.

### Two-Pass Flow Import
1. First pass: Create/update flows with module and queue references resolved
2. Second pass: Re-update flows to resolve flow-to-flow references

### Upsert Logic
- If resource exists in target (matched by name): update it (with `--overwrite`)
- If resource doesn't exist: create it
- Skips system-default resources (e.g., "Basic Hours", "BasicQueue")

## Prerequisites

- AWS credentials configured (via env vars, profile, or IAM role)
- Python 3.9+ with boto3
- Both source and target Connect instances must exist and be ACTIVE
- For prompts: an S3 bucket in the target region with appropriate permissions

## CLI Tool Location

```
tools/connect-instance-replicator/connect_instance_replicate.py
```

## Commands

### discover

List Connect instances in a region.

```bash
python3 tools/connect-instance-replicator/connect_instance_replicate.py discover --region us-east-1
```

**Example output:**
```
Found 2 instance(s):
  - my-prod-connect (ACTIVE) - arn:aws:connect:us-east-1:123456789012:instance/abc-123
  - my-test-connect (ACTIVE) - arn:aws:connect:us-east-1:123456789012:instance/def-456
```

### export

Export configuration bundle from a source instance.

```bash
python3 tools/connect-instance-replicator/connect_instance_replicate.py export \
  --source-region us-east-1 \
  --source-alias my-prod-connect \
  --output bundle.json
```

### import

Import configuration bundle into a target instance.

```bash
python3 tools/connect-instance-replicator/connect_instance_replicate.py import \
  --target-region us-west-2 \
  --target-alias my-dr-connect \
  --bundle bundle.json \
  --overwrite \
  --yes
```

### replicate (export + import in one step)

```bash
python3 tools/connect-instance-replicator/connect_instance_replicate.py replicate \
  --source-region us-east-1 \
  --source-alias my-prod-connect \
  --target-region us-west-2 \
  --target-alias my-dr-connect \
  --overwrite \
  --skip-unsupported \
  --continue-on-error \
  --yes
```

## Flags

| Flag | Description |
|------|-------------|
| `--source-region` | AWS region of source instance |
| `--source-alias` | Source instance alias (or use `--source-instance-id`) |
| `--source-instance-id` | Source instance ID (alternative to alias) |
| `--target-region` | AWS region of target instance |
| `--target-alias` | Target instance alias (or use `--target-instance-id`) |
| `--target-instance-id` | Target instance ID (alternative to alias) |
| `--overwrite` | Update existing resources in target |
| `--dry-run` | Preview without making changes |
| `--skip-unsupported` | Skip flows with external dependencies (Lambda, Lex) |
| `--continue-on-error` | Continue after individual resource errors |
| `--yes` | Confirm live changes (required for non-dry-run) |
| `--prompt-s3-bucket` | S3 bucket for copying prompt audio files |
| `--output` | Output file path for export command |
| `--bundle` | Bundle file path for import command |

## Safety Guardrails

- `--yes` is **required** for any live changes (prevents accidental modifications)
- `--dry-run` previews all operations without making changes
- Errors are logged but don't stop execution with `--continue-on-error`
- System-default resources are never modified

## Web UI

The project includes a React UI for visual replication management:

```bash
cd amazon-connect-replicator
npm install
npm run dev
# Open http://localhost:3000
```

**UI Features:**
- Region and instance selection dropdowns
- Visual resource selector grid (17 resource types)
- Select All / Select None buttons
- Bundle preview with resource counts
- Dry-run mode toggle
- Real-time import progress

## Output Artifacts

Each run writes to `~/Downloads/acr-replication-runs/<runId>/`:
- `bundle.json` — exported configuration (all 17 resource types)
- `import-report.json` — detailed import results per resource
- `verify.json` — post-import resource counts for verification

## Example Replication Report

```json
{
  "runId": "20260311T190000Z-abc123",
  "source": {
    "region": "us-east-1",
    "instanceId": "abc-123-def-456",
    "alias": "my-prod-connect"
  },
  "target": {
    "region": "us-west-2",
    "instanceId": "xyz-789-uvw-012",
    "alias": "my-dr-connect"
  },
  "results": {
    "hours": { "created": 0, "updated": 2, "skipped": 0 },
    "agentStatuses": { "created": 3, "updated": 0, "skipped": 2 },
    "securityProfiles": { "created": 0, "updated": 4, "skipped": 0 },
    "queues": { "created": 0, "updated": 6, "skipped": 1 },
    "routingProfiles": { "created": 0, "updated": 3, "skipped": 0 },
    "flowModules": { "created": 2, "updated": 5, "skipped": 0 },
    "contactFlows": { "created": 0, "updated": 21, "skipped": 0 },
    "predefinedAttributes": { "created": 5, "updated": 0, "skipped": 0 },
    "taskTemplates": { "created": 3, "updated": 0, "skipped": 0 }
  },
  "durationMs": 45230
}
```

## Disaster Recovery Use Case

For DR scenarios, pre-provision a target instance in your DR region:

1. **Setup (one-time):**
   ```bash
   # Create target instance via AWS Console or CLI
   aws connect create-instance --identity-management-type CONNECT_MANAGED \
     --instance-alias my-dr-connect --inbound-calls-enabled --outbound-calls-enabled
   ```

2. **Regular sync (scheduled or on-demand):**
   ```bash
   python3 tools/connect-instance-replicator/connect_instance_replicate.py replicate \
     --source-region us-east-1 --source-alias my-prod-connect \
     --target-region us-west-2 --target-alias my-dr-connect \
     --overwrite --yes
   ```

3. **Failover:** Update DNS/routing to point to DR instance (instance ID is already known)

## Limitations

- **Users not replicated:** Agent users must be provisioned separately (SSO/SAML considerations)
- **Phone numbers not replicated:** Must be claimed separately in target region
- **Lambda/Lex integrations:** Flows referencing external services need those services deployed in target region
- **Prompts require S3:** Audio files need an S3 bucket for cross-region copy

## GitHub Repository

https://github.com/636137/amazon-connect-replicator
