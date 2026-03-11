# Amazon Connect Replicator (Primitive APIs)

This repo implements a **best-effort** way to copy selected Amazon Connect resources between two *existing* instances using the primitive Connect APIs (List*/Describe*/Create*/Update*).

What’s in the repo:
- **Python CLI** (boto3) to export/import bundles.
- **API + React UI** to pick regions/instances, export a bundle JSON, and import it into a target instance.

## Important reality check
Amazon Connect does **not** expose an API to fully “clone an instance” (telephony setup, identity, storage configs, etc.) into a brand new instance in minutes.
This project instead focuses on migrating configuration objects that *do* have CRUD-style APIs.

## Current scope (bundle v1)
- Contact Flow Modules (DescribeContactFlowModule includes JSON `Content`)
- Contact Flows (DescribeContactFlow includes JSON `Content`)

## Run the UI + API
```bash
npm install
npm run dev
```
- UI: http://localhost:3000
- API: http://localhost:3001

## Python CLI
See: `tools/connect-instance-replicator/README.md`

## Notes / limitations
- Flow JSON often references other resources by **ID/ARN** (queues, prompts, routing profiles, other flows/modules). This repo does a small amount of ID/ARN rewriting for flows/modules, but it’s still best-effort.
- Prompts, queues, routing profiles, hours, quick connects, phone numbers, etc. are not copied yet.

References:
- Admin guide (flow import/export): https://docs.aws.amazon.com/connect/latest/adminguide/contact-flow-import-export.html
- API `DescribeContactFlow`: https://docs.aws.amazon.com/connect/latest/APIReference/API_DescribeContactFlow.html
- API `CreateContactFlow`: https://docs.aws.amazon.com/connect/latest/APIReference/API_CreateContactFlow.html
- API `UpdateContactFlowContent`: https://docs.aws.amazon.com/connect/latest/APIReference/API_UpdateContactFlowContent.html
