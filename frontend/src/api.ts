import {
  MatchedTick,
  OhlcvCandle,
  OptionChainResponse,
  OptionContract,
  QualityReport,
  UnderlyingAsset,
} from "./types";

const API_BASE =
  (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_API_BASE_URL ||
  "http://localhost:8000/api";

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    throw new Error(`API error ${res.status} on ${path}`);
  }
  return res.json() as Promise<T>;
}

export async function fetchUnderlyings(): Promise<UnderlyingAsset[]> {
  const data = await fetchJson<{ count: number; underlyings: UnderlyingAsset[] }>("/underlyings");
  return data.underlyings;
}

export async function fetchOptions(params?: {
  ua_ins_code?: string;
  option_type?: string;
  include_expired?: boolean;
  q?: string;
}): Promise<OptionContract[]> {
  const qs = new URLSearchParams();
  if (params?.ua_ins_code) qs.set("ua_ins_code", params.ua_ins_code);
  if (params?.option_type) qs.set("option_type", params.option_type);
  if (params?.include_expired !== undefined)
    qs.set("include_expired", String(params.include_expired));
  if (params?.q) qs.set("q", params.q);
  const query = qs.toString() ? `?${qs.toString()}` : "";
  const data = await fetchJson<{ count: number; options: OptionContract[] }>(`/options${query}`);
  return data.options;
}

export async function fetchOptionChain(
  uaInsCode: string,
  dEven?: number,
  includeExpired = true
): Promise<OptionChainResponse> {
  const qs = new URLSearchParams({
    ua_ins_code: uaInsCode,
    include_expired: String(includeExpired),
  });
  if (dEven) qs.set("d_even", String(dEven));
  return fetchJson<OptionChainResponse>(`/option-chain?${qs.toString()}`);
}

export async function fetchCandles(
  insCode: string,
  timeframe: "1m" | "5m" | "15m" | "1h" | "1d" = "1m",
  dEven?: number
): Promise<OhlcvCandle[]> {
  const qs = new URLSearchParams({
    ins_code: insCode,
    timeframe,
  });
  if (dEven) qs.set("d_even", String(dEven));
  const data = await fetchJson<{ count: number; candles: OhlcvCandle[] }>(`/candles?${qs.toString()}`);
  return data.candles;
}

export async function fetchTicks(
  insCode: string,
  dEven?: number,
  limit = 500
): Promise<MatchedTick[]> {
  const qs = new URLSearchParams({
    ins_code: insCode,
    limit: String(limit),
  });
  if (dEven) qs.set("d_even", String(dEven));
  const data = await fetchJson<{ count: number; ticks: MatchedTick[] }>(`/ticks?${qs.toString()}`);
  return data.ticks;
}

export async function fetchQualityReport(): Promise<QualityReport> {
  return fetchJson<QualityReport>("/quality-report");
}
