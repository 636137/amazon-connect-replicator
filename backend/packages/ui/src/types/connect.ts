export type ConnectRegion = { code: string; label: string };

export type InstanceSummary = {
  Id?: string;
  Arn?: string;
  IdentityManagementType?: string;
  InstanceAlias?: string;
  InstanceStatus?: string;
  InboundCallsEnabled?: boolean;
  OutboundCallsEnabled?: boolean;
};

export type DescribeInstance = InstanceSummary & {
  CreatedTime?: string;
  ServiceRole?: string;
};

export type ExportedFlowModule = {
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

export type ExportedContactFlow = {
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

export type ExportedHoursOfOperation = {
  id?: string;
  arn?: string;
  name: string;
  description?: string;
  timeZone?: string;
  config?: any;
  tags?: Record<string, string>;
};

export type ExportedQueue = {
  id?: string;
  arn?: string;
  name: string;
  description?: string;
  status?: string;
  maxContacts?: number;
  hoursOfOperationId?: string;
  hoursOfOperationName?: string;
  outboundCallerConfig?: any;
  tags?: Record<string, string>;
};

export type ExportedLambdaFunction = {
  arn: string;
  region?: string;
  accountId?: string;
  functionName?: string;
};

export type ExportedLexBot = {
  aliasArn?: string;
  name?: string;
  lexVersion: "V1" | "V2";
  region?: string;
  accountId?: string;
  botAliasId?: string;
  botName?: string;
  lexRegion?: string;
};

// Resource type keys for v3.1 bundle (19 resource types)
export type ResourceType =
  | "hoursOfOperations"
  | "agentStatuses"
  | "securityProfiles"
  | "userHierarchyGroups"
  | "queues"
  | "routingProfiles"
  | "quickConnects"
  | "flowModules"
  | "contactFlows"
  | "instanceAttributes"
  | "predefinedAttributes"
  | "prompts"
  | "taskTemplates"
  | "views"
  | "rules"
  | "evaluationForms"
  | "vocabularies"
  | "lambdaFunctions"
  | "lexBots";

export const RESOURCE_TYPES: { key: ResourceType; label: string; description: string }[] = [
  { key: "hoursOfOperations", label: "Hours of Operation", description: "Business hours schedules" },
  { key: "agentStatuses", label: "Agent Statuses", description: "Available, Break, Lunch, etc." },
  { key: "securityProfiles", label: "Security Profiles", description: "Permission sets for users" },
  { key: "userHierarchyGroups", label: "Hierarchy Groups", description: "Organizational structure" },
  { key: "queues", label: "Queues", description: "Contact queues (STANDARD)" },
  { key: "routingProfiles", label: "Routing Profiles", description: "Agent routing configurations" },
  { key: "quickConnects", label: "Quick Connects", description: "Transfer destinations" },
  { key: "flowModules", label: "Flow Modules", description: "Reusable flow components" },
  { key: "contactFlows", label: "Contact Flows", description: "IVR and routing logic" },
  { key: "instanceAttributes", label: "Instance Attributes", description: "Feature flags" },
  { key: "predefinedAttributes", label: "Predefined Attributes", description: "Routing skill tags" },
  { key: "prompts", label: "Prompts", description: "Audio files (requires S3)" },
  { key: "taskTemplates", label: "Task Templates", description: "Structured task definitions" },
  { key: "views", label: "Views", description: "Step-by-step guides" },
  { key: "rules", label: "Rules", description: "Contact Lens rules" },
  { key: "evaluationForms", label: "Evaluation Forms", description: "QA scoring forms" },
  { key: "vocabularies", label: "Vocabularies", description: "Custom vocabularies" },
  { key: "lambdaFunctions", label: "Lambda Functions", description: "AWS Lambda integrations (ARNs auto-replaced)" },
  { key: "lexBots", label: "Lex Bots", description: "Amazon Lex V1/V2 bots (ARNs auto-replaced)" },
];

export type ExportBundleV1 = {
  version: 1 | 2 | 3;
  exportedAt: string;
  source: { region: string; instanceId: string };
  hoursOfOperations?: any[];
  agentStatuses?: any[];
  securityProfiles?: any[];
  userHierarchyGroups?: any[];
  queues?: any[];
  routingProfiles?: any[];
  quickConnects?: any[];
  flowModules?: any[];
  contactFlows?: any[];
  instanceAttributes?: any[];
  predefinedAttributes?: any[];
  prompts?: any[];
  taskTemplates?: any[];
  views?: any[];
  rules?: any[];
  evaluationForms?: any[];
  vocabularies?: any[];
  lambdaFunctions?: ExportedLambdaFunction[];
  lexBots?: ExportedLexBot[];
};
