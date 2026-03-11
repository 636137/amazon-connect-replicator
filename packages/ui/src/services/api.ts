import type { ConnectRegion, DescribeInstance, ExportBundleV1, InstanceSummary, ResourceType } from "../types/connect";

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

export async function snapshot(region: string, instanceId: string): Promise<any> {
  return json("/api/connect/snapshot", {
    method: "POST",
    body: JSON.stringify({ region, instanceId })
  });
}

export async function exportBundle(region: string, instanceId: string): Promise<ExportBundleV1> {
  return json("/api/connect/export", {
    method: "POST",
    body: JSON.stringify({ region, instanceId })
  });
}

export async function importBundle(params: {
  region: string;
  instanceId: string;
  bundle: ExportBundleV1;
  overwrite?: boolean;
  selectedResources?: ResourceType[];
}): Promise<any> {
  return json("/api/connect/import", {
    method: "POST",
    body: JSON.stringify(params)
  });
}
