export type ConnectRegion = {
  code: string;
  label: string;
};

// Curated list (Connect isn't available in every AWS region).
export const CONNECT_REGIONS: ConnectRegion[] = [
  { code: "us-east-1", label: "US East (N. Virginia)" },
  { code: "us-east-2", label: "US East (Ohio)" },
  { code: "us-west-2", label: "US West (Oregon)" },
  { code: "ca-central-1", label: "Canada (Central)" },
  { code: "eu-west-2", label: "Europe (London)" },
  { code: "eu-central-1", label: "Europe (Frankfurt)" },
  { code: "ap-southeast-2", label: "Asia Pacific (Sydney)" },
  { code: "ap-northeast-1", label: "Asia Pacific (Tokyo)" },
  { code: "ap-northeast-2", label: "Asia Pacific (Seoul)" },
  { code: "ap-northeast-3", label: "Asia Pacific (Osaka)" }
];

