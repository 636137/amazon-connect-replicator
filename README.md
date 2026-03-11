# Amazon Connect Replicator (Primitive APIs)

A **best-effort** exporter/importer to replicate Amazon Connect configuration from a source instance (e.g., `us-east-1`) into a **pre-existing** target instance (e.g., `us-west-2`) using Connect's primitive APIs (`List*`/`Describe*` → `Create*`/`Update*`).

This repo is intentionally scoped to what Connect exposes as CRUD-style APIs; it is **not** Amazon Connect Global Resiliency.

---

## 🤖 Interactive AI Agent (Instance Manager)

The **Amazon Connect Instance Manager Agent** provides a conversational interface for complete instance management:

```
┌─────────────────────────────────────────────────────────────────────┐
│                   AGENT CAPABILITIES                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐             │
│  │   CREATE    │    │  REPLICATE  │    │  DESCRIBE   │             │
│  │             │    │             │    │             │             │
│  │ New Connect │    │ Copy config │    │ Full audit  │             │
│  │  instance   │    │ src → tgt   │    │ of instance │             │
│  │             │    │             │    │             │             │
│  └─────────────┘    └─────────────┘    └─────────────┘             │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Quick Start

```bash
# Install the agent and supporting skills
cp -r copilot-skills/connect-replication-agent ~/.copilot/skills/
cp -r copilot-skills/connect-instance-replication ~/.copilot/skills/

# Invoke in Copilot CLI
Use the connect-replication-agent skill to manage my Connect instances
```

### Agent Commands

| Action | Example Command |
|--------|-----------------|
| **Create** | `Create a new Connect instance in us-west-2` |
| **Create (named)** | `Create Connect instance my-dr-connect in us-east-1` |
| **Replicate** | `Replicate from my-prod to my-dr in us-west-2` |
| **Replicate (dry run)** | `Do a dry run replication from source to target` |
| **Describe** | `Describe my-prod-connect instance in us-east-1` |
| **Describe (audit)** | `Audit all resources in Connect instance abc-123` |
| **Discovery** | `List all Connect instances in us-east-1` |
| **Verify** | `Verify resource counts in my-dr-connect` |

See: [Full AI Agent Documentation](#copilot-ai-agent-instance-manager)

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

## Copilot AI Agent (Instance Manager)

The **connect-replication-agent** is a comprehensive Amazon Connect Instance Manager with three core capabilities.

### Installation

```bash
# Copy both skills to your Copilot skills directory
cp -r copilot-skills/connect-replication-agent ~/.copilot/skills/
cp -r copilot-skills/connect-instance-replication ~/.copilot/skills/

# Verify installation
ls ~/.copilot/skills/
# Should show: connect-replication-agent, connect-instance-replication
```

### Prerequisites

- AWS credentials configured (env vars, `~/.aws/credentials`, or IAM role)
- Python 3.9+ with boto3 installed
- This repo cloned to `~/amazon-connect-replicator`
- IAM permissions for Connect APIs (see [IAM Permissions](#iam-permissions))

---

## 1. CREATE - New Instance Creation

Create new Amazon Connect instances with guided configuration.

### CREATE Usage Examples

```
Create a new Connect instance in us-west-2
```

```
Create a Connect instance called my-dr-connect in us-east-1
```

```
Create a DR instance for my production contact center
```

### CREATE Workflow

The agent will:

1. **Ask clarifying questions:**
   - Which AWS region?
   - Instance alias (name)?
   - Identity management type? (CONNECT_MANAGED, SAML, EXISTING_DIRECTORY)
   - Enable inbound calls?
   - Enable outbound calls?
   - Enable Contact Lens?
   - Enable contact flow logs?

2. **Generate and deploy** via AWS CLI:
   ```bash
   aws connect create-instance \
     --identity-management-type CONNECT_MANAGED \
     --instance-alias my-new-instance \
     --inbound-calls-enabled \
     --outbound-calls-enabled
   ```

3. **Wait for ACTIVE status** and provide summary

### CREATE Example Session

```
User: Create a new Connect instance in us-west-2

Agent: I'll help you create a new Amazon Connect instance. Let me ask a few questions:

What should the instance alias (name) be?
> my-dr-connect

What identity management type?
  1. CONNECT_MANAGED (recommended for quick setup)
  2. SAML (for SSO integration)
  3. EXISTING_DIRECTORY (for Active Directory)
> 1

Enable inbound calls? (Yes/No)
> Yes

Enable outbound calls? (Yes/No)
> Yes

Enable Contact Lens for analytics? (Yes/No)
> Yes

Creating instance with these settings:
  - Region: us-west-2
  - Alias: my-dr-connect
  - Identity: CONNECT_MANAGED
  - Inbound: Yes
  - Outbound: Yes
  - Contact Lens: Yes

Proceed? (Yes/No)
> Yes

Creating instance... ⏳

✅ Instance Created Successfully!

Instance Details:
  - ID: 07eadde0-065b-4a96-ab60-d5a18aaa5a72
  - ARN: arn:aws:connect:us-west-2:123456789012:instance/07eadde0-...
  - Alias: my-dr-connect
  - Status: ACTIVE
  - Access URL: https://my-dr-connect.my.connect.aws

Next Steps:
1. Claim phone numbers
2. Create users and security profiles
3. Build contact flows
4. Or replicate configuration from an existing instance

What would you like to do next?
```

### CREATE CloudFormation Template

The agent can also generate CloudFormation:

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: Amazon Connect Instance

Parameters:
  InstanceAlias:
    Type: String
    Description: Unique alias for the Connect instance

Resources:
  ConnectInstance:
    Type: AWS::Connect::Instance
    Properties:
      IdentityManagementType: CONNECT_MANAGED
      InstanceAlias: !Ref InstanceAlias
      Attributes:
        InboundCalls: true
        OutboundCalls: true
        ContactflowLogs: true
        ContactLens: true
        AutoResolveBestVoices: true
        UseCustomTTSVoices: false
        EarlyMedia: true

Outputs:
  InstanceId:
    Value: !Ref ConnectInstance
  InstanceArn:
    Value: !GetAtt ConnectInstance.Arn
```

---

## 2. REPLICATE - Cross-Region Configuration Sync

Replicate all 19 resource types from a source instance to a target instance.

### REPLICATE Usage Examples

```
Replicate Connect instance from us-east-1 to us-west-2
```

```
Replicate from my-prod-connect to my-dr-connect
```

```
Sync configuration from source to target instance
```

```
Do a dry run replication to preview changes
```

### REPLICATE Workflow

1. **Discover instances** in source and target regions
2. **Ask clarifying questions:**
   - Confirm source instance
   - Confirm target instance
   - Overwrite existing resources?
   - Skip unsupported flows (Lambda/Lex dependencies)?
   - Continue on individual errors?
3. **Execute replication** with progress updates
4. **Provide detailed summary** with source vs target comparison

### REPLICATE Example Session

```
User: Replicate my Connect instance from us-east-1 to us-west-2

Agent: Let me discover the available Connect instances...

Found in us-east-1:
  1. my-prod-connect (ACTIVE)
  2. my-test-connect (ACTIVE)

Found in us-west-2:
  1. my-dr-connect (ACTIVE)

Which instance should be the SOURCE?
> my-prod-connect

Which instance should be the TARGET?
> my-dr-connect

Should I overwrite existing resources? (Yes/No)
> Yes

Should I skip flows with unsupported dependencies? (Yes/No)
> Yes

Proceeding with replication...

✅ Replication Complete!

| Resource Type         | Source | Target | Status |
|-----------------------|--------|--------|--------|
| Hours of Operation    | 2      | 2      | ✅     |
| Agent Statuses        | 2      | 2      | ✅     |
| Security Profiles     | 4      | 4      | ✅     |
| Queues                | 6      | 6      | ✅     |
| Routing Profiles      | 3      | 3      | ✅     |
| Contact Flows         | 15     | 15     | ✅     |
| Prompts               | 7      | 7      | ✅     |
| ...                   | ...    | ...    | ...    |

Artifacts saved to: ~/Downloads/acr-replication-runs/20260311T211921Z-abc123/

What would you like to do next?
```

### REPLICATE CLI Flags

| Flag | Description |
|------|-------------|
| `--source-region` | AWS region of source instance |
| `--source-alias` | Source instance alias (or use `--source-instance-id`) |
| `--target-region` | AWS region of target instance |
| `--target-alias` | Target instance alias (or use `--target-instance-id`) |
| `--overwrite` | Update existing resources in target |
| `--dry-run` | Preview without making changes |
| `--skip-unsupported` | Skip flows with external dependencies |
| `--continue-on-error` | Continue after individual resource errors |
| `--yes` | Confirm live changes (required for non-dry-run) |
| `--copy-lambda` | Copy Lambda functions to target region |
| `--copy-lex` | Copy Lex V2 bots to target region |

---

## 3. DESCRIBE - Full Instance Audit

Get complete details of all 19 resource types in a Connect instance.

### DESCRIBE Usage Examples

```
Describe my-prod-connect instance
```

```
Show all details of Connect instance in us-east-1
```

```
Audit the Connect instance acr-repl-test-ozqb6i2i
```

```
What resources are in my Connect instance?
```

### DESCRIBE Workflow

1. **Identify the instance** (by alias or ID, in specified region)
2. **Query all 19 resource types** via Connect APIs
3. **Present comprehensive summary**

### DESCRIBE Example Session

```
User: Describe my Connect instance my-prod-connect in us-east-1

Agent: Let me gather complete details for my-prod-connect...

═══════════════════════════════════════════════════════════════════
                    CONNECT INSTANCE DETAILS
═══════════════════════════════════════════════════════════════════

INSTANCE METADATA
─────────────────────────────────────────────────────────────────────
  Alias:           my-prod-connect
  ID:              be2975f8-7533-4c8c-b252-0f76ea9060da
  ARN:             arn:aws:connect:us-east-1:123456789012:instance/be2975f8-...
  Region:          us-east-1
  Status:          ACTIVE
  Created:         2026-02-15T10:30:00Z
  Identity Type:   CONNECT_MANAGED

INSTANCE ATTRIBUTES
─────────────────────────────────────────────────────────────────────
  Inbound Calls:              ✅ Enabled
  Outbound Calls:             ✅ Enabled
  Contact Flow Logs:          ✅ Enabled
  Contact Lens:               ✅ Enabled
  Auto Resolve Best Voices:   ✅ Enabled
  Early Media:                ✅ Enabled
  Multi-Party Conference:     ❌ Disabled
  High Volume Outbound:       ❌ Disabled

RESOURCE COUNTS (19 Types)
─────────────────────────────────────────────────────────────────────
  Hours of Operation:      2
  Agent Statuses:          2 (Available, Offline - system defaults)
  Security Profiles:       4 (Admin, Agent, CallCenterManager, QualityAnalyst)
  User Hierarchy Groups:   0
  Queues (STANDARD):       4 (BasicQueue, Sales, Support, Billing)
  Routing Profiles:        4 (Basic, Sales, Support, Escalation)
  Quick Connects:          0
  Contact Flow Modules:    0
  Contact Flows:           20
  Predefined Attributes:   14 (system attributes)
  Prompts:                 7
  Task Templates:          1
  Views:                   5
  Rules:                   0
  Evaluation Forms:        0
  Vocabularies:            0
  Lambda Functions:        0
  Lex Bots:                0

CONTACT FLOWS (20)
─────────────────────────────────────────────────────────────────────
  CONTACT_FLOW (10):
    • Default agent transfer
    • Default customer queue
    • Main IVR Flow
    • Sales Routing
    • Support Routing
    ...
  
  CUSTOMER_QUEUE (3):
    • Default customer queue
    • Priority Queue Flow
    • Callback Queue Flow

QUEUES (4)
─────────────────────────────────────────────────────────────────────
  • BasicQueue (Hours: Basic Hours)
  • Sales (Hours: Sales Hours)
  • Support (Hours: 24/7 Support)
  • Billing (Hours: Business Hours)

PROMPTS (7)
─────────────────────────────────────────────────────────────────────
  • Beep.wav
  • CustomerHold.wav
  • CustomerQueue.wav
  • Music_Jazz_MyTimetoFly_Inst.wav
  • Music_Pop_ThisAndThatIsLife_Inst.wav
  • Music_Pop_ThrowYourselfInFrontOfIt_Inst.wav
  • Music_Rock_EverywhereTheSunShines_Inst.wav

═══════════════════════════════════════════════════════════════════

Would you like more details on any specific resource type?
  1. List all contact flows with descriptions
  2. Show security profile permissions
  3. View routing profile queue assignments
  4. Export full configuration to JSON
```

---

## Agent Troubleshooting

The agent handles common issues automatically:

| Issue | Agent Response |
|-------|----------------|
| **Instance not found** | Lists available instances, asks user to select |
| **Permission denied** | Checks credentials, suggests required IAM permissions |
| **Instance creation failed** | Explains error (quota limit, naming conflict, invalid region) |
| **Resource creation failed** | Explains specific error, suggests workarounds |
| **Unsupported dependencies** | Lists flows with Lambda/Lex/prompt refs, offers to skip |
| **Region not supported** | Lists supported Connect regions |
| **Quota exceeded** | Shows current usage vs limits |

---

## Output Artifacts

Each replication run saves artifacts to `~/Downloads/acr-replication-runs/<runId>/`:

| File | Description |
|------|-------------|
| `bundle.json` | Exported configuration (all 19 resource types) |
| `import-report.json` | Detailed import results per resource |
| `verify.json` | Post-import resource counts for verification |

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

---

## IAM Permissions

### Minimum Permissions for Replication

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ConnectReadSource",
      "Effect": "Allow",
      "Action": [
        "connect:List*",
        "connect:Describe*",
        "connect:Get*",
        "connect:Search*"
      ],
      "Resource": "arn:aws:connect:*:*:instance/*"
    },
    {
      "Sid": "ConnectWriteTarget",
      "Effect": "Allow",
      "Action": [
        "connect:Create*",
        "connect:Update*",
        "connect:Associate*"
      ],
      "Resource": "arn:aws:connect:*:*:instance/*"
    }
  ]
}
```

### Additional Permissions for Instance Creation

```json
{
  "Sid": "ConnectInstanceManagement",
  "Effect": "Allow",
  "Action": [
    "connect:CreateInstance",
    "connect:DeleteInstance",
    "connect:DescribeInstance",
    "connect:ListInstances"
  ],
  "Resource": "*"
}
```

### Additional Permissions for Prompt S3 Copy

```json
{
  "Sid": "S3PromptCopy",
  "Effect": "Allow",
  "Action": [
    "s3:GetObject",
    "s3:PutObject"
  ],
  "Resource": [
    "arn:aws:s3:::source-bucket/*",
    "arn:aws:s3:::target-bucket/*"
  ]
}
```

---

## Disaster Recovery Use Case

For DR scenarios, use the agent to set up and maintain a standby instance:

### Initial Setup

```
User: Create a DR instance for my production contact center

Agent: I'll help you create a DR instance. Let me ask a few questions...
[Guided instance creation]

User: Now replicate configuration from my-prod-connect to the new DR instance

Agent: Replicating 19 resource types...
[Detailed replication with summary]
```

### Regular Sync (Scheduled)

```bash
# Add to cron or scheduled task
python3 ~/.copilot/skills/connect-instance-replication/scripts/connect_instance_replication.py replicate \
  --source-region us-east-1 --source-alias my-prod-connect \
  --target-region us-west-2 --target-alias my-dr-connect \
  --overwrite --skip-unsupported --continue-on-error --yes
```

### Failover Checklist

1. ✅ DR instance is ACTIVE (verify with `Describe my-dr-connect`)
2. ✅ Configuration is synced (verify resource counts match)
3. ✅ Phone numbers claimed in DR region
4. ✅ Update DNS/routing to point to DR instance
5. ✅ Notify agents to log into DR instance

---

## Supported AWS Regions

Amazon Connect is available in these regions:

| Region | Name |
|--------|------|
| us-east-1 | US East (N. Virginia) |
| us-west-2 | US West (Oregon) |
| eu-west-2 | Europe (London) |
| eu-central-1 | Europe (Frankfurt) |
| ap-southeast-1 | Asia Pacific (Singapore) |
| ap-southeast-2 | Asia Pacific (Sydney) |
| ap-northeast-1 | Asia Pacific (Tokyo) |
| ap-northeast-2 | Asia Pacific (Seoul) |
| ca-central-1 | Canada (Central) |
| af-south-1 | Africa (Cape Town) |

---

## References

- [Amazon Connect Admin Guide](https://docs.aws.amazon.com/connect/latest/adminguide/)
- [Contact Flow Import/Export](https://docs.aws.amazon.com/connect/latest/adminguide/contact-flow-import-export.html)
- [Connect API Reference](https://docs.aws.amazon.com/connect/latest/APIReference/API_Operations_Amazon_Connect_Service.html)
- [Best Practices for Connect APIs](https://docs.aws.amazon.com/connect/latest/APIReference/best-practices-connect-apis.html)
- [Connect CloudFormation Reference](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/AWS_Connect.html)

---

## Repository Structure

```
amazon-connect-replicator/
├── README.md                              # This file
├── package.json                           # Node.js dependencies
├── packages/
│   ├── api/                               # Express API server
│   │   └── src/
│   │       └── routes/connect.ts          # Connect API endpoints
│   └── ui/                                # React UI
│       └── src/
│           └── components/                # UI components
├── tools/
│   └── connect-instance-replicator/       # Python CLI (main tool)
│       ├── README.md
│       └── connect_instance_replicate.py  # Export/import logic
└── copilot-skills/
    ├── connect-instance-replication/      # Copilot skill wrapper
    │   ├── SKILL.md
    │   └── scripts/
    │       └── connect_instance_replication.py
    └── connect-replication-agent/         # Interactive AI agent
        └── SKILL.md                       # Agent definition
```

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests (if applicable)
5. Submit a pull request

---

## License

MIT License - see LICENSE file for details.
