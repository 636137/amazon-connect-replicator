# Amazon Connect cross-region replication (us-east-1 -> us-west-2)

This folder contains a small Python CLI that uses Amazon Connect Global Resiliency’s **ReplicateInstance** API to create a replica instance in a paired region and (optionally) helps with post-creation **Traffic Distribution Group** user association.

## Prerequisites / constraints (AWS)

From AWS docs:
- Global Resiliency replication is only available for specific region pairs (including **us-east-1 <-> us-west-2**).
- Access can be gated (you may need to work with your AWS SA/TAM to enable it).
- Source instance must be **ACTIVE**, must have an **instance alias**, and must have **SAML enabled**.
- Replica uses the **same instance ID** as the source; the **replica alias must be unique**.
- Update any contact flows that hardcode a Region to use `$.AwsRegion` / `$['AwsRegion']` instead.
- Ensure integrations exist in both regions (for example, Lambda functions should exist in both regions; AWS recommends the same function name).
- If you use Lex in flows, plan a cross-region strategy (Lex global resiliency or region-based branching).
- If you rely on AWS managed keys in the replica region, AWS recommends creating a temporary Connect instance in the target region first to initialize default managed keys.

Reference:
- Admin guide: https://docs.aws.amazon.com/connect/latest/adminguide/create-replica-connect-instance.html
- API: https://docs.aws.amazon.com/connect/latest/APIReference/API_ReplicateInstance.html
- CLI: https://docs.aws.amazon.com/cli/latest/reference/connect/replicate-instance.html

## Install

```bash
cd tools/connect-instance-replicator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Replicate instance (Python / boto3)

Call **ReplicateInstance** in the **source** region:

```bash
python connect_instance_replicate.py replicate \
  --source-region us-east-1 \
  --target-region us-west-2 \
  --instance-id <SOURCE_INSTANCE_ID> \
  --replica-alias <UNIQUE_REPLICA_ALIAS> \
  --wait
```

## Replicate instance (AWS CLI equivalent)

```bash
aws connect replicate-instance \
  --region us-east-1 \
  --instance-id <SOURCE_INSTANCE_ID> \
  --replica-region us-west-2 \
  --replica-alias <UNIQUE_REPLICA_ALIAS> \
  --no-cli-pager
```

## Post-step: associate users to the default Traffic Distribution Group

AWS notes you must associate agents to a traffic distribution group after replication.

Associate a specific user:
```bash
python connect_instance_replicate.py associate-users \
  --region us-east-1 \
  --instance-id <INSTANCE_ID> \
  --user-id <USER_ID>
```

Associate all users (can take time in large instances):
```bash
python connect_instance_replicate.py associate-users \
  --region us-east-1 \
  --instance-id <INSTANCE_ID> \
  --all-users
```

Relevant APIs:
- ListTrafficDistributionGroups: https://docs.aws.amazon.com/connect/latest/APIReference/API_ListTrafficDistributionGroups.html
- AssociateTrafficDistributionGroupUser: https://docs.aws.amazon.com/connect/latest/APIReference/API_AssociateTrafficDistributionGroupUser.html
