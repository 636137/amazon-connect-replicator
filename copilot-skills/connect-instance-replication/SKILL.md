---
name: connect-instance-replication
description: Replicate Amazon Connect instance configuration across regions using primitive APIs. Exports/imports 19 resource types including Lambda/Lex with automatic ARN replacement and optional cross-region copy.
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

## Bundle v3.2 Scope (19 resource types)

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
| 7a | **Prompts** | Audio prompts (with S3 copy) | CreatePrompt |
| 8 | Contact Flow Modules | Reusable flow components | CreateContactFlowModule / UpdateContactFlowModuleContent |
| 9 | Contact Flows | IVR and routing logic | CreateContactFlow / UpdateContactFlowContent |
| 10 | Instance Attributes | Instance-level settings | UpdateInstanceAttribute |
| 11 | Predefined Attributes | Contact attribute definitions | CreatePredefinedAttribute / UpdatePredefinedAttribute |
| 12 | Task Templates | Structured task definitions | CreateTaskTemplate / UpdateTaskTemplate |
| 13 | Views | Custom agent UI views | CreateView / UpdateViewContent |
| 14 | Rules | Automation rules and triggers | CreateRule / UpdateRule |
| 15 | Evaluation Forms | Quality management forms | CreateEvaluationForm |
| 16 | Vocabularies | Custom speech recognition | CreateVocabulary |
| 17 | **Lambda Functions** | Serverless integrations | ListLambdaFunctions / AssociateLambdaFunction |
| 18 | **Lex Bots (V1/V2)** | Conversational AI bots | ListBots / AssociateBot / AssociateLexBot |

**Note:** Prompts are processed at step 7a (before flows) to ensure prompt ARN replacements are available when processing flow content.

## Key Features

### Lambda & Lex Auto-Discovery
Automatically discovers Lambda functions and Lex bots associated with the source instance using:
- `ListLambdaFunctions` - Gets all Lambda ARNs configured for flows
- `ListBots` (V1 and V2) - Gets all Lex bot associations

### Cross-Region Lambda/Lex Copy (NEW in v3.2)
Optionally copy Lambda functions and Lex bots to the target region:
- `--copy-lambda` - Downloads function code and creates in target region
- `--copy-lex` - Exports Lex V2 bot definition and imports to target region

**Note:** IAM roles referenced by Lambda/Lex must exist in the target account.

### Cross-Region ARN Replacement
When replicating across regions, automatically rewrites ARNs in flow content:
```
arn:aws:lambda:us-east-1:123456789012:function:MyFunc
                ↓
arn:aws:lambda:us-west-2:123456789012:function:MyFunc
```

### Prompt ARN Mapping
Maps prompts by name between source and target instances:
```
arn:aws:connect:us-east-1:123456:instance/SRC-ID/prompt/abc123
                        ↓
arn:aws:connect:us-west-2:123456:instance/TGT-ID/prompt/xyz789
```

### Auto-Association
Associates Lambda functions and Lex bots with the target instance so they appear in flow designer dropdowns.

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
| `--skip-unsupported` | Skip flows with external dependencies that can't be resolved |
| `--continue-on-error` | Continue after individual resource errors |
| `--yes` | Confirm live changes (required for non-dry-run) |
| `--prompt-s3-bucket` | S3 bucket for copying prompt audio files |
| `--copy-lambda` | **NEW** Copy Lambda functions from source to target region |
| `--copy-lex` | **NEW** Copy Lex V2 bots from source to target region |
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
- Visual resource selector grid (19 resource types)
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
    "taskTemplates": { "created": 3, "updated": 0, "skipped": 0 },
    "lambdaFunctions": { "associated": 2, "skipped": 1, "failed": 0 },
    "lexBots": { "associated": 1, "skipped": 0, "failed": 0 }
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

2. **Deploy Lambda/Lex in target region:**
   ```bash
   # Lambda functions must exist in target region with same name
   # Lex bots must be deployed in target region with same bot ID
   ```

3. **Regular sync (scheduled or on-demand):**
   ```bash
   python3 tools/connect-instance-replicator/connect_instance_replicate.py replicate \
     --source-region us-east-1 --source-alias my-prod-connect \
     --target-region us-west-2 --target-alias my-dr-connect \
     --overwrite --yes
   ```

4. **Failover:** Update DNS/routing to point to DR instance (instance ID is already known)

## Lambda/Lex Replication Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        EXPORT PHASE                                  │
├─────────────────────────────────────────────────────────────────────┤
│  1. ListLambdaFunctions → Discovers Lambda ARNs                     │
│  2. ListBots (V1/V2)    → Discovers Lex bot associations            │
│  3. Export contact flows with embedded Lambda/Lex ARNs              │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                        IMPORT PHASE                                  │
├─────────────────────────────────────────────────────────────────────┤
│  1. Build ARN replacement map (source region → target region)       │
│  2. AssociateLambdaFunction → Register Lambda with target instance  │
│  3. AssociateBot / AssociateLexBot → Register Lex with target       │
│  4. Apply ARN replacements to all flow content                      │
│  5. Create/Update flows with corrected ARNs                         │
└─────────────────────────────────────────────────────────────────────┘
```

## Prerequisites for Lambda/Lex

For Lambda and Lex replication to succeed:

1. **Lambda functions must exist in target region** with the same function name
   - Deploy using SAM, CDK, or CloudFormation multi-region
   - ARN changes only in the region portion

2. **Lex V2 bots must exist in target region** with the same bot ID and alias ID
   - Use Lex bot versioning and multi-region deployment
   - Bot alias ARN changes only in the region portion

3. **Lex V1 bots** (legacy) must be available in target region

## Limitations

- **Users not replicated:** Agent users must be provisioned separately (SSO/SAML considerations)
- **Phone numbers not replicated:** Must be claimed separately in target region
- **Lambda/Lex must pre-exist:** The replicator associates and rewrites ARNs, but does NOT deploy Lambda/Lex resources
- **Prompts require S3:** Audio files need an S3 bucket for cross-region copy

## GitHub Repository

https://github.com/636137/amazon-connect-replicator
