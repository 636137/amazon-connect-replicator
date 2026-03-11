---
name: connect-campaign-agent
description: Interactive AI agent for building intelligent Amazon Connect outbound campaigns. Create AI-powered customer segments, configure compliant multi-channel campaigns (voice, SMS, email), personalize outreach with Bedrock, deploy via API or CloudFormation, and monitor with Contact Lens analytics. Supports predictive, progressive, preview, and agentless dialers.
user-invocable: true
disable-model-invocation: false
---

# Amazon Connect Smart Campaign Agent

An interactive AI agent for building and managing intelligent outbound campaigns in Amazon Connect. The agent guides users through the complete campaign lifecycle:

**SEGMENT → CREATE → PERSONALIZE → DEPLOY → MONITOR → OPTIMIZE**

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      SMART CAMPAIGN AGENT                                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌──────────┐         │
│  │ SEGMENT  │→ │  CREATE  │→ │PERSONALIZE│→ │  DEPLOY  │→ │ MONITOR  │         │
│  │          │  │          │  │           │  │          │  │          │         │
│  │ Build AI │  │ Campaign │  │ Bedrock   │  │ API/CFn  │  │ Contact  │         │
│  │ segments │  │  config  │  │  scripts  │  │  deploy  │  │  Lens    │         │
│  └──────────┘  └──────────┘  └───────────┘  └──────────┘  └──────────┘         │
│       │              │              │              │              │             │
│       ▼              ▼              ▼              ▼              ▼             │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌──────────┐         │
│  │Customer  │  │Outbound  │  │  Amazon   │  │CloudForm │  │Analytics │         │
│  │Profiles  │  │Campaigns │  │  Bedrock  │  │ation/API │  │Dashboard │         │
│  │  API     │  │ V2 API   │  │   API     │  │          │  │          │         │
│  └──────────┘  └──────────┘  └───────────┘  └──────────┘  └──────────┘         │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Capabilities Overview

| Module | Description | Key Features |
|--------|-------------|--------------|
| **DISCOVER** | Find instances, campaigns, segments | List resources, get details |
| **SEGMENT** | Build customer segments | AI-powered natural language, Spark SQL, calculated attributes |
| **CREATE** | Configure campaigns | 4 dialer modes, multi-channel, compliance settings |
| **PERSONALIZE** | Generate outreach content | Bedrock scripts, customer summaries, dynamic messages |
| **DEPLOY** | Launch campaigns | API deployment, CloudFormation IaC, lifecycle management |
| **MONITOR** | Track performance | Contact Lens analytics, real-time metrics, sentiment analysis |
| **OPTIMIZE** | Improve results | AI recommendations, A/B testing, conversion optimization |

---

## 1. DISCOVER - Resource Discovery

Find and list Amazon Connect resources for campaign management.

### Usage Examples

```
List all Connect instances
```

```
Show campaigns in my-prod-connect instance
```

```
List customer segments in us-east-1
```

```
Describe campaign Spring-Promo-2026
```

### Agent Workflow for DISCOVER

1. **List instances** in specified region(s)
2. **List campaigns** for selected instance
3. **List segments** in Customer Profiles domain
4. **Show detailed information** for selected resources

### DISCOVER Example Session

```
User: Show me all campaigns in my Connect instance

Agent: Let me discover your Connect instances first...

Found instances in us-east-1:
  1. my-prod-connect (ACTIVE)
  2. my-test-connect (ACTIVE)

Which instance would you like to view campaigns for?
> my-prod-connect

Fetching campaigns for my-prod-connect...

═══════════════════════════════════════════════════════════════════
                    CAMPAIGNS OVERVIEW
═══════════════════════════════════════════════════════════════════

Active Campaigns (2):
  1. Spring-Promotion-2026
     - Type: AGENT_ASSISTED (Predictive)
     - Channel: Voice
     - Status: RUNNING
     - Contacts Today: 1,247
     - Connect Rate: 34.2%

  2. Payment-Reminders
     - Type: AGENTLESS
     - Channel: Voice + SMS
     - Status: RUNNING
     - Messages Sent: 5,892
     - Delivery Rate: 98.1%

Paused Campaigns (1):
  3. Collections-Q1
     - Type: AGENT_ASSISTED (Preview)
     - Channel: Voice
     - Status: PAUSED
     - Reason: Pending compliance review

Scheduled Campaigns (1):
  4. Memorial-Day-Sale
     - Type: AGENT_ASSISTED (Progressive)
     - Scheduled Start: 2026-05-25 08:00 ET

Would you like details on any specific campaign?
```

---

## 2. SEGMENT - AI-Powered Customer Segmentation

Build intelligent customer segments using natural language, Spark SQL, or calculated attributes.

### Usage Examples

```
Create a segment of high-value customers who haven't purchased in 60 days
```

```
Build a segment for overdue accounts with balance over $500
```

```
Create a retention segment for customers with declining engagement
```

```
Show me customers likely to churn based on support contact frequency
```

### Segmentation Methods

| Method | Best For | Technical Approach |
|--------|----------|-------------------|
| **Natural Language** | Business users | AI translates to Spark SQL |
| **Spark SQL** | Data analysts | Direct SQL queries |
| **Calculated Attributes** | Real-time metrics | Pre-computed values |
| **Audience Groups** | Simple filters | UI-based filtering |

### Agent Workflow for SEGMENT

1. **Understand objective** - What customer behavior to target?
2. **Identify attributes** - Which profile fields to use?
3. **Generate query** - Create Spark SQL or filter definition
4. **Preview segment** - Show estimated audience size
5. **Deploy segment** - Create in Customer Profiles

### SEGMENT Example Session

```
User: Create a segment of high-value customers who haven't ordered in 60 days

Agent: I'll help you build that segment. Let me check your Customer Profiles domain...

✅ Found Customer Profiles domain: my-domain-xyz

Let me ask a few clarifying questions:

1. How do you define "high-value"?
   a) Lifetime value > $10,000
   b) Top 10% of spenders
   c) Custom threshold
> a

2. Should I include customers with open support tickets?
   a) Yes, include all
   b) No, exclude customers with active issues
   c) Only include if ticket is resolved
> c

3. What channels have these customers used?
   a) Any channel
   b) Voice customers only
   c) Digital customers only (chat/email)
> a

Generating Spark SQL segment definition...

┌─────────────────────────────────────────────────────────────────────┐
│ SEGMENT: high_value_dormant_60d                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ SELECT *                                                             │
│ FROM CustomerProfiles                                                │
│ WHERE calculated_lifetime_value > 10000                              │
│   AND last_order_date < current_date - INTERVAL 60 DAYS             │
│   AND (                                                              │
│     open_support_tickets = 0                                         │
│     OR last_ticket_status = 'RESOLVED'                               │
│   )                                                                  │
│   AND opt_out_status = 'OPTED_IN'                                   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

Previewing segment...

Segment Preview:
  - Estimated Size: 4,287 customers
  - Average Lifetime Value: $18,432
  - Average Days Since Last Order: 78
  - Top States: CA (18%), TX (12%), NY (11%)

Would you like to:
  1. Create this segment
  2. Refine the criteria
  3. Export to CSV for review
> 1

Creating segment in Customer Profiles...

✅ Segment Created Successfully!

Segment Details:
  - Name: high_value_dormant_60d
  - ID: seg-abc123xyz
  - ARN: arn:aws:profile:us-east-1:123456:domains/my-domain/segments/seg-abc123
  - Size: 4,287 customers
  - Auto-Refresh: Enabled (daily)

Ready to create a campaign targeting this segment?
```

### Calculated Attributes for Segmentation

| Attribute | Description | Example Use |
|-----------|-------------|-------------|
| `lifetime_value` | Total customer spend | Target high-value customers |
| `days_since_last_order` | Recency metric | Reactivation campaigns |
| `support_contact_count` | Service frequency | Proactive outreach |
| `engagement_score` | Computed engagement | Retention targeting |
| `churn_probability` | ML-predicted churn risk | Save campaigns |
| `preferred_channel` | Most used contact method | Channel selection |

---

## 3. CREATE - Campaign Configuration

Create outbound campaigns with full configuration options.

### Usage Examples

```
Create a collections campaign with preview dialer
```

```
Build a predictive dialer campaign for sales
```

```
Create an agentless reminder campaign
```

```
Set up a progressive dialer campaign for appointment confirmations
```

### Dialer Modes

| Mode | Description | Best For | Key Settings |
|------|-------------|----------|--------------|
| **Predictive** | ML-powered pacing, dials ahead | High-volume sales, collections | AMD, max abandon rate |
| **Progressive** | 1:1 agent ratio, sequential | Regulated industries, compliance-first | No abandon risk |
| **Preview** | Agent sees context first | Complex/sensitive calls | Pre-call data display |
| **Agentless** | Automated messages | Reminders, notifications | No agent needed |

### Channel Options

| Channel | Use Cases | Requirements |
|---------|-----------|--------------|
| **Voice** | Sales, collections, support | Phone numbers, contact flow |
| **SMS** | Reminders, notifications | SMS capability, opt-in consent |
| **Email** | Marketing, follow-ups | Email addresses, templates |
| **WhatsApp** | International, digital-first | WhatsApp Business API |

### Agent Workflow for CREATE

1. **Select campaign type** - Agent-assisted or agentless?
2. **Choose dialer mode** - Predictive, progressive, preview?
3. **Configure channels** - Voice, SMS, email, WhatsApp?
4. **Set source** - Segment or contact list?
5. **Configure compliance** - TCPA, timezone, limits
6. **Set schedule** - Start time, end time, recurrence
7. **Review and confirm** - Preview all settings

### CREATE Example Session (Collections Campaign)

```
User: Create a collections campaign with preview dialer

Agent: I'll help you create a collections campaign. Preview dialer is perfect for
collections - it gives agents time to review account details before each call.

Let me gather the configuration:

1. What's the campaign name?
> Q2-Collections-2026

2. Which Connect instance should this campaign use?
   Found instances:
   - my-prod-connect (us-east-1)
   - my-dr-connect (us-west-2)
> my-prod-connect

3. What's the target segment or contact list?
   Available segments:
   - overdue_30_plus (2,341 customers)
   - overdue_60_plus (987 customers)
   - high_balance_overdue (456 customers)
   
   Or provide a contact list S3 path
> overdue_30_plus

4. Which channel(s)?
   a) Voice only
   b) Voice + SMS
   c) Voice + SMS + Email
> b

5. Configure voice settings:
   - Source phone number: +1-555-123-4567
   - Contact flow: Collections-Outbound-Flow
   - Preview timeout (seconds): 30
   
   Confirm these settings? (Yes/No)
> Yes

6. Configure SMS settings:
   - SMS template: "Hi {{customer_name}}, this is regarding your account ending
     in {{account_last4}}. Please call us at 1-800-XXX-XXXX or reply CALL."
   - Send SMS after: Failed voice attempt
   
   Confirm? (Yes/No)
> Yes

7. Compliance settings (TCPA):
   - Timezone restrictions: 8am-9pm local time
   - Max attempts per day: 3
   - Max attempts per week: 7
   - Answering machine detection: Enabled (leave voicemail)
   
   Confirm? (Yes/No)
> Yes

8. Schedule:
   - Start date: Immediately
   - Operating hours: Mon-Fri 9am-6pm ET, Sat 10am-2pm ET
   - End date: None (continuous)
   
   Confirm? (Yes/No)
> Yes

Generating campaign configuration...

┌─────────────────────────────────────────────────────────────────────┐
│                    CAMPAIGN CONFIGURATION                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Name:           Q2-Collections-2026                                │
│  Type:           AGENT_ASSISTED                                      │
│  Dialer Mode:    Preview                                             │
│  Instance:       my-prod-connect (us-east-1)                        │
│                                                                      │
│  SOURCE                                                              │
│  ─────────────────────────────────────────────────────────────────  │
│  Segment:        overdue_30_plus                                    │
│  Size:           2,341 customers                                    │
│                                                                      │
│  CHANNELS                                                            │
│  ─────────────────────────────────────────────────────────────────  │
│  Voice:          +1-555-123-4567 → Collections-Outbound-Flow        │
│  SMS:            Enabled (fallback after failed voice)              │
│                                                                      │
│  COMPLIANCE (TCPA)                                                   │
│  ─────────────────────────────────────────────────────────────────  │
│  Call Hours:     8am-9pm local time                                 │
│  Max/Day:        3 attempts                                          │
│  Max/Week:       7 attempts                                          │
│  AMD:            Leave voicemail                                     │
│                                                                      │
│  SCHEDULE                                                            │
│  ─────────────────────────────────────────────────────────────────  │
│  Start:          Immediately                                         │
│  Operating:      Mon-Fri 9am-6pm ET, Sat 10am-2pm ET                │
│  End:            Continuous                                          │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

Create this campaign? (Yes/No)
> Yes

Creating campaign...

✅ Campaign Created Successfully!

Campaign Details:
  - ID: camp-xyz789
  - ARN: arn:aws:connect-campaigns:us-east-1:123456:campaigns/camp-xyz789
  - Status: STOPPED (ready to start)

Next Steps:
  1. Start the campaign: "Start campaign Q2-Collections-2026"
  2. Add personalization: "Personalize campaign Q2-Collections-2026"
  3. Review before launch: "Dry run campaign Q2-Collections-2026"

What would you like to do?
```

---

## 4. PERSONALIZE - AI-Powered Content Generation

Use Amazon Bedrock to generate personalized outreach content.

### Usage Examples

```
Generate personalized scripts for my collections campaign
```

```
Create customer summaries for preview dialer
```

```
Write SMS templates personalized by customer segment
```

```
Generate voicemail scripts for different customer types
```

### Personalization Types

| Type | Description | Use Case |
|------|-------------|----------|
| **Call Scripts** | Agent talking points | Guided conversations |
| **Customer Summaries** | Pre-call briefings | Preview dialer context |
| **SMS Messages** | Personalized texts | Multi-channel campaigns |
| **Voicemail Scripts** | Automated recordings | AMD follow-up |
| **Email Templates** | Personalized emails | Digital outreach |

### Agent Workflow for PERSONALIZE

1. **Select campaign** - Which campaign to personalize?
2. **Choose content type** - Script, summary, message?
3. **Provide context** - Campaign objective, tone, compliance requirements
4. **Generate with Bedrock** - AI-powered content creation
5. **Review and refine** - Edit generated content
6. **Deploy content** - Attach to campaign

### PERSONALIZE Example Session

```
User: Generate personalized scripts for my collections campaign

Agent: I'll help create personalized scripts using Amazon Bedrock. Let me check
your campaign...

Found campaign: Q2-Collections-2026
  - Segment: overdue_30_plus (2,341 customers)
  - Dialer: Preview

What type of content should I generate?
  1. Agent call scripts (talking points for each customer type)
  2. Customer summaries (pre-call briefing for preview dialer)
  3. Voicemail scripts (for AMD scenarios)
  4. All of the above
> 4

Let me understand your requirements:

1. What tone should the scripts use?
   a) Firm but professional
   b) Empathetic and helpful
   c) Urgent but respectful
> b

2. What payment options can agents offer?
   a) Full payment only
   b) Payment plans available
   c) Hardship programs available
> c

3. Any compliance requirements for the script?
   - Mini-Miranda disclosure required? (Yes/No)
> Yes

4. Should scripts reference specific customer data?
   - Account balance
   - Days overdue
   - Previous payment history
   - Customer tenure
> All of the above

Generating personalized content with Amazon Bedrock...

═══════════════════════════════════════════════════════════════════
                    GENERATED CONTENT
═══════════════════════════════════════════════════════════════════

AGENT CALL SCRIPT (High-Value Long-Tenure Customer)
─────────────────────────────────────────────────────────────────────
Opening:
"Good [morning/afternoon], may I speak with {{customer_name}}?
Hi {{customer_name}}, this is [Agent Name] calling from [Company].
This call is regarding your account ending in {{account_last4}}.
This is an attempt to collect a debt and any information obtained
will be used for that purpose."

Context (Agent sees in preview):
- Customer since: {{tenure_years}} years
- Lifetime value: ${{lifetime_value}}
- Current balance: ${{balance}}
- Days overdue: {{days_overdue}}
- Last payment: {{last_payment_date}} (${{last_payment_amount}})

Body:
"I see you've been a valued customer for {{tenure_years}} years, and
we truly appreciate your business. I'm calling about your account
which currently shows a balance of ${{balance}} that's {{days_overdue}}
days past due.

I understand that sometimes unexpected situations come up. I'd like
to work with you today to find a solution that works for your
situation. We have several options available:

1. If you're able to pay the full balance today, I can [offer incentive]
2. We can set up a payment plan that fits your budget
3. If you're experiencing financial hardship, we have programs that
   may be able to help

What would work best for you?"

Objection Handling:
- "I can't afford it": "I understand completely. Let me see what
   payment plan options we have. What amount could you manage monthly?"
- "I didn't receive a bill": "I apologize for any confusion. Let me
   verify your contact information and send you a detailed statement."
- "I need to talk to spouse": "Of course, when would be a good time
   for me to call back when you've had a chance to discuss?"

Closing:
"Thank you for taking the time to speak with me today. [Confirm
arrangement]. Is there anything else I can help you with?"

─────────────────────────────────────────────────────────────────────

CUSTOMER SUMMARY (Preview Screen)
─────────────────────────────────────────────────────────────────────
╔═══════════════════════════════════════════════════════════════════╗
║  CUSTOMER: {{customer_name}}                    PRIORITY: {{tier}} ║
╠═══════════════════════════════════════════════════════════════════╣
║  Account: ****{{account_last4}}    Balance: ${{balance}}          ║
║  Days Overdue: {{days_overdue}}    Previous: {{prev_result}}       ║
╠═══════════════════════════════════════════════════════════════════╣
║  KEY INSIGHTS:                                                     ║
║  • {{tenure_years}}-year customer with ${{lifetime_value}} LTV    ║
║  • Last payment: ${{last_payment_amount}} on {{last_payment_date}} ║
║  • Payment history: {{payment_pattern}}                            ║
║  • Preferred contact time: {{preferred_time}}                      ║
╠═══════════════════════════════════════════════════════════════════╣
║  RECOMMENDED APPROACH: {{ai_recommendation}}                       ║
╚═══════════════════════════════════════════════════════════════════╝

─────────────────────────────────────────────────────────────────────

VOICEMAIL SCRIPT (AMD)
─────────────────────────────────────────────────────────────────────
"Hi {{customer_name}}, this is [Company] calling regarding your
account. Please call us back at 1-800-XXX-XXXX at your earliest
convenience. Our hours are Monday through Friday, 9am to 6pm
Eastern. Thank you."

[Note: Voicemail follows Mini-Miranda on callback, not in message]

═══════════════════════════════════════════════════════════════════

Content generated! Would you like to:
  1. Apply this content to the campaign
  2. Edit the scripts
  3. Generate variations for different customer segments
  4. Export to review
> 1

Applying content to campaign Q2-Collections-2026...

✅ Personalization Applied!

The following content has been configured:
  - Agent scripts: 3 variations (high-value, standard, new customer)
  - Preview summaries: Enabled with AI recommendations
  - Voicemail script: Configured for AMD scenarios
  - Bedrock model: Claude for real-time agent suggestions

Ready to deploy the campaign?
```

---

## 5. DEPLOY - Launch and Manage Campaigns

Deploy campaigns via API or CloudFormation with full lifecycle management.

### Usage Examples

```
Start campaign Q2-Collections-2026
```

```
Pause campaign Spring-Promotion
```

```
Deploy campaign via CloudFormation
```

```
Add contacts to running campaign
```

### Deployment Methods

| Method | Best For | Features |
|--------|----------|----------|
| **API Deployment** | Quick launches | Immediate, programmatic |
| **CloudFormation** | Production, IaC | Version control, rollback |
| **Batch Upload** | Large lists | PutDialRequestBatch API |

### Campaign Lifecycle

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ CREATED  │ →  │ RUNNING  │ ←→ │ PAUSED   │ →  │ STOPPED  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
     │               │               │               │
     │               │               │               │
     │               ▼               │               │
     │         ┌──────────┐         │               │
     └────────→│ DELETED  │←────────┴───────────────┘
               └──────────┘
```

### Agent Workflow for DEPLOY

1. **Select deployment method** - API, CloudFormation, or batch?
2. **Pre-flight checks** - Validate configuration, compliance settings
3. **Deploy/Start campaign** - Execute with progress tracking
4. **Monitor launch** - Real-time status updates
5. **Manage lifecycle** - Pause, resume, stop as needed

### DEPLOY Example Session

```
User: Start campaign Q2-Collections-2026

Agent: Let me run pre-flight checks before starting the campaign...

PRE-FLIGHT CHECKLIST
═══════════════════════════════════════════════════════════════════

Configuration:
  ✅ Campaign exists and is in STOPPED state
  ✅ Connect instance is ACTIVE
  ✅ Contact flow exists and is published
  ✅ Source phone number is claimed

Segment:
  ✅ Segment overdue_30_plus is valid
  ✅ 2,341 customers in segment
  ✅ All customers have phone numbers
  ✅ Opt-out status checked (12 excluded)

Compliance:
  ✅ TCPA timezone rules configured
  ✅ Communication limits set (3/day, 7/week)
  ✅ DNC list integration enabled
  ✅ Mini-Miranda disclosure in script

Resources:
  ✅ Sufficient agent capacity (15 agents in queue)
  ✅ Contact flow Lambda functions responding
  ✅ Bedrock model available for personalization

All checks passed! Ready to start campaign.

Current time: 10:23 AM ET (within operating hours)
Segment will begin dialing immediately.

Start campaign now? (Yes/No)
> Yes

Starting campaign Q2-Collections-2026...

Campaign Starting...
  [████████████████████████████████████████] 100%

✅ Campaign Started Successfully!

Campaign Status:
  - ID: camp-xyz789
  - Status: RUNNING
  - Started: 2026-03-11 10:24:00 ET
  - Initial Contacts: 2,329 (12 opt-outs excluded)

Real-Time Metrics (updating every 30 seconds):
  - Contacts Dialed: 23
  - Connected: 8 (34.8%)
  - In Preview: 2 (agents reviewing)
  - In Queue: 13 (waiting for agents)

Agent Status:
  - Available: 12 / 15
  - On Call: 3 / 15

Commands:
  - "Pause campaign" - Stop dialing, agents finish current calls
  - "Show campaign metrics" - Detailed analytics
  - "Add contacts" - Upload additional numbers

The campaign is now running. I'll notify you of any issues.
```

### CloudFormation Deployment

```
User: Deploy campaign via CloudFormation

Agent: I'll generate a CloudFormation template for your campaign.

This provides:
  - Version-controlled configuration
  - Repeatable deployments
  - Rollback capability
  - Integration with CI/CD pipelines

Generating CloudFormation template...

Generated: campaign-q2-collections.yaml

Resources Created:
  1. AWS::ConnectCampaignsV2::Campaign
  2. AWS::Lambda::Function (personalization)
  3. AWS::IAM::Role (campaign execution)
  4. AWS::CloudWatch::Alarm (monitoring)

Deploy options:
  1. Deploy now via AWS CLI
  2. Save template for review
  3. Create change set (preview changes)
> 1

Deploying stack: connect-campaign-q2-collections...

Stack Status: CREATE_IN_PROGRESS
  [████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 20%
  
  Creating resources:
  ✅ IAM Role created
  ✅ Lambda Function created
  ⏳ Campaign creating...
  ⏳ CloudWatch Alarm creating...

Stack Status: CREATE_COMPLETE

✅ CloudFormation Deployment Successful!

Stack: connect-campaign-q2-collections
Outputs:
  - CampaignId: camp-xyz789
  - CampaignArn: arn:aws:connect-campaigns:us-east-1:123456:campaigns/camp-xyz789
  - DashboardUrl: https://console.aws.amazon.com/connect/...

The campaign is deployed but not started.
Say "Start campaign Q2-Collections-2026" to begin dialing.
```

---

## 6. MONITOR - Campaign Analytics

Track campaign performance with Contact Lens analytics and real-time metrics.

### Usage Examples

```
Show metrics for campaign Q2-Collections-2026
```

```
What's the sentiment analysis for today's calls?
```

```
Show conversion rates by time of day
```

```
Compare campaign performance week over week
```

### Available Metrics

| Category | Metrics |
|----------|---------|
| **Volume** | Contacts dialed, connected, abandoned, voicemail |
| **Efficiency** | Connect rate, agent utilization, avg handle time |
| **Outcomes** | Conversions, promises-to-pay, callbacks scheduled |
| **Quality** | Customer sentiment, agent compliance, escalations |
| **Compliance** | Opt-outs, DNC hits, timezone violations |

### Agent Workflow for MONITOR

1. **Select campaign** - Which campaign to analyze?
2. **Choose time range** - Today, this week, custom?
3. **Display metrics** - Real-time dashboard or historical
4. **Drill down** - Segment by agent, time, outcome
5. **Export reports** - CSV, PDF, or dashboard link

### MONITOR Example Session

```
User: Show metrics for campaign Q2-Collections-2026

Agent: Fetching analytics for Q2-Collections-2026...

═══════════════════════════════════════════════════════════════════
            CAMPAIGN ANALYTICS: Q2-Collections-2026
            Period: Today (2026-03-11 9:00 AM - Now)
═══════════════════════════════════════════════════════════════════

VOLUME METRICS
─────────────────────────────────────────────────────────────────────
Total Contacts:        847 / 2,329 (36.4% penetration)

  Dialed:              847
  Connected:           312 (36.8%)
  No Answer:           287 (33.9%)
  Voicemail:           198 (23.4%)
  Busy/Failed:         50 (5.9%)

EFFICIENCY METRICS
─────────────────────────────────────────────────────────────────────
Agent Utilization:     78.3%
Avg Handle Time:       4:23
Avg Preview Time:      12 sec
Avg Wait Time:         8 sec

Preview Dialer Stats:
  - Skipped (agent):   23 (2.7%)
  - Timeout:           5 (0.6%)

OUTCOME METRICS
─────────────────────────────────────────────────────────────────────
Connected Calls:       312

  ✅ Promise to Pay:    127 (40.7%)
     └─ Total Promised: $47,832
  
  📅 Callback Scheduled: 89 (28.5%)
     └─ Avg Callback:    2.3 days out
  
  ❌ Refused:           52 (16.7%)
  
  📞 Transfer to Mgr:   18 (5.8%)
  
  ❓ Other:             26 (8.3%)

QUALITY METRICS (Contact Lens)
─────────────────────────────────────────────────────────────────────
Customer Sentiment:
  😊 Positive:         34% (106 calls)
  😐 Neutral:          48% (150 calls)
  😠 Negative:         18% (56 calls)

Agent Compliance:
  ✅ Mini-Miranda:      99.7% (311/312)
  ⚠️ Violation:        1 call flagged for review

Top Customer Concerns (detected themes):
  1. "Financial hardship" - 47 mentions
  2. "Payment plan" - 38 mentions
  3. "Didn't receive statement" - 22 mentions
  4. "Dispute charge" - 15 mentions

COMPLIANCE METRICS
─────────────────────────────────────────────────────────────────────
  ✅ Timezone Compliant: 100%
  ✅ Communication Limits: No violations
  ✅ DNC Checks: 3 blocked
  ✅ Opt-outs Today: 2 processed

═══════════════════════════════════════════════════════════════════

Performance vs. Goals:
  - Connect Rate: 36.8% (Goal: 35%) ✅ +1.8%
  - Promise Rate: 40.7% (Goal: 38%) ✅ +2.7%
  - Avg Handle Time: 4:23 (Goal: 5:00) ✅ Under target

Recommendations:
  1. 📈 Peak connect time is 10-11 AM - consider adding agents
  2. 😠 18% negative sentiment - review call recordings
  3. 📞 High callback rate - ensure follow-up campaign scheduled

Would you like to:
  1. View hourly breakdown
  2. See agent performance rankings
  3. Listen to flagged calls
  4. Export report
```

---

## 7. OPTIMIZE - AI-Powered Recommendations

Get AI recommendations to improve campaign performance.

### Usage Examples

```
How can I improve my collections campaign?
```

```
Optimize dial times for best connect rates
```

```
Which scripts are performing best?
```

```
Run A/B test on call scripts
```

### Optimization Areas

| Area | AI Analysis | Recommendations |
|------|-------------|-----------------|
| **Timing** | Best hours/days | Schedule optimization |
| **Scripts** | A/B performance | Script improvements |
| **Segments** | Conversion by group | Targeting refinement |
| **Agents** | Individual performance | Coaching insights |
| **Compliance** | Risk patterns | Process improvements |

### OPTIMIZE Example Session

```
User: How can I improve my collections campaign?

Agent: Analyzing Q2-Collections-2026 performance data...

═══════════════════════════════════════════════════════════════════
            AI OPTIMIZATION RECOMMENDATIONS
═══════════════════════════════════════════════════════════════════

Based on 3 days of campaign data (2,541 contacts), here are my
recommendations ranked by potential impact:

1. TIMING OPTIMIZATION (High Impact)
─────────────────────────────────────────────────────────────────────
Finding: Connect rates vary significantly by time of day

Current Performance:
  - Morning (9-12):    42.1% connect rate
  - Afternoon (12-3):  31.2% connect rate  ← Underperforming
  - Late Afternoon (3-6): 38.7% connect rate

Recommendation:
  ✓ Shift 20% of afternoon capacity to morning hours
  ✓ Reduce staff 12-2 PM, increase 9-11 AM
  
Projected Impact: +5.2% overall connect rate (+$8,400 collections)


2. SEGMENT REFINEMENT (High Impact)
─────────────────────────────────────────────────────────────────────
Finding: Long-tenure customers convert at 2x rate of new customers

Conversion Rates by Tenure:
  - 5+ years:          52.3% promise rate
  - 2-5 years:         41.1% promise rate
  - < 2 years:         24.8% promise rate

Recommendation:
  ✓ Create separate campaigns by tenure
  ✓ Prioritize long-tenure customers for preview dialer
  ✓ Use agentless for new customers (lower conversion, high volume)
  
Projected Impact: +8.1% overall promise rate


3. SCRIPT OPTIMIZATION (Medium Impact)
─────────────────────────────────────────────────────────────────────
Finding: Calls mentioning "payment plan" early convert 31% better

Script Analysis (Contact Lens NLP):
  - Early payment plan mention: 48.2% conversion
  - Late payment plan mention:  36.8% conversion
  - No payment plan mention:    29.1% conversion

Recommendation:
  ✓ Update script to introduce payment options in first 60 seconds
  ✓ Add payment calculator to agent screen
  
Projected Impact: +12.3% conversion on revised script


4. AGENT COACHING (Medium Impact)
─────────────────────────────────────────────────────────────────────
Finding: Top 3 agents outperform average by 23%

Top Performer Analysis:
  - Avg empathy score: 8.4/10 (vs team avg 6.9)
  - Avg talk-listen ratio: 40/60 (vs team avg 55/45)
  - First-call resolution: 67% (vs team avg 51%)

Recommendation:
  ✓ Share top performer call recordings with team
  ✓ Implement empathy training module
  ✓ Set talk-listen ratio target of 45/55
  
Projected Impact: +7.5% team conversion rate


5. COMPLIANCE RISK MITIGATION (Preventive)
─────────────────────────────────────────────────────────────────────
Finding: 3 near-miss compliance events detected

Risk Patterns:
  - 2 calls initiated at 8:58 PM local (2-min buffer risk)
  - 1 Mini-Miranda delivered after payment discussion started

Recommendation:
  ✓ Increase timezone buffer from 2 min to 5 min
  ✓ Add contact flow check for Mini-Miranda before payment topic
  
Risk Reduction: Prevents potential $50K+ TCPA exposure

═══════════════════════════════════════════════════════════════════

Implementation Priority:
  1. Script optimization (quick win, high impact)
  2. Timing optimization (operational change)
  3. Segment refinement (requires new campaigns)
  4. Agent coaching (ongoing program)
  5. Compliance updates (immediate for risk)

Would you like me to:
  1. Implement the script changes
  2. Create optimized campaign schedule
  3. Set up A/B test for scripts
  4. Generate agent coaching report
```

---

## Commands Summary

| Command Type | Example |
|--------------|---------|
| **Discover** | `List campaigns in my-prod-connect` |
| **Segment** | `Create a segment of high-value customers who haven't ordered in 60 days` |
| **Create** | `Create a collections campaign with preview dialer` |
| **Personalize** | `Generate personalized scripts for my collections campaign` |
| **Deploy** | `Start campaign Q2-Collections-2026` |
| **Deploy CFn** | `Deploy campaign via CloudFormation` |
| **Monitor** | `Show metrics for campaign Q2-Collections-2026` |
| **Optimize** | `How can I improve my collections campaign?` |
| **Lifecycle** | `Pause campaign Spring-Promotion` |
| **Lifecycle** | `Resume campaign Spring-Promotion` |
| **Lifecycle** | `Stop campaign Q1-Outreach` |

---

## Compliance Reference (TCPA)

### Built-In Compliance Features

| Feature | Description | Configuration |
|---------|-------------|---------------|
| **Timezone Restrictions** | Limit calls to 8am-9pm local | Automatic based on phone number |
| **Communication Limits** | Max contacts per day/week | Instance-level or campaign-level |
| **Answering Machine Detection** | Detect and handle voicemails | AMD enabled/disabled per campaign |
| **Do-Not-Call Integration** | Check against DNC lists | External DNC API integration |
| **Consent Tracking** | Honor opt-in/opt-out status | Customer Profiles attribute |
| **Exempt Communications** | Bypass limits for critical messages | Fraud alerts, emergencies |

### Example TCPA Configuration

```yaml
CommunicationLimits:
  MaxContactsPerDay: 3
  MaxContactsPerWeek: 7
  ExemptFromLimits: false  # true for emergency/fraud

CommunicationTimeConfig:
  LocalTimeZoneConfig:
    LocalTimeZoneDetection: ZIP_CODE  # or AREA_CODE
  OpenHours:
    StartTime: "08:00"
    EndTime: "21:00"

AnswerMachineDetection:
  EnableAnswerMachineDetection: true
  AwaitAnswerMachinePrompt: true  # wait for beep
```

---

## Troubleshooting Guide

| Issue | Possible Cause | Resolution |
|-------|----------------|------------|
| Campaign won't start | Missing permissions | Check IAM role for connectcampaigns:* |
| Low connect rates | Wrong time of day | Analyze hourly metrics, adjust schedule |
| Segment not found | Domain mismatch | Verify Customer Profiles domain |
| AMD not working | Configuration issue | Enable Contact Lens on instance |
| Agents not receiving calls | Queue misconfiguration | Check routing profile assignments |
| Compliance violation | Timezone detection failed | Use ZIP_CODE detection method |
| Bedrock timeout | Model throttling | Implement retry with exponential backoff |
| High abandon rate | Predictive too aggressive | Switch to progressive or reduce pacing |

---

## Tools Used

This agent uses:

1. **smart_campaign_agent.py** - Main skill wrapper
   - Location: `~/.copilot/skills/connect-campaign-agent/scripts/`

2. **AWS Services:**
   - Amazon Connect Outbound Campaigns V2 API
   - Amazon Connect Customer Profiles API
   - Amazon Connect Contact Lens API
   - Amazon Bedrock API
   - AWS CloudFormation

3. **Related Skills:**
   - `amazon-connect-builder` - Instance and flow creation
   - `connect-instance-replication` - Cross-region sync

---

## Prerequisites

- AWS credentials configured (env vars, profile, or IAM role)
- Python 3.9+ with boto3
- Amazon Connect instance with:
  - Outbound campaigns enabled
  - Customer Profiles domain configured
  - Contact Lens enabled (for analytics)
- Amazon Bedrock access (for personalization)

### Required IAM Permissions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "connect:*",
        "connect-campaigns:*",
        "profile:*",
        "bedrock:InvokeModel",
        "cloudformation:*",
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## GitHub Repository

https://github.com/636137/amazon-connect-replicator
