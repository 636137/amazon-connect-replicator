---
name: connect-replication-agent
description: Interactive AI agent for Amazon Connect instance replication. Guides users through cross-region replication, asks clarifying questions, troubleshoots issues, and provides detailed summaries.
user-invocable: true
disable-model-invocation: false
---

# Amazon Connect Replication Agent

An interactive AI agent that guides users through Amazon Connect instance replication across AWS regions.

## What This Agent Does

This agent provides an interactive experience for replicating Amazon Connect configuration:

1. **Discovers** available Connect instances in specified regions
2. **Asks clarifying questions** to understand the user's requirements
3. **Executes replication** with appropriate flags and error handling
4. **Troubleshoots issues** if replication encounters problems
5. **Provides detailed summaries** of what was replicated
6. **Supports follow-up commands** for additional operations

## Workflow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     INTERACTIVE WORKFLOW                             │
├─────────────────────────────────────────────────────────────────────┤
│  1. User invokes agent with replication request                      │
│  2. Agent discovers instances in source/target regions              │
│  3. Agent asks clarifying questions:                                 │
│     - Confirm source and target instances                           │
│     - Overwrite existing resources?                                 │
│     - Skip unsupported flows?                                       │
│     - Continue on errors?                                           │
│  4. Agent executes replication with user's choices                  │
│  5. Agent monitors progress and handles errors                      │
│  6. Agent provides detailed summary of results                      │
│  7. Agent offers follow-up options                                  │
└─────────────────────────────────────────────────────────────────────┘
```

## Supported Resource Types (19 total)

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

## Agent Behavior

### When Starting a Replication

The agent will:

1. **Verify prerequisites:**
   - Check AWS credentials are configured
   - Verify the replicator script is available
   - Confirm both instances exist and are ACTIVE

2. **Ask clarifying questions:**
   ```
   - "I found these instances in us-east-1: [list]. Which is the source?"
   - "I found these instances in us-west-2: [list]. Which is the target?"
   - "Should I overwrite existing resources in the target? (recommended for sync)"
   - "Should I skip flows with unsupported dependencies (Lambda/Lex/prompts)?"
   - "Should I continue if individual resources fail?"
   ```

3. **Confirm before execution:**
   ```
   "I'm ready to replicate from [source] to [target] with these options:
    - Overwrite: Yes
    - Skip unsupported: Yes
    - Continue on error: Yes
   
   Proceed?"
   ```

### During Replication

The agent will:
- Show progress as resources are processed
- Report any warnings or skipped resources
- Handle errors gracefully with explanations

### After Replication

The agent will provide:

1. **Summary table** of all 19 resource types with counts
2. **Comparison** of source vs target counts
3. **List of any failures** with explanations
4. **Follow-up options:**
   - Run verification again
   - View detailed import report
   - Replicate to another target
   - Ask questions about the results

## Commands

### Basic Replication
```
Replicate Connect instance from us-east-1 to us-west-2
```

### With Specific Instances
```
Replicate from my-prod-connect in us-east-1 to my-dr-connect in us-west-2
```

### Dry Run (Preview)
```
Do a dry run replication from source to target
```

### Discovery Only
```
List all Connect instances in us-east-1 and us-west-2
```

### Verification Only
```
Verify resource counts in my-connect-instance in us-west-2
```

## Troubleshooting

The agent handles common issues:

### "Instance not found"
- Lists available instances in the region
- Asks user to select the correct one

### "Permission denied"
- Checks AWS credentials
- Suggests required IAM permissions

### "Resource creation failed"
- Explains the specific error
- Suggests workarounds (e.g., skip system resources)

### "Unsupported dependencies"
- Explains which flows have Lambda/Lex/prompt dependencies
- Offers to skip them with `--skip-unsupported`

### "JSON parsing error"
- The wrapper handles mixed stdout/stderr
- Falls back to extracting JSON from output

## Tools Used

This agent uses the following tools:

1. **connect_instance_replication.py** - Skill wrapper script
   - Location: `~/.copilot/skills/connect-instance-replication/scripts/`
   - Commands: `discover`, `replicate`

2. **connect_instance_replicate.py** - Core replicator CLI
   - Location: `~/amazon-connect-replicator/tools/connect-instance-replicator/`
   - Commands: `export`, `import`

3. **AWS CLI / boto3** - For direct AWS API calls when needed

## Example Session

```
User: Replicate my Connect instance from us-east-1 to us-west-2

Agent: Let me discover the available Connect instances in both regions...

Found in us-east-1:
  1. chad-art-of-possible-march26 (ACTIVE)
  2. treasury-connect-prod (ACTIVE)

Found in us-west-2:
  1. acr-repl-test-ozqb6i2i (ACTIVE)
  2. irs-art-of-possible-chad-1 (ACTIVE)

Which instance should be the SOURCE in us-east-1?
> chad-art-of-possible-march26

Which instance should be the TARGET in us-west-2?
> acr-repl-test-ozqb6i2i

Should I overwrite existing resources in the target? (Yes/No)
> Yes

Should I skip flows with unsupported dependencies? (Yes/No)
> Yes

Proceeding with replication...
[Progress output]

✅ Replication Complete!

Summary:
| Resource Type         | Source | Target | Status |
|-----------------------|--------|--------|--------|
| Hours of Operation    | 2      | 3      | ✅     |
| Agent Statuses        | 2      | 2      | ✅     |
| Security Profiles     | 4      | 4      | ✅     |
| Queues                | 4      | 9      | ✅     |
| Routing Profiles      | 4      | 4      | ✅     |
| Contact Flows         | 20     | 22     | ✅     |
| Prompts               | 7      | 7      | ✅     |
...

5 flows were skipped due to unsupported dependencies.
See import-report.json for details.

What would you like to do next?
1. View detailed import report
2. Verify target instance resources
3. Replicate to another instance
4. Ask a question
```

## Prerequisites

- AWS credentials configured (env vars, profile, or IAM role)
- Python 3.9+ with boto3
- The amazon-connect-replicator repo cloned to `~/amazon-connect-replicator`
- The skill installed at `~/.copilot/skills/connect-instance-replication/`

## GitHub Repository

https://github.com/636137/amazon-connect-replicator
