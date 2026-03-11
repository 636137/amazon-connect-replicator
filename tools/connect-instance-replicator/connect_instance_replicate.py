#!/usr/bin/env python3

import argparse
import json
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError


CONTACT_FLOW_TYPES: List[str] = [
    "CONTACT_FLOW",
    "CUSTOMER_QUEUE",
    "CUSTOMER_HOLD",
    "CUSTOMER_WHISPER",
    "AGENT_HOLD",
    "AGENT_WHISPER",
    "OUTBOUND_WHISPER",
    "AGENT_TRANSFER",
    "QUEUE_TRANSFER",
    "CAMPAIGN",
]


def _session(profile: Optional[str], region: str) -> boto3.session.Session:
    if profile:
        return boto3.session.Session(profile_name=profile, region_name=region)
    return boto3.session.Session(region_name=region)


def _connect_client(profile: Optional[str], region: str):
    return _session(profile, region).client("connect")


def _paginate(method, *, next_token_key: str = "NextToken", **kwargs) -> Iterable[Dict[str, Any]]:
    token = None
    while True:
        call_kwargs = dict(kwargs)
        if token:
            call_kwargs[next_token_key] = token
        resp = method(**call_kwargs)
        yield resp
        token = resp.get(next_token_key)
        if not token:
            break


def _apply_replacements(content: str, replacements: List[Tuple[str, str]]) -> str:
    out = content
    for src, dst in replacements:
        if not src or src == dst:
            continue
        out = out.replace(src, dst)
    return out


def export_bundle(*, profile: Optional[str], region: str, instance_id: str) -> Dict[str, Any]:
    client = _connect_client(profile, region)

    # Hours of operation
    hours_summaries: List[Dict[str, Any]] = []
    for page in _paginate(client.list_hours_of_operations, InstanceId=instance_id, MaxResults=100):
        hours_summaries.extend(page.get("HoursOfOperationSummaryList") or [])

    hours_of_operations: List[Dict[str, Any]] = []
    for h in hours_summaries:
        hid = h.get("Id")
        if not hid:
            continue
        d = client.describe_hours_of_operation(InstanceId=instance_id, HoursOfOperationId=hid)
        ho = d.get("HoursOfOperation") or {}
        if ho.get("Name"):
            hours_of_operations.append(
                {
                    "id": ho.get("HoursOfOperationId"),
                    "arn": ho.get("HoursOfOperationArn"),
                    "name": ho.get("Name"),
                    "description": ho.get("Description"),
                    "timeZone": ho.get("TimeZone"),
                    "config": ho.get("Config"),
                    "tags": ho.get("Tags"),
                }
            )

    hours_name_by_id: Dict[str, str] = {}
    for ho in hours_of_operations:
        if ho.get("id") and ho.get("name"):
            hours_name_by_id[str(ho["id"])]=str(ho["name"])

    # Queues
    # Best-effort: some accounts/instances can return queue IDs that fail DescribeQueue (eventual consistency
    # or deleted resources). We skip those rather than failing the entire export.
    queue_summaries: List[Dict[str, Any]] = []
    for page in _paginate(
        client.list_queues,
        InstanceId=instance_id,
        MaxResults=100,
        QueueTypes=["STANDARD"],
    ):
        queue_summaries.extend(page.get("QueueSummaryList") or [])

    queues: List[Dict[str, Any]] = []
    for q in queue_summaries:
        qid = q.get("Id")
        if not qid:
            continue
        try:
            d = client.describe_queue(InstanceId=instance_id, QueueId=qid)
        except ClientError as e:
            code = (e.response or {}).get("Error", {}).get("Code")
            if code == "ResourceNotFoundException":
                print(f"WARN: skipping queue id {qid}: {code}", file=sys.stderr)
                continue
            raise
        qq = d.get("Queue") or {}
        if qq.get("Name"):
            hours_id = qq.get("HoursOfOperationId")
            queues.append(
                {
                    "id": qq.get("QueueId"),
                    "arn": qq.get("QueueArn"),
                    "name": qq.get("Name"),
                    "description": qq.get("Description"),
                    "status": qq.get("Status"),
                    "maxContacts": qq.get("MaxContacts"),
                    "hoursOfOperationId": hours_id,
                    "hoursOfOperationName": hours_name_by_id.get(str(hours_id)) if hours_id else None,
                    "outboundCallerConfig": qq.get("OutboundCallerConfig"),
                    "tags": qq.get("Tags"),
                }
            )

    # Modules
    modules: List[Dict[str, Any]] = []
    for page in _paginate(client.list_contact_flow_modules, InstanceId=instance_id, MaxResults=100):
        modules.extend(page.get("ContactFlowModulesSummaryList") or [])

    flow_modules: List[Dict[str, Any]] = []
    for m in modules:
        mid = m.get("Id")
        if not mid:
            continue
        d = client.describe_contact_flow_module(InstanceId=instance_id, ContactFlowModuleId=mid)
        mod = d.get("ContactFlowModule") or {}
        if mod.get("Name"):
            flow_modules.append(
                {
                    "id": mod.get("Id"),
                    "arn": mod.get("Arn"),
                    "name": mod.get("Name"),
                    "description": mod.get("Description"),
                    "state": mod.get("State"),
                    "status": mod.get("Status"),
                    "content": mod.get("Content"),
                    "settings": mod.get("Settings"),
                    "tags": mod.get("Tags"),
                }
            )

    # Flows
    flows: List[Dict[str, Any]] = []
    for page in _paginate(
        client.list_contact_flows,
        InstanceId=instance_id,
        ContactFlowTypes=CONTACT_FLOW_TYPES,
        MaxResults=100,
    ):
        flows.extend(page.get("ContactFlowSummaryList") or [])

    contact_flows: List[Dict[str, Any]] = []
    for f in flows:
        fid = f.get("Id")
        if not fid:
            continue
        d = client.describe_contact_flow(InstanceId=instance_id, ContactFlowId=fid)
        flow = d.get("ContactFlow") or {}
        if flow.get("Name") and flow.get("Type"):
            contact_flows.append(
                {
                    "id": flow.get("Id"),
                    "arn": flow.get("Arn"),
                    "name": flow.get("Name"),
                    "type": flow.get("Type"),
                    "description": flow.get("Description"),
                    "state": flow.get("State"),
                    "status": flow.get("Status"),
                    "content": flow.get("Content"),
                    "tags": flow.get("Tags"),
                }
            )

    return {
        "version": 1,
        "exportedAt": __import__("datetime").datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "source": {"region": region, "instanceId": instance_id},
        "hoursOfOperations": hours_of_operations,
        "queues": queues,
        "flowModules": flow_modules,
        "contactFlows": contact_flows,
    }


def import_bundle(
    *,
    profile: Optional[str],
    region: str,
    instance_id: str,
    bundle: Dict[str, Any],
    overwrite: bool,
    dry_run: bool,
) -> Dict[str, Any]:
    if bundle.get("version") != 1:
        raise ValueError("Unsupported bundle version")

    client = _connect_client(profile, region)

    # Existing hours of operation
    existing_hours: Dict[str, Dict[str, Any]] = {}
    for page in _paginate(client.list_hours_of_operations, InstanceId=instance_id, MaxResults=100):
        for h in page.get("HoursOfOperationSummaryList") or []:
            if h.get("Name"):
                existing_hours[h["Name"]] = h

    hours_repl: List[Tuple[str, str]] = []
    created_hours = updated_hours = skipped_hours = 0

    for h in bundle.get("hoursOfOperations") or []:
        name = h.get("name")
        if not name:
            continue
        existing = existing_hours.get(name)

        if existing and existing.get("Id"):
            if not overwrite:
                skipped_hours += 1
            else:
                if not dry_run:
                    client.update_hours_of_operation(
                        InstanceId=instance_id,
                        HoursOfOperationId=existing["Id"],
                        Name=name,
                        Description=h.get("description"),
                        TimeZone=h.get("timeZone"),
                        Config=h.get("config"),
                    )
                updated_hours += 1

            if h.get("id"):
                hours_repl.append((h["id"], existing["Id"]))
            if h.get("arn") and existing.get("Arn"):
                hours_repl.append((h["arn"], existing["Arn"]))
            continue

        if dry_run:
            created_hours += 1
            continue

        resp = client.create_hours_of_operation(
            InstanceId=instance_id,
            Name=name,
            Description=h.get("description"),
            TimeZone=h.get("timeZone"),
            Config=h.get("config"),
            Tags=h.get("tags"),
        )
        created_hours += 1

        existing_hours[name] = {
            "Id": resp.get("HoursOfOperationId"),
            "Arn": resp.get("HoursOfOperationArn"),
            "Name": name,
        }
        if h.get("id") and resp.get("HoursOfOperationId"):
            hours_repl.append((h["id"], resp["HoursOfOperationId"]))
        if h.get("arn") and resp.get("HoursOfOperationArn"):
            hours_repl.append((h["arn"], resp["HoursOfOperationArn"]))

    def _resolve_hours_id(q: Dict[str, Any]) -> Optional[str]:
        if q.get("hoursOfOperationName"):
            eh = existing_hours.get(str(q["hoursOfOperationName"]))
            if eh and eh.get("Id"):
                return str(eh["Id"])
        if q.get("hoursOfOperationId"):
            for src, dst in hours_repl:
                if src == q["hoursOfOperationId"]:
                    return dst
        return None

    # Existing queues
    existing_queues: Dict[str, Dict[str, Any]] = {}
    for page in _paginate(client.list_queues, InstanceId=instance_id, MaxResults=100):
        for q in page.get("QueueSummaryList") or []:
            if q.get("Name"):
                existing_queues[q["Name"]] = q

    queue_repl: List[Tuple[str, str]] = []
    created_queues = updated_queues = skipped_queues = 0

    for q in bundle.get("queues") or []:
        name = q.get("name")
        if not name:
            continue
        existing = existing_queues.get(name)
        target_hours_id = _resolve_hours_id(q)

        if existing and existing.get("Id"):
            if not overwrite:
                skipped_queues += 1
            else:
                if not dry_run:
                    if isinstance(q.get("maxContacts"), int):
                        client.update_queue_max_contacts(
                            InstanceId=instance_id,
                            QueueId=existing["Id"],
                            MaxContacts=q.get("maxContacts"),
                        )
                    if target_hours_id:
                        client.update_queue_hours_of_operation(
                            InstanceId=instance_id,
                            QueueId=existing["Id"],
                            HoursOfOperationId=target_hours_id,
                        )
                    if q.get("outboundCallerConfig"):
                        client.update_queue_outbound_caller_config(
                            InstanceId=instance_id,
                            QueueId=existing["Id"],
                            OutboundCallerConfig=q.get("outboundCallerConfig"),
                        )
                    if q.get("status"):
                        client.update_queue_status(
                            InstanceId=instance_id,
                            QueueId=existing["Id"],
                            Status=q.get("status"),
                        )
                updated_queues += 1

            if q.get("id"):
                queue_repl.append((q["id"], existing["Id"]))
            if q.get("arn") and existing.get("Arn"):
                queue_repl.append((q["arn"], existing["Arn"]))
            continue

        if dry_run:
            created_queues += 1
            continue

        if not target_hours_id:
            raise RuntimeError(f"Queue '{name}' is missing a resolvable hoursOfOperationId/name")

        resp = client.create_queue(
            InstanceId=instance_id,
            Name=name,
            Description=q.get("description"),
            HoursOfOperationId=target_hours_id,
            MaxContacts=q.get("maxContacts"),
            OutboundCallerConfig=q.get("outboundCallerConfig"),
            Tags=q.get("tags"),
        )
        created_queues += 1

        existing_queues[name] = {"Id": resp.get("QueueId"), "Arn": resp.get("QueueArn"), "Name": name}
        if q.get("id") and resp.get("QueueId"):
            queue_repl.append((q["id"], resp["QueueId"]))
        if q.get("arn") and resp.get("QueueArn"):
            queue_repl.append((q["arn"], resp["QueueArn"]))

    # Existing modules
    existing_modules: Dict[str, Dict[str, Any]] = {}
    for page in _paginate(client.list_contact_flow_modules, InstanceId=instance_id, MaxResults=100):
        for m in page.get("ContactFlowModulesSummaryList") or []:
            if m.get("Name"):
                existing_modules[m["Name"]] = m

    module_repl: List[Tuple[str, str]] = []

    created_modules = updated_modules = skipped_modules = 0

    for m in bundle.get("flowModules") or []:
        name = m.get("name")
        if not name:
            continue
        existing = existing_modules.get(name)

        content0 = _apply_replacements(_apply_replacements(str(m.get("content") or "{}"), hours_repl), queue_repl)

        if existing and existing.get("Id"):
            if not overwrite:
                skipped_modules += 1
            else:
                if not dry_run:
                    client.update_contact_flow_module_content(
                        InstanceId=instance_id,
                        ContactFlowModuleId=existing["Id"],
                        Content=content0,
                        Settings=m.get("settings"),
                    )
                updated_modules += 1

            if m.get("id"):
                module_repl.append((m["id"], existing["Id"]))
            if m.get("arn") and existing.get("Arn"):
                module_repl.append((m["arn"], existing["Arn"]))
            continue

        if dry_run:
            created_modules += 1
            continue

        resp = client.create_contact_flow_module(
            InstanceId=instance_id,
            Name=name,
            Description=m.get("description"),
            Content=content0,
            Tags=m.get("tags"),
            Settings=m.get("settings"),
        )
        created_modules += 1

        existing_modules[name] = {"Id": resp.get("Id"), "Arn": resp.get("Arn"), "Name": name}
        if m.get("id") and resp.get("Id"):
            module_repl.append((m["id"], resp["Id"]))
        if m.get("arn") and resp.get("Arn"):
            module_repl.append((m["arn"], resp["Arn"]))

    # Existing flows
    existing_flows: Dict[str, Dict[str, Any]] = {}
    for page in _paginate(
        client.list_contact_flows,
        InstanceId=instance_id,
        ContactFlowTypes=CONTACT_FLOW_TYPES,
        MaxResults=100,
    ):
        for f in page.get("ContactFlowSummaryList") or []:
            if f.get("Name") and f.get("ContactFlowType"):
                existing_flows[f"{f['ContactFlowType']}|{f['Name']}"] = f

    flow_repl: List[Tuple[str, str]] = []
    created_flows = updated_flows = skipped_flows = 0

    imported_targets: List[Tuple[Dict[str, Any], str]] = []

    for f in bundle.get("contactFlows") or []:
        name = f.get("name")
        ftype = f.get("type")
        if not name or not ftype:
            continue

        key = f"{ftype}|{name}"
        existing = existing_flows.get(key)

        raw_content = f.get("content") or "{}"
        content1 = _apply_replacements(
            _apply_replacements(_apply_replacements(str(raw_content), hours_repl), queue_repl),
            module_repl,
        )

        if existing and existing.get("Id"):
            if not overwrite:
                skipped_flows += 1
            else:
                if not dry_run:
                    client.update_contact_flow_content(
                        InstanceId=instance_id,
                        ContactFlowId=existing["Id"],
                        Content=content1,
                    )
                updated_flows += 1

            if f.get("id"):
                flow_repl.append((f["id"], existing["Id"]))
            if f.get("arn") and existing.get("Arn"):
                flow_repl.append((f["arn"], existing["Arn"]))

            imported_targets.append((f, existing["Id"]))
            continue

        if dry_run:
            created_flows += 1
            continue

        try:
            resp = client.create_contact_flow(
                InstanceId=instance_id,
                Name=name,
                Type=ftype,
                Description=f.get("description"),
                Content=content1,
                Tags=f.get("tags"),
            )
        except ClientError as e:
            raise RuntimeError(f"Failed creating contact flow '{name}' ({ftype}): {e}")

        created_flows += 1

        if f.get("id") and resp.get("ContactFlowId"):
            flow_repl.append((f["id"], resp["ContactFlowId"]))
        if f.get("arn") and resp.get("ContactFlowArn"):
            flow_repl.append((f["arn"], resp["ContactFlowArn"]))

        if resp.get("ContactFlowId"):
            imported_targets.append((f, resp["ContactFlowId"]))

        existing_flows[key] = {
            "Id": resp.get("ContactFlowId"),
            "Arn": resp.get("ContactFlowArn"),
            "Name": name,
            "ContactFlowType": ftype,
        }

    # Second pass: rewrite flow-to-flow references (best-effort)
    if not dry_run and overwrite:
        for src_flow, target_id in imported_targets:
            raw_content = src_flow.get("content")
            if not isinstance(raw_content, str):
                continue
            content2 = _apply_replacements(
                _apply_replacements(
                    _apply_replacements(_apply_replacements(raw_content, hours_repl), queue_repl),
                    module_repl,
                ),
                flow_repl,
            )
            client.update_contact_flow_content(
                InstanceId=instance_id,
                ContactFlowId=target_id,
                Content=content2,
            )

    return {
        "createdHours": created_hours,
        "updatedHours": updated_hours,
        "skippedHours": skipped_hours,
        "createdQueues": created_queues,
        "updatedQueues": updated_queues,
        "skippedQueues": skipped_queues,
        "createdModules": created_modules,
        "updatedModules": updated_modules,
        "skippedModules": skipped_modules,
        "createdFlows": created_flows,
        "updatedFlows": updated_flows,
        "skippedFlows": skipped_flows,
        "dryRun": dry_run,
        "overwrite": overwrite,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Best-effort Amazon Connect exporter/importer using primitive Connect APIs (hours, queues, flows + modules)."
    )
    p.add_argument("--profile", default=None, help="AWS credential profile name (optional)")

    sub = p.add_subparsers(dest="cmd", required=True)

    exp = sub.add_parser("export", help="Export a bundle (hours, queues, flows + flow modules)")
    exp.add_argument("--region", required=True)
    exp.add_argument("--instance-id", required=True)
    exp.add_argument("--out", required=False, default="-", help="Output file path, or '-' for stdout")

    imp = sub.add_parser("import", help="Import a bundle into an existing instance (hours, queues, flows + modules)")
    imp.add_argument("--region", required=True)
    imp.add_argument("--instance-id", required=True)
    imp.add_argument("--in", dest="in_path", required=True, help="Input bundle JSON path")
    imp.add_argument("--overwrite", action="store_true", help="Overwrite (update content) if resource exists")
    imp.add_argument("--dry-run", action="store_true", help="Print what would happen, but do not call Create/Update")

    return p


def main(argv: List[str]) -> int:
    args = build_parser().parse_args(argv)

    try:
        if args.cmd == "export":
            b = export_bundle(profile=args.profile, region=args.region, instance_id=args.instance_id)
            data = json.dumps(b, indent=2)
            if args.out == "-":
                print(data)
            else:
                with open(args.out, "w", encoding="utf-8") as f:
                    f.write(data)
                print(f"Wrote bundle: {args.out}")
            return 0

        if args.cmd == "import":
            with open(args.in_path, "r", encoding="utf-8") as f:
                bundle = json.load(f)
            out = import_bundle(
                profile=args.profile,
                region=args.region,
                instance_id=args.instance_id,
                bundle=bundle,
                overwrite=args.overwrite,
                dry_run=args.dry_run,
            )
            print(json.dumps(out, indent=2))
            return 0

        raise RuntimeError("Unknown command")

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
