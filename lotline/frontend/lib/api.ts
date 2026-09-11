export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

export type AgentStep = {
  agent: string;
  iteration: number;
  status: string;
  summary: string;
  details: Record<string, unknown>;
};

export type PipelineResponse = {
  interpretation?: string;
  criteria?: Record<string, unknown>;
  headline: string;
  narrative: string;
  mode: string;
  iterations: number;
  trace: string[];
  agent_steps: AgentStep[];
  query_plan: Record<string, unknown>;
  trend: {
    months: Array<{
      month: string;
      median_price: number;
      median_price_per_sqft: number;
      active_count: number;
    }>;
    yoy_pct_change: number | null;
    total_listings: number;
    coverage_score: number;
    empty_months: string[];
  };
  monthly: Array<{
    month: string;
    median_price: number;
    median_price_per_sqft: number;
    active_count: number;
    mom_pct_change: number | null;
  }>;
  filtered_count: number;
  listings_preview: Array<Record<string, unknown>>;
  analytics: {
    kpis: {
      listings: number;
      median_price: number;
      median_ppsf: number;
      median_sqft: number;
      zips: number;
      localities: number;
    };
    by_zip: Array<{
      zip: string;
      locality: string;
      listings: number;
      median_price: number;
      median_ppsf: number;
      median_beds: number;
      median_sqft: number;
    }>;
    by_beds: Array<{ beds: number; listings: number; median_price: number }>;
    by_price_tier: Array<{ tier: string; listings: number; median_price: number }>;
    price_histogram: Array<{ bucket: string; lo: number; hi: number; count: number }>;
    locality_share: Array<{ locality: string; listings: number; share_pct: number }>;
  };
};

export type Snapshot = {
  total_listings: number;
  zip_count: number;
  month_span: number;
  median_price: number;
  monthly: Array<{ list_month: string; median_price: number; active_count: number }>;
  top_zips: PipelineResponse["analytics"]["by_zip"];
  beds: PipelineResponse["analytics"]["by_beds"];
  price_tiers?: PipelineResponse["analytics"]["by_price_tier"];
  price_hist: PipelineResponse["analytics"]["price_histogram"];
  localities: PipelineResponse["analytics"]["locality_share"];
};

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/api/health`);
  if (!res.ok) throw new Error("Backend offline");
  return res.json();
}

export async function fetchSnapshot(): Promise<Snapshot> {
  const res = await fetch(`${API_BASE}/api/snapshot`);
  if (!res.ok) throw new Error("Snapshot failed");
  return res.json();
}

export async function chatAsk(
  message: string,
  mode: string,
  maxIterations = 3
): Promise<PipelineResponse> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, mode, max_iterations: maxIterations }),
  });
  if (!res.ok) throw new Error(`Chat failed: ${res.status}`);
  return res.json();
}

export function money(n: number) {
  return n >= 1000 ? `$${(n / 1000).toFixed(0)}k` : `$${n.toFixed(0)}`;
}

export type MrSeries = {
  months: string[];
  median_price: number[];
  median_ppsf: number[];
  active_count: number[];
  yoy_pct_change: number | null;
  total_listings: number;
  coverage_score: number;
};

export type MrAgentPipeline = {
  mode: string;
  iterations: number;
  trace: string[];
  agent_steps: AgentStep[];
  headline?: string;
};

export type MrCase = {
  case: number;
  passed: boolean;
  detail: string;
  criteria?: {
    price_min: number;
    price_max: number;
    zips: string[];
    window_end: string;
    beds_min?: number;
    beds_max?: number;
  };
  metrics?: {
    transform?: string;
    expect?: string;
    checks?: Record<string, boolean>;
    source?: MrSeries;
    followup?: MrSeries;
    agents?: string[];
    agent_rationale?: string;
    agent_pipeline?: MrAgentPipeline;
    [key: string]: unknown;
  };
};

export type MrCatalogEntry = {
  id: string;
  family: string;
  title: string;
  transform: string;
  metrics: string[];
  expect: string;
  agents?: string[];
  agent_rationale?: string;
};

export type MrResultRow = {
  mr_id: string;
  n: number;
  violations: number;
  violation_rate: number;
  ci95: [number, number];
  seed?: number;
  agents?: string[];
  agent_rationale?: string;
  sample_failures?: string[];
  cases?: MrCase[];
};

export type MrRunResponse = {
  available: boolean;
  seed?: number;
  n_base_inputs?: number;
  selected_mrs?: string[];
  smoke?: { mr_id: string; passed: boolean; detail: string } | null;
  results: MrResultRow[];
  saved_to?: string;
  message?: string;
};

export type MrListResponse = {
  mrs: string[];
  catalog: MrCatalogEntry[];
  metrics_glossary: Record<string, string>;
  data: { panel: string; rows: number; zips: number; note: string };
};

export async function fetchMrList(): Promise<MrListResponse> {
  const res = await fetch(`${API_BASE}/api/mrs/list`);
  if (!res.ok) throw new Error("MR list failed");
  return res.json();
}

export async function fetchMrSummary(): Promise<MrRunResponse> {
  const res = await fetch(`${API_BASE}/api/mrs/summary`);
  if (!res.ok) throw new Error("MR summary failed");
  return res.json();
}

export async function runMrs(body: {
  n: number;
  seed: number;
  mrs?: string[] | null;
  verbose?: boolean;
  agent_trace_cases?: number;
}): Promise<MrRunResponse> {
  const res = await fetch(`${API_BASE}/api/mrs/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      n: body.n,
      seed: body.seed,
      mrs: body.mrs ?? null,
      verbose: body.verbose ?? true,
      no_smoke: false,
      agent_trace_cases: body.agent_trace_cases ?? Math.min(3, body.n),
    }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`MR run failed: ${res.status} ${detail}`);
  }
  return res.json();
}
