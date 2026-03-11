# Amazon Connect resource export/import (primitive APIs)

This folder contains a small Python CLI to export/import a JSON bundle using Connect’s primitive APIs.

## Install
```bash
cd tools/connect-instance-replicator
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Export a bundle
Exports Contact Flow Modules + Contact Flows (including the JSON `Content` fields):

```bash
python connect_instance_replicate.py export \
  --region us-east-1 \
  --instance-id <SOURCE_INSTANCE_ID> \
  --out bundle.json
```

## Import a bundle
Imports into an *existing* target instance. By default it skips resources that already exist (matched by name).

```bash
python connect_instance_replicate.py import \
  --region us-west-2 \
  --instance-id <TARGET_INSTANCE_ID> \
  --in bundle.json
```

To overwrite existing flows/modules (update content):
```bash
python connect_instance_replicate.py import \
  --region us-west-2 \
  --instance-id <TARGET_INSTANCE_ID> \
  --in bundle.json \
  --overwrite
```

## Notes / limitations
- This does not create a new instance; it copies resources between existing instances.
- Flow JSON can reference queues/prompts/routing profiles/etc by ID/ARN; this tool only attempts limited rewriting for flows/modules.

References:
- Admin guide (flow import/export): https://docs.aws.amazon.com/connect/latest/adminguide/contact-flow-import-export.html
- API `DescribeContactFlow`: https://docs.aws.amazon.com/connect/latest/APIReference/API_DescribeContactFlow.html
- API `CreateContactFlow`: https://docs.aws.amazon.com/connect/latest/APIReference/API_CreateContactFlow.html
