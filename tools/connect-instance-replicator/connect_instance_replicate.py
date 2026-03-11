#!/usr/bin/env python3
"""
Amazon Connect Instance Replicator (v2)
Best-effort export/import of Connect configuration using primitive APIs.

Bundle v2 scope:
  - Hours of Operation
  - Agent Statuses
  - Security Profiles
  - User Hierarchy Groups
  - Queues (STANDARD)
  - Routing Profiles
  - Quick Connects (queue + phone; user-type skipped)
  - Contact Flow Modules
  - Contact Flows
"""

import argparse
import json
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError, ParamValidationError


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

INSTANCE_ATTRIBUTE_TYPES: List[str] = [
    "INBOUND_CALLS",
    "OUTBOUND_CALLS",
    "CONTACTFLOW_LOGS",
    "CONTACT_LENS",
    "AUTO_RESOLVE_BEST_VOICES",
    "USE_CUSTOM_TTS_VOICES",
    "EARLY_MEDIA",
    "MULTI_PARTY_CONFERENCE",
    "HIGH_VOLUME_OUTBOUND",
    "ENHANCED_CONTACT_MONITORING",
]


def _unsupported_reasons(content: str) -> List[str]:
    l = content.lower()
    reasons: List[str] = []
    if "/prompt/" in l:
        reasons.append("prompt")
    if "arn:aws:lex:" in l:
        reasons.append("lex")
    if "arn:aws:lambda:" in l:
        reasons.append("lambda")
    if "arn:aws:s3:::" in l:
        reasons.append("s3")
    if "/phone-number/" in l:
        reasons.append("phone-number")
    return reasons


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
    for src, dst in sorted(replacements, key=lambda t: len(t[0] or ""), reverse=True):
        if not src or src == dst:
            continue
        out = out.replace(src, dst)
    return out


def _drop_none(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


# =============================================================================
# EXPORT
# =============================================================================

def _export_hours_of_operations(client, instance_id: str) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    hours_summaries: List[Dict[str, Any]] = []
    for page in _paginate(client.list_hours_of_operations, InstanceId=instance_id, MaxResults=100):
        hours_summaries.extend(page.get("HoursOfOperationSummaryList") or [])

    hours_of_operations: List[Dict[str, Any]] = []
    hours_name_by_id: Dict[str, str] = {}

    for h in hours_summaries:
        hid = h.get("Id")
        if not hid:
            continue
        try:
            d = client.describe_hours_of_operation(InstanceId=instance_id, HoursOfOperationId=hid)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                print(f"WARN: skipping hours id {hid}: ResourceNotFoundException", file=sys.stderr)
                continue
            raise
        ho = d.get("HoursOfOperation") or {}
        if ho.get("Name"):
            hours_of_operations.append({
                "id": ho.get("HoursOfOperationId"),
                "arn": ho.get("HoursOfOperationArn"),
                "name": ho.get("Name"),
                "description": ho.get("Description"),
                "timeZone": ho.get("TimeZone"),
                "config": ho.get("Config"),
                "tags": ho.get("Tags"),
            })
            hours_name_by_id[str(ho["HoursOfOperationId"])] = str(ho["Name"])

    return hours_of_operations, hours_name_by_id


def _export_agent_statuses(client, instance_id: str) -> List[Dict[str, Any]]:
    summaries: List[Dict[str, Any]] = []
    for page in _paginate(client.list_agent_statuses, InstanceId=instance_id, MaxResults=100):
        summaries.extend(page.get("AgentStatusSummaryList") or [])

    agent_statuses: List[Dict[str, Any]] = []
    for s in summaries:
        sid = s.get("Id")
        if not sid:
            continue
        try:
            d = client.describe_agent_status(InstanceId=instance_id, AgentStatusId=sid)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                print(f"WARN: skipping agent status id {sid}: ResourceNotFoundException", file=sys.stderr)
                continue
            raise
        st = d.get("AgentStatus") or {}
        if st.get("Name"):
            agent_statuses.append({
                "id": st.get("AgentStatusId"),
                "arn": st.get("AgentStatusArn"),
                "name": st.get("Name"),
                "description": st.get("Description"),
                "type": st.get("Type"),
                "state": st.get("State"),
                "displayOrder": st.get("DisplayOrder"),
                "tags": st.get("Tags"),
            })
    return agent_statuses


def _export_security_profiles(client, instance_id: str) -> List[Dict[str, Any]]:
    summaries: List[Dict[str, Any]] = []
    for page in _paginate(client.list_security_profiles, InstanceId=instance_id, MaxResults=100):
        summaries.extend(page.get("SecurityProfileSummaryList") or [])

    security_profiles: List[Dict[str, Any]] = []
    for s in summaries:
        sid = s.get("Id")
        if not sid:
            continue
        try:
            d = client.describe_security_profile(InstanceId=instance_id, SecurityProfileId=sid)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                print(f"WARN: skipping security profile id {sid}: ResourceNotFoundException", file=sys.stderr)
                continue
            raise
        sp = d.get("SecurityProfile") or {}
        if sp.get("SecurityProfileName"):
            # Get permissions
            perms: List[str] = []
            try:
                for ppage in _paginate(client.list_security_profile_permissions, InstanceId=instance_id, SecurityProfileId=sid, MaxResults=100):
                    perms.extend(ppage.get("Permissions") or [])
            except ClientError:
                pass  # may not have permission to list permissions
            security_profiles.append({
                "id": sp.get("Id"),
                "arn": sp.get("Arn"),
                "name": sp.get("SecurityProfileName"),
                "description": sp.get("Description"),
                "permissions": perms,
                "allowedAccessControlTags": sp.get("AllowedAccessControlTags"),
                "tagRestrictedResources": sp.get("TagRestrictedResources"),
                "tags": sp.get("Tags"),
            })
    return security_profiles


def _export_user_hierarchy_groups(client, instance_id: str) -> List[Dict[str, Any]]:
    summaries: List[Dict[str, Any]] = []
    for page in _paginate(client.list_user_hierarchy_groups, InstanceId=instance_id, MaxResults=100):
        summaries.extend(page.get("UserHierarchyGroupSummaryList") or [])

    hierarchy_groups: List[Dict[str, Any]] = []
    for s in summaries:
        sid = s.get("Id")
        if not sid:
            continue
        try:
            d = client.describe_user_hierarchy_group(InstanceId=instance_id, HierarchyGroupId=sid)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                print(f"WARN: skipping hierarchy group id {sid}: ResourceNotFoundException", file=sys.stderr)
                continue
            raise
        hg = d.get("HierarchyGroup") or {}
        if hg.get("Name"):
            hierarchy_groups.append({
                "id": hg.get("Id"),
                "arn": hg.get("Arn"),
                "name": hg.get("Name"),
                "levelId": hg.get("LevelId"),
                "hierarchyPath": hg.get("HierarchyPath"),
                "tags": hg.get("Tags"),
            })
    return hierarchy_groups


def _export_queues(client, instance_id: str, hours_name_by_id: Dict[str, str]) -> List[Dict[str, Any]]:
    queue_summaries: List[Dict[str, Any]] = []
    for page in _paginate(client.list_queues, InstanceId=instance_id, MaxResults=100, QueueTypes=["STANDARD"]):
        queue_summaries.extend(page.get("QueueSummaryList") or [])

    queues: List[Dict[str, Any]] = []
    for q in queue_summaries:
        qid = q.get("Id")
        if not qid:
            continue
        try:
            d = client.describe_queue(InstanceId=instance_id, QueueId=qid)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                print(f"WARN: skipping queue id {qid}: ResourceNotFoundException", file=sys.stderr)
                continue
            raise
        qq = d.get("Queue") or {}
        if qq.get("Name"):
            hours_id = qq.get("HoursOfOperationId")
            queues.append({
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
            })
    return queues


def _export_routing_profiles(client, instance_id: str) -> List[Dict[str, Any]]:
    summaries: List[Dict[str, Any]] = []
    for page in _paginate(client.list_routing_profiles, InstanceId=instance_id, MaxResults=100):
        summaries.extend(page.get("RoutingProfileSummaryList") or [])

    routing_profiles: List[Dict[str, Any]] = []
    for s in summaries:
        sid = s.get("Id")
        if not sid:
            continue
        try:
            d = client.describe_routing_profile(InstanceId=instance_id, RoutingProfileId=sid)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                print(f"WARN: skipping routing profile id {sid}: ResourceNotFoundException", file=sys.stderr)
                continue
            raise
        rp = d.get("RoutingProfile") or {}
        if rp.get("Name"):
            # Get queue configs
            queue_configs: List[Dict[str, Any]] = []
            try:
                for qpage in _paginate(client.list_routing_profile_queues, InstanceId=instance_id, RoutingProfileId=sid, MaxResults=100):
                    queue_configs.extend(qpage.get("RoutingProfileQueueConfigSummaryList") or [])
            except ClientError:
                pass
            routing_profiles.append({
                "id": rp.get("RoutingProfileId"),
                "arn": rp.get("RoutingProfileArn"),
                "name": rp.get("Name"),
                "description": rp.get("Description"),
                "defaultOutboundQueueId": rp.get("DefaultOutboundQueueId"),
                "mediaConcurrencies": rp.get("MediaConcurrencies"),
                "queueConfigs": queue_configs,
                "tags": rp.get("Tags"),
            })
    return routing_profiles


def _export_quick_connects(client, instance_id: str) -> List[Dict[str, Any]]:
    summaries: List[Dict[str, Any]] = []
    for page in _paginate(client.list_quick_connects, InstanceId=instance_id, MaxResults=100):
        summaries.extend(page.get("QuickConnectSummaryList") or [])

    quick_connects: List[Dict[str, Any]] = []
    for s in summaries:
        sid = s.get("Id")
        if not sid:
            continue
        try:
            d = client.describe_quick_connect(InstanceId=instance_id, QuickConnectId=sid)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                print(f"WARN: skipping quick connect id {sid}: ResourceNotFoundException", file=sys.stderr)
                continue
            raise
        qc = d.get("QuickConnect") or {}
        if qc.get("Name"):
            quick_connects.append({
                "id": qc.get("QuickConnectId"),
                "arn": qc.get("QuickConnectARN"),
                "name": qc.get("Name"),
                "description": qc.get("Description"),
                "quickConnectConfig": qc.get("QuickConnectConfig"),
                "tags": qc.get("Tags"),
            })
    return quick_connects


def _export_flow_modules(client, instance_id: str) -> List[Dict[str, Any]]:
    modules: List[Dict[str, Any]] = []
    for page in _paginate(client.list_contact_flow_modules, InstanceId=instance_id, MaxResults=100):
        modules.extend(page.get("ContactFlowModulesSummaryList") or [])

    flow_modules: List[Dict[str, Any]] = []
    for m in modules:
        mid = m.get("Id")
        if not mid:
            continue
        try:
            d = client.describe_contact_flow_module(InstanceId=instance_id, ContactFlowModuleId=mid)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                print(f"WARN: skipping module id {mid}: ResourceNotFoundException", file=sys.stderr)
                continue
            raise
        mod = d.get("ContactFlowModule") or {}
        if mod.get("Name"):
            flow_modules.append({
                "id": mod.get("Id"),
                "arn": mod.get("Arn"),
                "name": mod.get("Name"),
                "description": mod.get("Description"),
                "state": mod.get("State"),
                "status": mod.get("Status"),
                "content": mod.get("Content"),
                "settings": mod.get("Settings"),
                "tags": mod.get("Tags"),
            })
    return flow_modules


def _export_contact_flows(client, instance_id: str) -> List[Dict[str, Any]]:
    flows: List[Dict[str, Any]] = []
    for page in _paginate(client.list_contact_flows, InstanceId=instance_id, ContactFlowTypes=CONTACT_FLOW_TYPES, MaxResults=100):
        flows.extend(page.get("ContactFlowSummaryList") or [])

    contact_flows: List[Dict[str, Any]] = []
    for f in flows:
        fid = f.get("Id")
        if not fid:
            continue
        try:
            d = client.describe_contact_flow(InstanceId=instance_id, ContactFlowId=fid)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                print(f"WARN: skipping flow id {fid}: ResourceNotFoundException", file=sys.stderr)
                continue
            raise
        flow = d.get("ContactFlow") or {}
        if flow.get("Name") and flow.get("Type"):
            contact_flows.append({
                "id": flow.get("Id"),
                "arn": flow.get("Arn"),
                "name": flow.get("Name"),
                "type": flow.get("Type"),
                "description": flow.get("Description"),
                "state": flow.get("State"),
                "status": flow.get("Status"),
                "content": flow.get("Content"),
                "tags": flow.get("Tags"),
            })
    return contact_flows


def _export_instance_attributes(client, instance_id: str) -> List[Dict[str, Any]]:
    attrs: List[Dict[str, Any]] = []
    for attr_type in INSTANCE_ATTRIBUTE_TYPES:
        try:
            resp = client.describe_instance_attribute(InstanceId=instance_id, AttributeType=attr_type)
            a = resp.get("Attribute") or {}
            attrs.append({
                "attributeType": a.get("AttributeType"),
                "value": a.get("Value"),
            })
        except ClientError:
            pass
    return attrs


def export_bundle(*, profile: Optional[str], region: str, instance_id: str) -> Dict[str, Any]:
    client = _connect_client(profile, region)

    hours_of_operations, hours_name_by_id = _export_hours_of_operations(client, instance_id)
    agent_statuses = _export_agent_statuses(client, instance_id)
    security_profiles = _export_security_profiles(client, instance_id)
    user_hierarchy_groups = _export_user_hierarchy_groups(client, instance_id)
    queues = _export_queues(client, instance_id, hours_name_by_id)
    routing_profiles = _export_routing_profiles(client, instance_id)
    quick_connects = _export_quick_connects(client, instance_id)
    flow_modules = _export_flow_modules(client, instance_id)
    contact_flows = _export_contact_flows(client, instance_id)
    instance_attributes = _export_instance_attributes(client, instance_id)

    return {
        "version": 2,
        "exportedAt": __import__("datetime").datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "source": {"region": region, "instanceId": instance_id},
        "hoursOfOperations": hours_of_operations,
        "agentStatuses": agent_statuses,
        "securityProfiles": security_profiles,
        "userHierarchyGroups": user_hierarchy_groups,
        "queues": queues,
        "routingProfiles": routing_profiles,
        "quickConnects": quick_connects,
        "flowModules": flow_modules,
        "contactFlows": contact_flows,
        "instanceAttributes": instance_attributes,
    }


# =============================================================================
# IMPORT
# =============================================================================

def import_bundle(
    *,
    profile: Optional[str],
    region: str,
    instance_id: str,
    bundle: Dict[str, Any],
    overwrite: bool,
    dry_run: bool,
    continue_on_error: bool = False,
    skip_unsupported: bool = False,
) -> Dict[str, Any]:
    version = bundle.get("version")
    if version not in (1, 2):
        raise ValueError(f"Unsupported bundle version: {version}")

    client = _connect_client(profile, region)

    # Replacement mappings (source -> target)
    replacements: List[Tuple[str, str]] = []

    # Stats
    stats: Dict[str, int] = {}
    errors: Dict[str, List[Dict[str, Any]]] = {}

    def inc(key: str):
        stats[key] = stats.get(key, 0) + 1

    def add_error(category: str, err: Dict[str, Any]):
        if category not in errors:
            errors[category] = []
        if len(errors[category]) < 50:
            errors[category].append(err)

    def add_repl(src_id: Optional[str], dst_id: Optional[str], src_arn: Optional[str] = None, dst_arn: Optional[str] = None):
        if src_id and dst_id:
            replacements.append((src_id, dst_id))
        if src_arn and dst_arn:
            replacements.append((src_arn, dst_arn))

    # -------------------------------------------------------------------------
    # 1. Hours of Operation
    # -------------------------------------------------------------------------
    existing_hours: Dict[str, Dict[str, Any]] = {}
    for page in _paginate(client.list_hours_of_operations, InstanceId=instance_id, MaxResults=100):
        for h in page.get("HoursOfOperationSummaryList") or []:
            if h.get("Name"):
                existing_hours[h["Name"]] = h

    for h in bundle.get("hoursOfOperations") or []:
        name = h.get("name")
        if not name:
            continue
        existing = existing_hours.get(name)

        if existing and existing.get("Id"):
            add_repl(h.get("id"), existing["Id"], h.get("arn"), existing.get("Arn"))
            if not overwrite:
                inc("skippedHours")
                continue
            if dry_run:
                inc("updatedHours")
                continue
            try:
                client.update_hours_of_operation(**_drop_none({
                    "InstanceId": instance_id,
                    "HoursOfOperationId": existing["Id"],
                    "Name": name,
                    "Description": h.get("description"),
                    "TimeZone": h.get("timeZone"),
                    "Config": h.get("config"),
                }))
                inc("updatedHours")
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedHours")
                add_error("hours", {"name": name, "action": "update", "error": str(e)})
        else:
            if dry_run:
                inc("createdHours")
                continue
            try:
                resp = client.create_hours_of_operation(**_drop_none({
                    "InstanceId": instance_id,
                    "Name": name,
                    "Description": h.get("description"),
                    "TimeZone": h.get("timeZone"),
                    "Config": h.get("config"),
                    "Tags": h.get("tags"),
                }))
                inc("createdHours")
                existing_hours[name] = {"Id": resp.get("HoursOfOperationId"), "Arn": resp.get("HoursOfOperationArn"), "Name": name}
                add_repl(h.get("id"), resp.get("HoursOfOperationId"), h.get("arn"), resp.get("HoursOfOperationArn"))
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedHours")
                add_error("hours", {"name": name, "action": "create", "error": str(e)})

    # -------------------------------------------------------------------------
    # 2. Agent Statuses
    # -------------------------------------------------------------------------
    existing_agent_statuses: Dict[str, Dict[str, Any]] = {}
    for page in _paginate(client.list_agent_statuses, InstanceId=instance_id, MaxResults=100):
        for s in page.get("AgentStatusSummaryList") or []:
            if s.get("Name"):
                existing_agent_statuses[s["Name"]] = s

    for s in bundle.get("agentStatuses") or []:
        name = s.get("name")
        if not name:
            continue
        existing = existing_agent_statuses.get(name)

        if existing and existing.get("Id"):
            add_repl(s.get("id"), existing["Id"], s.get("arn"), existing.get("Arn"))
            if not overwrite:
                inc("skippedAgentStatuses")
                continue
            if dry_run:
                inc("updatedAgentStatuses")
                continue
            try:
                client.update_agent_status(**_drop_none({
                    "InstanceId": instance_id,
                    "AgentStatusId": existing["Id"],
                    "Name": name,
                    "Description": s.get("description"),
                    "State": s.get("state"),
                    "DisplayOrder": s.get("displayOrder"),
                    "ResetOrderNumber": False,
                }))
                inc("updatedAgentStatuses")
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedAgentStatuses")
                add_error("agentStatuses", {"name": name, "action": "update", "error": str(e)})
        else:
            if dry_run:
                inc("createdAgentStatuses")
                continue
            try:
                resp = client.create_agent_status(**_drop_none({
                    "InstanceId": instance_id,
                    "Name": name,
                    "Description": s.get("description"),
                    "State": s.get("state"),
                    "DisplayOrder": s.get("displayOrder"),
                    "Tags": s.get("tags"),
                }))
                inc("createdAgentStatuses")
                existing_agent_statuses[name] = {"Id": resp.get("AgentStatusId"), "Arn": resp.get("AgentStatusARN"), "Name": name}
                add_repl(s.get("id"), resp.get("AgentStatusId"), s.get("arn"), resp.get("AgentStatusARN"))
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedAgentStatuses")
                add_error("agentStatuses", {"name": name, "action": "create", "error": str(e)})

    # -------------------------------------------------------------------------
    # 3. Security Profiles
    # -------------------------------------------------------------------------
    existing_security_profiles: Dict[str, Dict[str, Any]] = {}
    for page in _paginate(client.list_security_profiles, InstanceId=instance_id, MaxResults=100):
        for sp in page.get("SecurityProfileSummaryList") or []:
            if sp.get("Name"):
                existing_security_profiles[sp["Name"]] = sp

    for sp in bundle.get("securityProfiles") or []:
        name = sp.get("name")
        if not name:
            continue
        existing = existing_security_profiles.get(name)

        if existing and existing.get("Id"):
            add_repl(sp.get("id"), existing["Id"], sp.get("arn"), existing.get("Arn"))
            if not overwrite:
                inc("skippedSecurityProfiles")
                continue
            if dry_run:
                inc("updatedSecurityProfiles")
                continue
            try:
                update_args = _drop_none({
                    "InstanceId": instance_id,
                    "SecurityProfileId": existing["Id"],
                    "Description": sp.get("description"),
                    "Permissions": sp.get("permissions") or None,
                    "AllowedAccessControlTags": sp.get("allowedAccessControlTags"),
                    "TagRestrictedResources": sp.get("tagRestrictedResources"),
                })
                client.update_security_profile(**update_args)
                inc("updatedSecurityProfiles")
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedSecurityProfiles")
                add_error("securityProfiles", {"name": name, "action": "update", "error": str(e)})
        else:
            if dry_run:
                inc("createdSecurityProfiles")
                continue
            try:
                resp = client.create_security_profile(**_drop_none({
                    "InstanceId": instance_id,
                    "SecurityProfileName": name,
                    "Description": sp.get("description"),
                    "Permissions": sp.get("permissions") or None,
                    "AllowedAccessControlTags": sp.get("allowedAccessControlTags"),
                    "TagRestrictedResources": sp.get("tagRestrictedResources"),
                    "Tags": sp.get("tags"),
                }))
                inc("createdSecurityProfiles")
                existing_security_profiles[name] = {"Id": resp.get("SecurityProfileId"), "Arn": resp.get("SecurityProfileArn"), "Name": name}
                add_repl(sp.get("id"), resp.get("SecurityProfileId"), sp.get("arn"), resp.get("SecurityProfileArn"))
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedSecurityProfiles")
                add_error("securityProfiles", {"name": name, "action": "create", "error": str(e)})

    # -------------------------------------------------------------------------
    # 4. User Hierarchy Groups
    # -------------------------------------------------------------------------
    existing_hierarchy_groups: Dict[str, Dict[str, Any]] = {}
    for page in _paginate(client.list_user_hierarchy_groups, InstanceId=instance_id, MaxResults=100):
        for hg in page.get("UserHierarchyGroupSummaryList") or []:
            if hg.get("Name"):
                existing_hierarchy_groups[hg["Name"]] = hg

    for hg in bundle.get("userHierarchyGroups") or []:
        name = hg.get("name")
        if not name:
            continue
        existing = existing_hierarchy_groups.get(name)

        if existing and existing.get("Id"):
            add_repl(hg.get("id"), existing["Id"], hg.get("arn"), existing.get("Arn"))
            if not overwrite:
                inc("skippedHierarchyGroups")
                continue
            if dry_run:
                inc("updatedHierarchyGroups")
                continue
            try:
                client.update_user_hierarchy_group_name(InstanceId=instance_id, HierarchyGroupId=existing["Id"], Name=name)
                inc("updatedHierarchyGroups")
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedHierarchyGroups")
                add_error("hierarchyGroups", {"name": name, "action": "update", "error": str(e)})
        else:
            if dry_run:
                inc("createdHierarchyGroups")
                continue
            try:
                # Note: parent hierarchy resolution is complex; we skip parent for now
                resp = client.create_user_hierarchy_group(**_drop_none({
                    "InstanceId": instance_id,
                    "Name": name,
                    "Tags": hg.get("tags"),
                }))
                inc("createdHierarchyGroups")
                existing_hierarchy_groups[name] = {"Id": resp.get("HierarchyGroupId"), "Arn": resp.get("HierarchyGroupArn"), "Name": name}
                add_repl(hg.get("id"), resp.get("HierarchyGroupId"), hg.get("arn"), resp.get("HierarchyGroupArn"))
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedHierarchyGroups")
                add_error("hierarchyGroups", {"name": name, "action": "create", "error": str(e)})

    # -------------------------------------------------------------------------
    # 5. Queues
    # -------------------------------------------------------------------------
    existing_queues: Dict[str, Dict[str, Any]] = {}
    for page in _paginate(client.list_queues, InstanceId=instance_id, MaxResults=100):
        for q in page.get("QueueSummaryList") or []:
            if q.get("Name"):
                existing_queues[q["Name"]] = q

    def _resolve_hours_id(q: Dict[str, Any]) -> Optional[str]:
        if q.get("hoursOfOperationName"):
            eh = existing_hours.get(str(q["hoursOfOperationName"]))
            if eh and eh.get("Id"):
                return str(eh["Id"])
        if q.get("hoursOfOperationId"):
            for src, dst in replacements:
                if src == q["hoursOfOperationId"]:
                    return dst
        return None

    for q in bundle.get("queues") or []:
        name = q.get("name")
        if not name:
            continue
        existing = existing_queues.get(name)
        target_hours_id = _resolve_hours_id(q)

        if existing and existing.get("Id"):
            add_repl(q.get("id"), existing["Id"], q.get("arn"), existing.get("Arn"))
            if not overwrite:
                inc("skippedQueues")
                continue
            if dry_run:
                inc("updatedQueues")
                continue
            try:
                client.update_queue_name(InstanceId=instance_id, QueueId=existing["Id"], Name=name)
                if q.get("description") is not None:
                    client.update_queue_name(InstanceId=instance_id, QueueId=existing["Id"], Description=q.get("description"))
                if target_hours_id:
                    client.update_queue_hours_of_operation(InstanceId=instance_id, QueueId=existing["Id"], HoursOfOperationId=target_hours_id)
                if q.get("maxContacts") is not None:
                    client.update_queue_max_contacts(InstanceId=instance_id, QueueId=existing["Id"], MaxContacts=q["maxContacts"])
                if q.get("status"):
                    client.update_queue_status(InstanceId=instance_id, QueueId=existing["Id"], Status=q["status"])
                inc("updatedQueues")
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedQueues")
                add_error("queues", {"name": name, "action": "update", "error": str(e)})
        else:
            if dry_run:
                inc("createdQueues")
                continue
            if not target_hours_id:
                if continue_on_error:
                    inc("failedQueues")
                    add_error("queues", {"name": name, "action": "create", "error": "No hours-of-operation mapping found"})
                    continue
                raise ValueError(f"Queue {name}: could not resolve hours-of-operation")
            try:
                resp = client.create_queue(**_drop_none({
                    "InstanceId": instance_id,
                    "Name": name,
                    "Description": q.get("description"),
                    "HoursOfOperationId": target_hours_id,
                    "MaxContacts": q.get("maxContacts"),
                    "OutboundCallerConfig": q.get("outboundCallerConfig"),
                    "Tags": q.get("tags"),
                }))
                inc("createdQueues")
                existing_queues[name] = {"Id": resp.get("QueueId"), "Arn": resp.get("QueueArn"), "Name": name}
                add_repl(q.get("id"), resp.get("QueueId"), q.get("arn"), resp.get("QueueArn"))
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedQueues")
                add_error("queues", {"name": name, "action": "create", "error": str(e)})

    # -------------------------------------------------------------------------
    # 6. Routing Profiles
    # -------------------------------------------------------------------------
    existing_routing_profiles: Dict[str, Dict[str, Any]] = {}
    for page in _paginate(client.list_routing_profiles, InstanceId=instance_id, MaxResults=100):
        for rp in page.get("RoutingProfileSummaryList") or []:
            if rp.get("Name"):
                existing_routing_profiles[rp["Name"]] = rp

    for rp in bundle.get("routingProfiles") or []:
        name = rp.get("name")
        if not name:
            continue
        existing = existing_routing_profiles.get(name)

        # Resolve default outbound queue
        default_queue_id = None
        if rp.get("defaultOutboundQueueId"):
            for src, dst in replacements:
                if src == rp["defaultOutboundQueueId"]:
                    default_queue_id = dst
                    break
            if not default_queue_id:
                # Try to find by name in existing queues
                for eq_name, eq in existing_queues.items():
                    if eq.get("Id") == rp["defaultOutboundQueueId"]:
                        default_queue_id = eq["Id"]
                        break

        if existing and existing.get("Id"):
            add_repl(rp.get("id"), existing["Id"], rp.get("arn"), existing.get("Arn"))
            if not overwrite:
                inc("skippedRoutingProfiles")
                continue
            if dry_run:
                inc("updatedRoutingProfiles")
                continue
            try:
                client.update_routing_profile_name(InstanceId=instance_id, RoutingProfileId=existing["Id"], Name=name, Description=rp.get("description"))
                if default_queue_id:
                    client.update_routing_profile_default_outbound_queue(InstanceId=instance_id, RoutingProfileId=existing["Id"], DefaultOutboundQueueId=default_queue_id)
                if rp.get("mediaConcurrencies"):
                    client.update_routing_profile_concurrency(InstanceId=instance_id, RoutingProfileId=existing["Id"], MediaConcurrencies=rp["mediaConcurrencies"])
                inc("updatedRoutingProfiles")
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedRoutingProfiles")
                add_error("routingProfiles", {"name": name, "action": "update", "error": str(e)})
        else:
            if dry_run:
                inc("createdRoutingProfiles")
                continue
            if not default_queue_id:
                # Use first available queue
                for eq in existing_queues.values():
                    if eq.get("Id"):
                        default_queue_id = eq["Id"]
                        break
            if not default_queue_id:
                if continue_on_error:
                    inc("failedRoutingProfiles")
                    add_error("routingProfiles", {"name": name, "action": "create", "error": "No default outbound queue available"})
                    continue
                raise ValueError(f"Routing profile {name}: no default outbound queue available")
            try:
                resp = client.create_routing_profile(**_drop_none({
                    "InstanceId": instance_id,
                    "Name": name,
                    "Description": rp.get("description"),
                    "DefaultOutboundQueueId": default_queue_id,
                    "MediaConcurrencies": rp.get("mediaConcurrencies") or [{"Channel": "VOICE", "Concurrency": 1}],
                    "Tags": rp.get("tags"),
                }))
                inc("createdRoutingProfiles")
                existing_routing_profiles[name] = {"Id": resp.get("RoutingProfileId"), "Arn": resp.get("RoutingProfileArn"), "Name": name}
                add_repl(rp.get("id"), resp.get("RoutingProfileId"), rp.get("arn"), resp.get("RoutingProfileArn"))
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedRoutingProfiles")
                add_error("routingProfiles", {"name": name, "action": "create", "error": str(e)})

    # -------------------------------------------------------------------------
    # 7. Quick Connects
    # -------------------------------------------------------------------------
    existing_quick_connects: Dict[str, Dict[str, Any]] = {}
    for page in _paginate(client.list_quick_connects, InstanceId=instance_id, MaxResults=100):
        for qc in page.get("QuickConnectSummaryList") or []:
            if qc.get("Name"):
                existing_quick_connects[qc["Name"]] = qc

    for qc in bundle.get("quickConnects") or []:
        name = qc.get("name")
        if not name:
            continue
        cfg = qc.get("quickConnectConfig") or {}
        qc_type = cfg.get("QuickConnectType")

        # Skip user-type quick connects (require user replication)
        if qc_type == "USER":
            inc("skippedQuickConnectsUser")
            continue

        existing = existing_quick_connects.get(name)

        # Rewrite queue references in config
        if qc_type == "QUEUE" and cfg.get("QueueConfig", {}).get("QueueId"):
            orig_queue_id = cfg["QueueConfig"]["QueueId"]
            for src, dst in replacements:
                if src == orig_queue_id:
                    cfg["QueueConfig"]["QueueId"] = dst
                    break

        if existing and existing.get("Id"):
            add_repl(qc.get("id"), existing["Id"], qc.get("arn"), existing.get("Arn"))
            if not overwrite:
                inc("skippedQuickConnects")
                continue
            if dry_run:
                inc("updatedQuickConnects")
                continue
            try:
                client.update_quick_connect_config(InstanceId=instance_id, QuickConnectId=existing["Id"], QuickConnectConfig=cfg)
                if qc.get("name"):
                    client.update_quick_connect_name(InstanceId=instance_id, QuickConnectId=existing["Id"], Name=name, Description=qc.get("description"))
                inc("updatedQuickConnects")
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedQuickConnects")
                add_error("quickConnects", {"name": name, "action": "update", "error": str(e)})
        else:
            if dry_run:
                inc("createdQuickConnects")
                continue
            try:
                resp = client.create_quick_connect(**_drop_none({
                    "InstanceId": instance_id,
                    "Name": name,
                    "Description": qc.get("description"),
                    "QuickConnectConfig": cfg,
                    "Tags": qc.get("tags"),
                }))
                inc("createdQuickConnects")
                existing_quick_connects[name] = {"Id": resp.get("QuickConnectId"), "Arn": resp.get("QuickConnectARN"), "Name": name}
                add_repl(qc.get("id"), resp.get("QuickConnectId"), qc.get("arn"), resp.get("QuickConnectARN"))
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedQuickConnects")
                add_error("quickConnects", {"name": name, "action": "create", "error": str(e)})

    # -------------------------------------------------------------------------
    # 8. Flow Modules
    # -------------------------------------------------------------------------
    existing_modules: Dict[str, Dict[str, Any]] = {}
    for page in _paginate(client.list_contact_flow_modules, InstanceId=instance_id, MaxResults=100):
        for m in page.get("ContactFlowModulesSummaryList") or []:
            if m.get("Name"):
                existing_modules[m["Name"]] = m

    for m in bundle.get("flowModules") or []:
        name = m.get("name")
        if not name:
            continue
        content = m.get("content") or ""

        if skip_unsupported:
            reasons = _unsupported_reasons(content)
            if reasons:
                inc("skippedUnsupportedModules")
                continue

        existing = existing_modules.get(name)

        if existing and existing.get("Id"):
            add_repl(m.get("id"), existing["Id"], m.get("arn"), existing.get("Arn"))
            if not overwrite:
                inc("skippedModules")
                continue
            if dry_run:
                inc("updatedModules")
                continue
            try:
                new_content = _apply_replacements(content, replacements)
                client.update_contact_flow_module_content(InstanceId=instance_id, ContactFlowModuleId=existing["Id"], Content=new_content)
                inc("updatedModules")
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedModules")
                add_error("modules", {"name": name, "action": "update", "error": str(e)})
        else:
            if dry_run:
                inc("createdModules")
                continue
            try:
                new_content = _apply_replacements(content, replacements)
                resp = client.create_contact_flow_module(**_drop_none({
                    "InstanceId": instance_id,
                    "Name": name,
                    "Description": m.get("description"),
                    "Content": new_content,
                    "Tags": m.get("tags"),
                }))
                inc("createdModules")
                existing_modules[name] = {"Id": resp.get("Id"), "Arn": resp.get("Arn"), "Name": name}
                add_repl(m.get("id"), resp.get("Id"), m.get("arn"), resp.get("Arn"))
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedModules")
                add_error("modules", {"name": name, "action": "create", "error": str(e)})

    # -------------------------------------------------------------------------
    # 9. Contact Flows
    # -------------------------------------------------------------------------
    existing_flows: Dict[str, Dict[str, Any]] = {}
    for page in _paginate(client.list_contact_flows, InstanceId=instance_id, ContactFlowTypes=CONTACT_FLOW_TYPES, MaxResults=100):
        for f in page.get("ContactFlowSummaryList") or []:
            if f.get("Name") and f.get("ContactFlowType"):
                key = f"{f['ContactFlowType']}|{f['Name']}"
                existing_flows[key] = f

    # Pre-populate replacements for existing flows (for cross-flow refs)
    for src_flow in bundle.get("contactFlows") or []:
        key = f"{src_flow.get('type')}|{src_flow.get('name')}"
        existing = existing_flows.get(key)
        if existing and existing.get("Id"):
            add_repl(src_flow.get("id"), existing["Id"], src_flow.get("arn"), existing.get("Arn"))

    second_pass_flows: List[Tuple[Dict[str, Any], str]] = []

    for f in bundle.get("contactFlows") or []:
        name = f.get("name")
        flow_type = f.get("type")
        if not name or not flow_type:
            continue
        content = f.get("content") or ""
        key = f"{flow_type}|{name}"

        if skip_unsupported:
            reasons = _unsupported_reasons(content)
            if reasons:
                inc("skippedUnsupportedFlows")
                continue

        existing = existing_flows.get(key)
        new_content = _apply_replacements(content, replacements)

        if existing and existing.get("Id"):
            if not overwrite:
                inc("skippedFlows")
                continue
            if dry_run:
                inc("updatedFlows")
                continue
            try:
                client.update_contact_flow_content(InstanceId=instance_id, ContactFlowId=existing["Id"], Content=new_content)
                inc("updatedFlows")
                second_pass_flows.append((f, existing["Id"]))
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedFlows")
                add_error("flows", {"name": name, "type": flow_type, "action": "update", "error": str(e)})
        else:
            if dry_run:
                inc("createdFlows")
                continue
            try:
                resp = client.create_contact_flow(**_drop_none({
                    "InstanceId": instance_id,
                    "Name": name,
                    "Type": flow_type,
                    "Description": f.get("description"),
                    "Content": new_content,
                    "Tags": f.get("tags"),
                }))
                inc("createdFlows")
                new_id = resp.get("ContactFlowId")
                new_arn = resp.get("ContactFlowArn")
                existing_flows[key] = {"Id": new_id, "Arn": new_arn, "Name": name, "ContactFlowType": flow_type}
                add_repl(f.get("id"), new_id, f.get("arn"), new_arn)
                second_pass_flows.append((f, new_id))
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedFlows")
                add_error("flows", {"name": name, "type": flow_type, "action": "create", "error": str(e)})

    # Second pass for cross-flow references
    if not dry_run:
        for src_flow, target_id in second_pass_flows:
            content = src_flow.get("content") or ""
            content2 = _apply_replacements(content, replacements)
            try:
                client.update_contact_flow_content(InstanceId=instance_id, ContactFlowId=target_id, Content=content2)
            except (ClientError, ParamValidationError) as e:
                if not continue_on_error:
                    raise
                inc("failedFlows")
                add_error("flows", {"name": src_flow.get("name"), "type": src_flow.get("type"), "action": "secondPassUpdate", "error": str(e)})

    # -------------------------------------------------------------------------
    # 10. Instance Attributes (optional sync)
    # -------------------------------------------------------------------------
    for attr in bundle.get("instanceAttributes") or []:
        attr_type = attr.get("attributeType")
        value = attr.get("value")
        if not attr_type or value is None:
            continue
        if dry_run:
            inc("updatedInstanceAttributes")
            continue
        try:
            client.update_instance_attribute(InstanceId=instance_id, AttributeType=attr_type, Value=value)
            inc("updatedInstanceAttributes")
        except (ClientError, ParamValidationError) as e:
            if not continue_on_error:
                raise
            inc("failedInstanceAttributes")
            add_error("instanceAttributes", {"attributeType": attr_type, "error": str(e)})

    return {
        **stats,
        "errors": errors,
        "dryRun": dry_run,
        "overwrite": overwrite,
        "continueOnError": continue_on_error,
        "skipUnsupported": skip_unsupported,
    }


# =============================================================================
# CLI
# =============================================================================

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Best-effort Amazon Connect exporter/importer using primitive Connect APIs (v2: hours, agent statuses, security profiles, hierarchy groups, queues, routing profiles, quick connects, modules, flows)."
    )
    p.add_argument("--profile", default=None, help="AWS credential profile name (optional)")

    sub = p.add_subparsers(dest="cmd", required=True)

    exp = sub.add_parser("export", help="Export a bundle (v2)")
    exp.add_argument("--region", required=True)
    exp.add_argument("--instance-id", required=True)
    exp.add_argument("--out", required=False, default="-", help="Output file path, or '-' for stdout")

    imp = sub.add_parser("import", help="Import a bundle into an existing instance")
    imp.add_argument("--region", required=True)
    imp.add_argument("--instance-id", required=True)
    imp.add_argument("--in", dest="in_path", required=True, help="Input bundle JSON path")
    imp.add_argument("--overwrite", action="store_true", help="Overwrite (update content) if resource exists")
    imp.add_argument("--dry-run", action="store_true", help="Print what would happen, but do not call Create/Update")
    imp.add_argument("--continue-on-error", action="store_true", help="Continue importing after errors")
    imp.add_argument("--skip-unsupported", action="store_true", help="Skip flows/modules with external deps")

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
                print(f"Wrote bundle: {args.out}", file=sys.stderr)
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
                continue_on_error=args.continue_on_error,
                skip_unsupported=args.skip_unsupported,
            )
            print(json.dumps(out, indent=2))
            return 0

        raise RuntimeError("Unknown command")

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
