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

        if existing and existing.get("Id"):
            if not overwrite:
                skipped_modules += 1
            else:
                if not dry_run:
                    client.update_contact_flow_module_content(
                        InstanceId=instance_id,
                        ContactFlowModuleId=existing["Id"],
                        Content=m.get("content") or "{}",
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
            Content=m.get("content") or "{}",
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
        content1 = _apply_replacements(str(raw_content), module_repl)

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
            content2 = _apply_replacements(_apply_replacements(raw_content, module_repl), flow_repl)
            client.update_contact_flow_content(
                InstanceId=instance_id,
                ContactFlowId=target_id,
                Content=content2,
            )

    return {
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
        description="Best-effort Amazon Connect exporter/importer using primitive Connect APIs (flows + modules)."
    )
    p.add_argument("--profile", default=None, help="AWS credential profile name (optional)")

    sub = p.add_subparsers(dest="cmd", required=True)

    exp = sub.add_parser("export", help="Export a bundle (flows + flow modules)")
    exp.add_argument("--region", required=True)
    exp.add_argument("--instance-id", required=True)
    exp.add_argument("--out", required=False, default="-", help="Output file path, or '-' for stdout")

    imp = sub.add_parser("import", help="Import a bundle into an existing instance")
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
