---
name: connect-replication-agent
description: Interactive AI agent for Amazon Connect instance management. Create new instances, replicate configuration across regions, or describe instance details. Guides users with clarifying questions, troubleshoots issues, and provides detailed summaries.
user-invocable: true
disable-model-invocation: false
---

# Amazon Connect Instance Manager Agent

An interactive AI agent for comprehensive Amazon Connect instance management:

1. **Create** new Connect instances with guided configuration
2. **Replicate** configuration from one instance to another (same or cross-region)
3. **Describe** complete details of any Connect instance (all 19 resource types)

## Capabilities Overview

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

---

## 1. CREATE - New Instance Creation

Create a new Amazon Connect instance with guided configuration.

### Usage Examples

```
Create a new Connect instance in us-west-2
```

```
Create a Connect instance called my-new-instance in us-east-1
```

```
Create a DR instance for my production contact center
```

### Agent Workflow for CREATE

1. **Ask clarifying questions:**
   - Which AWS region?
   - Instance alias (name)?
   - Identity management type? (CONNECT_MANAGED, SAML, etc.)
   - Enable inbound calls?
   - Enable outbound calls?
   - Enable Contact Lens?
   - Enable contact flow logs?

2. **Generate CloudFormation template:**
   ```yaml
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
           EarlyMedia: true
   ```

3. **Deploy via CloudFormation or AWS CLI:**
   ```bash
   aws connect create-instance \
     --identity-management-type CONNECT_MANAGED \
     --instance-alias my-new-instance \
     --inbound-calls-enabled \
     --outbound-calls-enabled
   ```

4. **Wait for instance to become ACTIVE**

5. **Provide summary:**
   - Instance ID
   - Instance ARN
   - Access URL
   - Next steps (claim phone numbers, create users, etc.)

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
  - ARN: arn:aws:connect:us-west-2:123456789012:instance/07eadde0-065b-4a96-ab60-d5a18aaa5a72
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

---

## 2. REPLICATE - Cross-Region Configuration Sync

Replicate all 19 resource types from a source instance to a target instance.

### Usage Examples

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

### Agent Workflow for REPLICATE

1. **Discover instances** in source and target regions
2. **Ask clarifying questions:**
   - Confirm source instance
   - Confirm target instance
   - Overwrite existing resources?
   - Skip unsupported flows (Lambda/Lex dependencies)?
   - Continue on individual errors?
3. **Execute replication** with progress updates
4. **Provide detailed summary** with source vs target comparison

### Supported Resource Types (19)

| # | Resource Type | Description |
|---|---------------|-------------|
| 1 | Hours of Operation | Business hours schedules |
| 2 | Agent Statuses | Custom agent availability states |
| 3 | Security Profiles | Permission sets for agents |
| 4 | User Hierarchy Groups | Agent organizational hierarchy |
| 5 | Queues (STANDARD) | Call/chat routing queues |
| 6 | Routing Profiles | Queue priority assignments |
| 7 | Quick Connects | One-click transfer destinations |
| 8 | Contact Flow Modules | Reusable flow components |
| 9 | Contact Flows | IVR and routing logic |
| 10 | Instance Attributes | Instance-level settings |
| 11 | Predefined Attributes | Contact attribute definitions |
| 12 | Prompts | Audio prompts (mapped by name) |
| 13 | Task Templates | Structured task definitions |
| 14 | Views | Custom agent UI views |
| 15 | Rules | Automation rules and triggers |
| 16 | Evaluation Forms | Quality management forms |
| 17 | Vocabularies | Custom speech recognition |
| 18 | Lambda Functions | Serverless integrations (ARN mapping) |
| 19 | Lex Bots | Conversational AI bots (ARN mapping) |

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

What would you like to do next?
```

---

## 3. DESCRIBE - Full Instance Audit

Get complete details of all 19 resource types in a Connect instance.

### Usage Examples

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

### Agent Workflow for DESCRIBE

1. **Identify the instance** (by alias or ID, in specified region)
2. **Query all 19 resource types** via Connect APIs
3. **Present comprehensive summary:**
   - Instance metadata (ID, ARN, status, created date)
   - Resource counts for all 19 types
   - Detailed listings for each resource type (optional)

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
    • After Hours Flow
    • Holiday Flow
    • Callback Flow
    • Survey Flow
    • Emergency Closure
  
  CUSTOMER_QUEUE (3):
    • Default customer queue
    • Priority Queue Flow
    • Callback Queue Flow
  
  CUSTOMER_WHISPER (2):
    • Default customer whisper
    • VIP Customer Whisper
  
  AGENT_WHISPER (2):
    • Default agent whisper
    • Screen Pop Whisper
  
  CUSTOMER_HOLD (2):
    • Default customer hold
    • Music On Hold
  
  AGENT_HOLD (1):
    • Default agent hold

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

## Commands Summary

| Command Type | Example |
|--------------|---------|
| **Create** | `Create a new Connect instance in us-west-2` |
| **Create (named)** | `Create Connect instance my-dr-connect in us-east-1` |
| **Replicate** | `Replicate from my-prod to my-dr in us-west-2` |
| **Replicate (dry run)** | `Do a dry run replication from source to target` |
| **Describe** | `Describe my-prod-connect instance in us-east-1` |
| **Describe (audit)** | `Audit all resources in Connect instance abc-123` |
| **Discovery** | `List all Connect instances in us-east-1` |
| **Verify** | `Verify resource counts in my-dr-connect` |

## Troubleshooting

| Issue | Agent Response |
|-------|----------------|
| Instance not found | Lists available instances, asks user to select |
| Permission denied | Checks credentials, suggests IAM permissions |
| Instance creation failed | Explains error (quota, naming conflict, etc.) |
| Resource creation failed | Explains specific error, suggests workarounds |
| Unsupported dependencies | Lists flows with Lambda/Lex, offers to skip |
| Region not supported | Lists supported Connect regions |

## Tools Used

This agent uses:

1. **connect_instance_replication.py** - Skill wrapper for discovery, replication, verification
   - Location: `~/.copilot/skills/connect-instance-replication/scripts/`

2. **amazon-connect-builder skill** - For instance creation and CloudFormation
   - Location: `~/.copilot/skills/amazon-connect-builder/`

3. **AWS CLI / boto3** - Direct API calls for:
   - `aws connect create-instance`
   - `aws connect describe-instance`
   - `aws connect list-*` (all 19 resource types)

## Prerequisites

- AWS credentials configured (env vars, profile, or IAM role)
- Python 3.9+ with boto3
- Skills installed:
  - `~/.copilot/skills/connect-instance-replication/`
  - `~/.copilot/skills/amazon-connect-builder/`

## GitHub Repository

https://github.com/636137/amazon-connect-replicator
