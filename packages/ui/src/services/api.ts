import type { ConnectRegion, DescribeInstance, InstanceSummary } from "../types/connect";

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "content-type": "application/json" },
    ...init
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = (data as any)?.error || `${res.status} ${res.statusText}`;
    throw new Error(msg);
  }
  return data as T;
}

export async function getRegions(): Promise<ConnectRegion[]> {
  const out = await json<{ regions: ConnectRegion[] }>("/api/connect/regions");
  return out.regions;
}

export async function listInstances(region: string): Promise<InstanceSummary[]> {
  const out = await json<{ instances: InstanceSummary[] }>(
    `/api/connect/instances?region=${encodeURIComponent(region)}`
  );
  return out.instances;
}

export async function describeInstance(region: string, instanceId: string): Promise<DescribeInstance | undefined> {
  const out = await json<{ instance?: DescribeInstance }>(
    `/api/connect/instance?region=${encodeURIComponent(region)}&instanceId=${encodeURIComponent(instanceId)}`
  );
  return out.instance;
}

export async function replicationStatus(region: string, instanceId: string): Promise<{ status: string | null; instance?: DescribeInstance }>{
  return json(`/api/connect/replication-status?region=${encodeURIComponent(region)}&instanceId=${encodeURIComponent(instanceId)}`);
}

export async function snapshot(region: string, instanceId: string): Promise<any> {
  return json("/api/connect/snapshot", {
    method: "POST",
    body: JSON.stringify({ region, instanceId })
  });
}

export async function replicate(params: {
  sourceRegion: string;
  instanceId: string;
  replicaRegion: string;
  replicaAlias: string;
}): Promise<any> {
  return json("/api/connect/replicate", {
    method: "POST",
    body: JSON.stringify(params)
  });
}
