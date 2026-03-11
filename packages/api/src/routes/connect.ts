import {
  ConnectClient,
  DescribeInstanceCommand,
  ListInstancesCommand,
  ReplicateInstanceCommand
} from "@aws-sdk/client-connect";
import { Router } from "express";
import { z } from "zod";

import { CONNECT_REGIONS, isAllowedReplicationPair } from "../services/connectRegions.js";

function clientFor(region: string) {
  return new ConnectClient({ region });
}

export const connectRouter = Router();

connectRouter.get("/regions", (_req, res) => {
  res.status(200).json({ regions: CONNECT_REGIONS });
});

connectRouter.get("/instances", async (req, res) => {
  const q = z
    .object({ region: z.string().min(1) })
    .safeParse(req.query);

  if (!q.success) {
    return res.status(400).json({ error: "Missing or invalid region" });
  }

  const region = q.data.region;

  try {
    const c = clientFor(region);
    const out = await c.send(new ListInstancesCommand({ MaxResults: 100 }));
    return res.status(200).json({ instances: out.InstanceSummaryList || [] });
  } catch (e: any) {
    return res.status(500).json({ error: e?.message || String(e) });
  }
});

connectRouter.get("/instance", async (req, res) => {
  const q = z
    .object({ region: z.string().min(1), instanceId: z.string().min(1) })
    .safeParse(req.query);

  if (!q.success) {
    return res.status(400).json({ error: "Missing region or instanceId" });
  }

  const { region, instanceId } = q.data;

  try {
    const c = clientFor(region);
    const out = await c.send(new DescribeInstanceCommand({ InstanceId: instanceId }));
    return res.status(200).json({ instance: out.Instance });
  } catch (e: any) {
    return res.status(500).json({ error: e?.message || String(e) });
  }
});

connectRouter.get("/replication-status", async (req, res) => {
  const q = z
    .object({ region: z.string().min(1), instanceId: z.string().min(1) })
    .safeParse(req.query);

  if (!q.success) {
    return res.status(400).json({ error: "Missing region or instanceId" });
  }

  const { region, instanceId } = q.data;

  try {
    const c = clientFor(region);
    const out = await c.send(new DescribeInstanceCommand({ InstanceId: instanceId }));
    const status = out.Instance?.InstanceStatus || null;
    return res.status(200).json({ status, instance: out.Instance });
  } catch (e: any) {
    return res.status(500).json({ error: e?.message || String(e) });
  }
});

connectRouter.post("/snapshot", async (req, res) => {
  const body = z
    .object({ region: z.string().min(1), instanceId: z.string().min(1) })
    .safeParse(req.body);

  if (!body.success) {
    return res.status(400).json({ error: "Missing region or instanceId" });
  }

  const { region, instanceId } = body.data;

  try {
    const c = clientFor(region);
    const out = await c.send(new DescribeInstanceCommand({ InstanceId: instanceId }));

    return res.status(200).json({
      capturedAt: new Date().toISOString(),
      region,
      instanceId,
      instance: out.Instance
    });
  } catch (e: any) {
    return res.status(500).json({ error: e?.message || String(e) });
  }
});

connectRouter.post("/replicate", async (req, res) => {
  const body = z
    .object({
      sourceRegion: z.string().min(1),
      instanceId: z.string().min(1),
      replicaRegion: z.string().min(1),
      replicaAlias: z.string().min(1)
    })
    .safeParse(req.body);

  if (!body.success) {
    return res.status(400).json({ error: "Missing required fields" });
  }

  const { sourceRegion, instanceId, replicaRegion, replicaAlias } = body.data;

  if (!isAllowedReplicationPair(sourceRegion, replicaRegion)) {
    return res.status(400).json({
      error: `Region pair not supported for Connect Global Resiliency: ${sourceRegion} -> ${replicaRegion}`
    });
  }

  try {
    // Preflight: instance must be ACTIVE + SAML.
    const pre = await clientFor(sourceRegion).send(
      new DescribeInstanceCommand({ InstanceId: instanceId })
    );

    const status = pre.Instance?.InstanceStatus;
    const idm = pre.Instance?.IdentityManagementType;

    if (status !== "ACTIVE") {
      return res.status(400).json({
        error: `Source instance must be ACTIVE to replicate. Current: ${status}`,
        instance: pre.Instance
      });
    }

    if (idm !== "SAML") {
      return res.status(400).json({
        error: `Replication requires IdentityManagementType=SAML. Current: ${idm}`,
        instance: pre.Instance
      });
    }

    const out = await clientFor(sourceRegion).send(
      new ReplicateInstanceCommand({
        InstanceId: instanceId,
        ReplicaRegion: replicaRegion,
        ReplicaAlias: replicaAlias
      })
    );

    return res.status(200).json({ result: out });
  } catch (e: any) {
    return res.status(500).json({ error: e?.message || String(e) });
  }
});
