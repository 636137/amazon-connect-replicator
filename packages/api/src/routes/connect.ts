import {
  ConnectClient,
  CreateContactFlowCommand,
  CreateContactFlowModuleCommand,
  DescribeContactFlowCommand,
  DescribeContactFlowModuleCommand,
  DescribeInstanceCommand,
  ListContactFlowModulesCommand,
  ListContactFlowsCommand,
  ListInstancesCommand,
  UpdateContactFlowContentCommand,
  UpdateContactFlowModuleContentCommand
} from "@aws-sdk/client-connect";
import { Router } from "express";
import { z } from "zod";

import { CONNECT_REGIONS } from "../services/connectRegions.js";

function clientFor(region: string) {
  return new ConnectClient({ region });
}

const CONTACT_FLOW_TYPES = [
  "CONTACT_FLOW",
  "CUSTOMER_QUEUE",
  "CUSTOMER_HOLD",
  "CUSTOMER_WHISPER",
  "AGENT_HOLD",
  "AGENT_WHISPER",
  "OUTBOUND_WHISPER",
  "AGENT_TRANSFER",
  "QUEUE_TRANSFER",
  "CAMPAIGN"
] as const;

type ExportedFlowModule = {
  id?: string;
  arn?: string;
  name: string;
  description?: string;
  state?: string;
  status?: string;
  content?: string;
  settings?: string;
  tags?: Record<string, string>;
};

type ExportedContactFlow = {
  id?: string;
  arn?: string;
  name: string;
  type: string;
  description?: string;
  state?: string;
  status?: string;
  content?: string;
  tags?: Record<string, string>;
};

type ExportBundleV1 = {
  version: 1;
  exportedAt: string;
  source: { region: string; instanceId: string };
  flowModules: ExportedFlowModule[];
  contactFlows: ExportedContactFlow[];
};

function applyReplacements(content: string, replacements: Array<[string, string]>): string {
  let out = content;
  for (const [from, to] of replacements) {
    if (!from || from === to) continue;
    out = out.split(from).join(to);
  }
  return out;
}

async function listAllContactFlowModules(region: string, instanceId: string) {
  const c = clientFor(region);
  const out: Array<{ Id?: string; Arn?: string; Name?: string; State?: string }> = [];
  let nextToken: string | undefined = undefined;
  do {
    const page = await c.send(
      new ListContactFlowModulesCommand({
        InstanceId: instanceId,
        MaxResults: 100,
        NextToken: nextToken
      })
    );
    out.push(...(page.ContactFlowModulesSummaryList || []));
    nextToken = page.NextToken;
  } while (nextToken);
  return out;
}

async function listAllContactFlows(region: string, instanceId: string) {
  const c = clientFor(region);
  const out: Array<{ Id?: string; Arn?: string; Name?: string; ContactFlowType?: string }> = [];
  let nextToken: string | undefined = undefined;
  do {
    const page = await c.send(
      new ListContactFlowsCommand({
        InstanceId: instanceId,
        ContactFlowTypes: [...CONTACT_FLOW_TYPES],
        MaxResults: 100,
        NextToken: nextToken
      })
    );
    out.push(...(page.ContactFlowSummaryList || []));
    nextToken = page.NextToken;
  } while (nextToken);
  return out;
}

export const connectRouter = Router();

connectRouter.get("/regions", (_req, res) => {
  res.status(200).json({ regions: CONNECT_REGIONS });
});

connectRouter.get("/instances", async (req, res) => {
  const q = z.object({ region: z.string().min(1) }).safeParse(req.query);
  if (!q.success) return res.status(400).json({ error: "Missing or invalid region" });

  try {
    const c = clientFor(q.data.region);
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
  if (!q.success) return res.status(400).json({ error: "Missing region or instanceId" });

  try {
    const c = clientFor(q.data.region);
    const out = await c.send(new DescribeInstanceCommand({ InstanceId: q.data.instanceId }));
    return res.status(200).json({ instance: out.Instance });
  } catch (e: any) {
    return res.status(500).json({ error: e?.message || String(e) });
  }
});

connectRouter.post("/snapshot", async (req, res) => {
  const body = z.object({ region: z.string().min(1), instanceId: z.string().min(1) }).safeParse(req.body);
  if (!body.success) return res.status(400).json({ error: "Missing region or instanceId" });

  try {
    const c = clientFor(body.data.region);
    const out = await c.send(new DescribeInstanceCommand({ InstanceId: body.data.instanceId }));
    return res.status(200).json({
      capturedAt: new Date().toISOString(),
      region: body.data.region,
      instanceId: body.data.instanceId,
      instance: out.Instance
    });
  } catch (e: any) {
    return res.status(500).json({ error: e?.message || String(e) });
  }
});

connectRouter.post("/export", async (req, res) => {
  const body = z.object({ region: z.string().min(1), instanceId: z.string().min(1) }).safeParse(req.body);
  if (!body.success) return res.status(400).json({ error: "Missing region or instanceId" });

  const { region, instanceId } = body.data;

  try {
    const c = clientFor(region);

    const modules = await listAllContactFlowModules(region, instanceId);
    const flows = await listAllContactFlows(region, instanceId);

    const flowModules: ExportedFlowModule[] = [];
    for (const m of modules) {
      if (!m.Id || !m.Name) continue;
      const d = await c.send(
        new DescribeContactFlowModuleCommand({ InstanceId: instanceId, ContactFlowModuleId: m.Id })
      );
      const mod = d.ContactFlowModule;
      if (!mod?.Name) continue;
      flowModules.push({
        id: mod.Id,
        arn: mod.Arn,
        name: mod.Name,
        description: mod.Description,
        state: mod.State,
        status: mod.Status,
        content: mod.Content,
        settings: mod.Settings,
        tags: mod.Tags
      });
    }

    const contactFlows: ExportedContactFlow[] = [];
    for (const f of flows) {
      if (!f.Id || !f.Name || !f.ContactFlowType) continue;
      const d = await c.send(
        new DescribeContactFlowCommand({ InstanceId: instanceId, ContactFlowId: f.Id })
      );
      const flow = d.ContactFlow;
      if (!flow?.Name || !flow?.Type) continue;
      contactFlows.push({
        id: flow.Id,
        arn: flow.Arn,
        name: flow.Name,
        type: flow.Type,
        description: flow.Description,
        state: flow.State,
        status: flow.Status,
        content: flow.Content,
        tags: flow.Tags
      });
    }

    const bundle: ExportBundleV1 = {
      version: 1,
      exportedAt: new Date().toISOString(),
      source: { region, instanceId },
      flowModules,
      contactFlows
    };

    return res.status(200).json(bundle);
  } catch (e: any) {
    return res.status(500).json({ error: e?.message || String(e) });
  }
});

connectRouter.post("/import", async (req, res) => {
  const body = z
    .object({
      region: z.string().min(1),
      instanceId: z.string().min(1),
      overwrite: z.boolean().optional().default(false),
      bundle: z.any()
    })
    .safeParse(req.body);

  if (!body.success) return res.status(400).json({ error: "Missing required fields" });

  const { region, instanceId, overwrite } = body.data;

  const bundle = body.data.bundle as ExportBundleV1;
  if (bundle?.version !== 1 || !Array.isArray(bundle.contactFlows) || !Array.isArray(bundle.flowModules)) {
    return res.status(400).json({ error: "Invalid bundle format" });
  }

  try {
    const c = clientFor(region);

    // Build target lookup tables
    const existingModules = await listAllContactFlowModules(region, instanceId);
    const moduleByName = new Map<string, { Id?: string; Arn?: string; Name?: string }>();
    for (const m of existingModules) {
      if (m.Name) moduleByName.set(m.Name, m);
    }

    const moduleReplacements: Array<[string, string]> = [];

    let createdModules = 0;
    let updatedModules = 0;
    let skippedModules = 0;

    // 1) Upsert flow modules
    for (const m of bundle.flowModules) {
      if (!m.name) continue;
      const existing = moduleByName.get(m.name);
      if (existing?.Id) {
        if (!overwrite) {
          skippedModules++;
          continue;
        }
        if (typeof m.content === "string") {
          await c.send(
            new UpdateContactFlowModuleContentCommand({
              InstanceId: instanceId,
              ContactFlowModuleId: existing.Id,
              Content: m.content,
              Settings: m.settings
            })
          );
        }
        updatedModules++;
        if (m.id && existing.Id) moduleReplacements.push([m.id, existing.Id]);
        if (m.arn && existing.Arn) moduleReplacements.push([m.arn, existing.Arn]);
        continue;
      }

      const created = await c.send(
        new CreateContactFlowModuleCommand({
          InstanceId: instanceId,
          Name: m.name,
          Description: m.description,
          Content: m.content || "{}",
          Tags: m.tags,
          Settings: m.settings
        })
      );
      createdModules++;

      if (m.id && created.Id) moduleReplacements.push([m.id, created.Id]);
      if (m.arn && created.Arn) moduleReplacements.push([m.arn, created.Arn]);

      moduleByName.set(m.name, { Id: created.Id, Arn: created.Arn, Name: m.name });
    }

    // Flow replacements are only known after creating/updating flows.
    const flowReplacements: Array<[string, string]> = [];

    // Build target flow lookup tables
    const existingFlows = await listAllContactFlows(region, instanceId);
    const flowByNameType = new Map<string, { Id?: string; Arn?: string; Name?: string; ContactFlowType?: string }>();
    for (const f of existingFlows) {
      if (f.Name && f.ContactFlowType) flowByNameType.set(`${f.ContactFlowType}|${f.Name}`, f);
    }

    let createdFlows = 0;
    let updatedFlows = 0;
    let skippedFlows = 0;

    const importedFlowTargets: Array<{ source: ExportedContactFlow; targetId: string }> = [];

    // 2) Upsert flows (first pass: replace modules)
    for (const f of bundle.contactFlows) {
      if (!f.name || !f.type) continue;

      const key = `${f.type}|${f.name}`;
      const existing = flowByNameType.get(key);
      const content1 = typeof f.content === "string" ? applyReplacements(f.content, moduleReplacements) : "{}";

      if (existing?.Id) {
        if (!overwrite) {
          skippedFlows++;
          continue;
        }
        await c.send(
          new UpdateContactFlowContentCommand({
            InstanceId: instanceId,
            ContactFlowId: existing.Id,
            Content: content1
          })
        );
        updatedFlows++;

        if (f.id) flowReplacements.push([f.id, existing.Id]);
        if (f.arn && existing.Arn) flowReplacements.push([f.arn, existing.Arn]);

        importedFlowTargets.push({ source: f, targetId: existing.Id });
        continue;
      }

      const created = await c.send(
        new CreateContactFlowCommand({
          InstanceId: instanceId,
          Name: f.name,
          Type: f.type as any,
          Description: f.description,
          Content: content1,
          Tags: f.tags
        })
      );
      createdFlows++;

      if (f.id && created.ContactFlowId) flowReplacements.push([f.id, created.ContactFlowId]);
      if (f.arn && created.ContactFlowArn) flowReplacements.push([f.arn, created.ContactFlowArn]);

      if (created.ContactFlowId) {
        importedFlowTargets.push({ source: f, targetId: created.ContactFlowId });
      }

      flowByNameType.set(key, {
        Id: created.ContactFlowId,
        Arn: created.ContactFlowArn,
        Name: f.name,
        ContactFlowType: f.type
      });
    }

    // 3) Second pass: update imported flows to replace flow-to-flow references too
    for (const { source, targetId } of importedFlowTargets) {
      if (!overwrite && createdFlows === 0 && updatedFlows === 0) break;
      if (typeof source.content !== "string") continue;

      const content2 = applyReplacements(
        applyReplacements(source.content, moduleReplacements),
        flowReplacements
      );

      await c.send(
        new UpdateContactFlowContentCommand({
          InstanceId: instanceId,
          ContactFlowId: targetId,
          Content: content2
        })
      );
    }

    return res.status(200).json({
      createdModules,
      updatedModules,
      skippedModules,
      createdFlows,
      updatedFlows,
      skippedFlows
    });
  } catch (e: any) {
    return res.status(500).json({ error: e?.message || String(e) });
  }
});
