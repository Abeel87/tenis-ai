import { createClient } from "jsr:@supabase/supabase-js@2.116.0";
import { createRemoteJWKSet, jwtVerify } from "npm:jose@6.2.12";
import nodemailer from "npm:nodemailer@^9";

const EXPECTED_AUDIENCE = "tenis-ai-ineed";
const EXPECTED_REPOSITORY = "Abeel87/tenis-ai";
const EXPECTED_REF = "refs/heads/main";
const EXPECTED_WORKFLOW_REF = `${EXPECTED_REPOSITORY}/.github/workflows/ineed-shadow.yml@${EXPECTED_REF}`;
const TENIS_AI_SITE = "https://abeel87.github.io/tenis-ai/";
const ISSUER = "https://token.actions.githubusercontent.com";
const JWKS = createRemoteJWKSet(new URL("https://token.actions.githubusercontent.com/.well-known/jwks"));

type Json = Record<string, any>;

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}

function serviceKey(): string {
  const modern = Deno.env.get("SUPABASE_SECRET_KEYS");
  if (modern) {
    try {
      const parsed = JSON.parse(modern);
      if (typeof parsed?.default === "string" && parsed.default) return parsed.default;
    } catch { /* legacy fallback */ }
  }
  const legacy = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!legacy) throw new Error("Supabase secret key is unavailable");
  return legacy;
}

async function authorize(req: Request) {
  const header = req.headers.get("authorization") || "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : "";
  if (!token) throw new Error("Missing GitHub OIDC bearer token");
  const { payload } = await jwtVerify(token, JWKS, { issuer: ISSUER, audience: EXPECTED_AUDIENCE });
  if (payload.repository !== EXPECTED_REPOSITORY) throw new Error("OIDC repository mismatch");
  if (payload.ref !== EXPECTED_REF) throw new Error("OIDC ref mismatch");
  if (payload.workflow_ref !== EXPECTED_WORKFLOW_REF) throw new Error("OIDC workflow mismatch");
  if (!["workflow_run", "schedule", "workflow_dispatch"].includes(String(payload.event_name || ""))) throw new Error("OIDC event is not allowed");
}

function stableJson(value: any): string {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
  if (value && typeof value === "object") return `{${Object.keys(value).sort().map(k => `${JSON.stringify(k)}:${stableJson(value[k])}`).join(",")}}`;
  return JSON.stringify(value);
}

async function digestSnapshot(snapshot: Json): Promise<string> {
  const canonical = { ...snapshot };
  delete canonical.timestamp;
  const bytes = new TextEncoder().encode(stableJson(canonical));
  const hash = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(hash)).map(b => b.toString(16).padStart(2, "0")).join("");
}

async function activeState(supabase: any) {
  const { data: experiment, error } = await supabase.from("ineed_experiments").select("*").eq("status", "ACTIVE").maybeSingle();
  if (error) throw error;
  if (!experiment) throw new Error("No active iNeed$ experiment");
  const [{ data: ledger, error: ledgerError }, { data: openBets, error: betsError }, { data: settled, error: settledError }] = await Promise.all([
    supabase.from("ineed_bankroll_ledger").select("bankroll_after,created_at,id").eq("experiment_id", experiment.id).order("created_at", { ascending: false }).order("id", { ascending: false }).limit(1),
    supabase.from("ineed_shadow_bets").select("*").eq("experiment_id", experiment.id).in("status", ["SHADOW_PLACED", "PENDING"]),
    supabase.from("ineed_shadow_bets").select("bankroll_after").eq("experiment_id", experiment.id).not("bankroll_after", "is", null),
  ]);
  if (ledgerError) throw ledgerError;
  if (betsError) throw betsError;
  if (settledError) throw settledError;
  const available = Number(ledger?.[0]?.bankroll_after ?? 0);
  const exposure = (openBets || []).reduce((sum: number, row: Json) => sum + Number(row.stake || 0), 0);
  const peak = Math.max(Number(experiment.starting_bankroll || 0), available + exposure, ...(settled || []).map((x: Json) => Number(x.bankroll_after || 0)));
  return { experiment, available_capital: available, active_exposure: exposure, bankroll_equity: available + exposure, peak_bankroll: peak, open_bets: openBets || [] };
}

async function upsertEvaluation(supabase: any, experiment: Json, evaluation: Json) {
  const { data: current, error: currentError } = await supabase.from("ineed_signals").select("*").eq("experiment_id", experiment.id).eq("fingerprint", evaluation.fingerprint).maybeSingle();
  if (currentError) throw currentError;
  const protectedStatus = current && ["SHADOW_PLACED", "PENDING", "WIN", "LOSS", "VOID", "CANCELLED", "SETTLED"].includes(current.status);
  const row = {
    experiment_id: experiment.id,
    fingerprint: evaluation.fingerprint,
    status: protectedStatus ? current.status : evaluation.status,
    reason_code: protectedStatus ? current.reason_code : (evaluation.reason_code ?? null),
    match_id: protectedStatus ? current.match_id : String(evaluation.match_id),
    market: protectedStatus ? current.market : String(evaluation.market || "unknown"),
    selection: protectedStatus ? current.selection : (evaluation.selection == null ? null : String(evaluation.selection)),
    odds: protectedStatus ? current.odds : (evaluation.odds ?? null),
    odds_timestamp: protectedStatus ? current.odds_timestamp : (evaluation.odds_timestamp ?? null),
    model_probability: protectedStatus ? current.model_probability : (evaluation.model_probability ?? null),
    raw_implied_probability: protectedStatus ? current.raw_implied_probability : (evaluation.raw_implied_probability ?? null),
    no_vig_probability: protectedStatus ? current.no_vig_probability : (evaluation.no_vig_probability ?? null),
    break_even_probability: protectedStatus ? current.break_even_probability : (evaluation.break_even_probability ?? null),
    fair_odds: protectedStatus ? current.fair_odds : (evaluation.fair_odds ?? null),
    edge_probability_points: protectedStatus ? current.edge_probability_points : (evaluation.edge_probability_points ?? null),
    expected_value_net: protectedStatus ? current.expected_value_net : (evaluation.expected_value_net ?? null),
    estimated_bookmaker_margin: protectedStatus ? current.estimated_bookmaker_margin : (evaluation.estimated_bookmaker_margin ?? null),
    confidence: protectedStatus ? current.confidence : (evaluation.confidence ?? null),
    data_quality: protectedStatus ? current.data_quality : (evaluation.data_quality ?? null),
    proposed_stake: protectedStatus ? current.proposed_stake : (evaluation.proposed_stake ?? null),
    final_stake: protectedStatus ? current.final_stake : (evaluation.final_stake ?? null),
    current_snapshot: protectedStatus ? current.current_snapshot : (evaluation.snapshot || {}),
    updated_at: new Date().toISOString(),
  };
  const { data: saved, error: saveError } = await supabase.from("ineed_signals").upsert(row, { onConflict: "experiment_id,fingerprint" }).select("*").single();
  if (saveError) throw saveError;

  const snapshot = evaluation.snapshot || {};
  const snapshotHash = await digestSnapshot(snapshot);
  const { error: snapshotError } = await supabase.from("ineed_decision_snapshots").upsert({
    experiment_id: experiment.id,
    signal_id: saved.id,
    snapshot_hash: snapshotHash,
    evaluated_at: snapshot.timestamp || new Date().toISOString(),
    odds: evaluation.odds ?? null,
    odds_timestamp: evaluation.odds_timestamp ?? null,
    status: evaluation.status,
    reason_code: evaluation.reason_code ?? null,
    snapshot,
  }, { onConflict: "signal_id,snapshot_hash", ignoreDuplicates: true });
  if (snapshotError) throw snapshotError;

  let placed = null;
  const newlyQualified = evaluation.status === "QUALIFIED" && !protectedStatus && current?.status !== "QUALIFIED";
  if (evaluation.status === "QUALIFIED" && !protectedStatus) {
    const { data, error } = await supabase.rpc("ineed_system_place_bet", { target_signal_id: saved.id });
    if (error) throw error;
    placed = data;
  }
  if (newlyQualified) {
    const emailPayload = {
      kind: "QUALIFIED", signal_id: saved.id,
      match: `${snapshot.p1 || ""} — ${snapshot.p2 || ""}`.trim(),
      market: snapshot.market, selection: snapshot.selection, odds: snapshot.raw_odds,
      stake: snapshot.final_stake, bankroll: snapshot.bankroll_before, net_ev: snapshot.expected_value_net,
      confidence: snapshot.confidence, risk: snapshot.risk_state, match_id: snapshot.match_id,
    };
    const { error: emailInsertError } = await supabase.from("ineed_email_events").upsert({
      experiment_id: experiment.id, signal_id: saved.id, event_type: "QUALIFIED", revision: 1, status: "PENDING", payload: emailPayload,
    }, { onConflict: "signal_id,event_type,revision", ignoreDuplicates: true });
    if (emailInsertError) throw emailInsertError;
  }
  return { signal_id: saved.id, status: saved.status, placed };
}

async function settle(supabase: any, settlement: Json) {
  const { data, error } = await supabase.rpc("ineed_system_settle_bet", {
    target_bet_id: settlement.bet_id,
    settlement_outcome: settlement.outcome,
    settlement_payout: settlement.payout,
    settlement_detail: settlement.settlement_snapshot || {},
  });
  if (error) throw error;
  return data;
}

async function staffEmails(supabase: any): Promise<string[]> {
  const recipients = new Set<string>();
  const configured = (Deno.env.get("INEED_ALERT_EMAIL") || "").split(/[;,]/).map(v => v.trim().toLowerCase()).filter(Boolean);
  for (const email of configured) recipients.add(email);
  const { data: profiles, error } = await supabase.from("profiles").select("id,role").in("role", ["admin", "moderator"]).is("banned_at", null);
  if (error) throw error;
  const users = await Promise.all((profiles || []).map(async (profile: Json) => {
    const { data, error: userError } = await supabase.auth.admin.getUserById(profile.id);
    if (userError) return null;
    return data?.user?.email?.trim().toLowerCase() || null;
  }));
  for (const email of users) if (email) recipients.add(email);
  return [...recipients];
}

async function flushEmails(supabase: any) {
  const { data: rows, error } = await supabase.from("ineed_email_events").select("*").in("status", ["PENDING", "PENDING_CONFIG", "FAILED"]).order("created_at", { ascending: true }).limit(20);
  if (error) throw error;
  if (!rows?.length) return { sent: 0, pending: 0, provider: "gmail-smtp", recipient_count: 0 };
  const gmailUser = Deno.env.get("INEED_GMAIL_USER")?.trim();
  const gmailAppPassword = Deno.env.get("INEED_GMAIL_APP_PASSWORD")?.replace(/\s+/g, "");
  const recipients = await staffEmails(supabase);
  if (!gmailUser || !gmailAppPassword || !recipients.length) {
    for (const row of rows) {
      await supabase.from("ineed_email_events").update({ status: "PENDING_CONFIG", last_error: "Missing Gmail SMTP config or staff recipients", attempt_count: Number(row.attempt_count || 0) + 1 }).eq("id", row.id);
    }
    return { sent: 0, pending: rows.length, configuration_required: true, provider: "gmail-smtp", recipient_count: recipients.length };
  }
  const transport = nodemailer.createTransport({
    host: "smtp.gmail.com", port: 465, secure: true,
    auth: { user: gmailUser, pass: gmailAppPassword },
    connectionTimeout: 15000, greetingTimeout: 15000, socketTimeout: 30000,
  });
  let sent = 0;
  for (const row of rows) {
    const p = row.payload || {};
    const appUrl = p.match_id ? `${TENIS_AI_SITE}#match/${encodeURIComponent(String(p.match_id))}/summary` : TENIS_AI_SITE;
    const netEv = p.net_ev == null ? "—" : `${(Number(p.net_ev) * 100).toFixed(1)}%`;
    const text = ["iNeed$ znalazł value", p.match || "Mecz", `Typ: ${p.selection || p.market || "—"}`, `Superbet: ${p.odds ?? "—"}`, `Proponowana stawka: ${p.stake ?? "—"} PLN`, `Bankroll: ${p.bankroll ?? "—"} PLN`, `NET EV: ${netEv}`, `Confidence: ${p.confidence ?? "—"}`, `Risk: ${p.risk || "—"}`, `Tenis AI: ${appUrl}`].join("\n");
    const html = `<h2>💰 iNeed$ znalazł value</h2><p><b>${p.match || "Mecz"}</b></p><p>Typ: ${p.selection || p.market || "—"}<br>Superbet: ${p.odds ?? "—"}<br>Proponowana stawka: ${p.stake ?? "—"} PLN<br>Bankroll: ${p.bankroll ?? "—"} PLN<br>NET EV: ${netEv}<br>Confidence: ${p.confidence ?? "—"}<br>Risk: ${p.risk || "—"}</p><p><a href="${appUrl}">OTWÓRZ MECZ W TENIS AI</a></p>`;
    try {
      const info = await transport.sendMail({ from: `"Tenis AI iNeed$" <${gmailUser}>`, to: recipients, subject: "💰 iNeed$ znalazł value", text, html });
      await supabase.from("ineed_email_events").update({ status: "SENT", provider_message_id: info?.messageId || null, sent_at: new Date().toISOString(), attempt_count: Number(row.attempt_count || 0) + 1, last_error: null }).eq("id", row.id);
      sent++;
    } catch (err) {
      await supabase.from("ineed_email_events").update({ status: "FAILED", last_error: String(err), attempt_count: Number(row.attempt_count || 0) + 1 }).eq("id", row.id);
    }
  }
  return { sent, pending: rows.length - sent, provider: "gmail-smtp", recipient_count: recipients.length };
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return response({ error: "POST required" }, 405);
  try { await authorize(req); } catch (err) { return response({ error: "unauthorized", detail: String(err) }, 401); }
  try {
    const supabase = createClient(Deno.env.get("SUPABASE_URL")!, serviceKey(), { auth: { persistSession: false, autoRefreshToken: false } });
    const body = await req.json().catch(() => ({}));
    if (body.action === "state") return response(await activeState(supabase));
    if (body.action !== "sync") return response({ error: "Unknown action" }, 400);
    const state = await activeState(supabase);
    const payload = body.payload || {};
    if (String(payload.experiment_id || "") !== String(state.experiment.id)) return response({ error: "Experiment mismatch" }, 409);
    if (payload.operator !== "superbet.pl" || payload.mode !== "SHADOW") return response({ error: "Invalid V1 operator/mode" }, 400);
    if (payload.health?.automatic_real_betting !== false) return response({ error: "Real betting must remain disabled" }, 400);
    const settlementResults = [];
    for (const item of payload.settlements || []) settlementResults.push(await settle(supabase, item));
    const evaluationResults = [];
    for (const item of payload.evaluations || []) evaluationResults.push(await upsertEvaluation(supabase, state.experiment, item));
    const email = await flushEmails(supabase);
    const { error: healthError } = await supabase.from("ineed_runtime_health").upsert({
      experiment_id: state.experiment.id, status: "OK", last_sync_at: payload.generated_at || new Date().toISOString(),
      detail: { ...(payload.health || {}), settlement_results: settlementResults.length, evaluation_results: evaluationResults.length, email }, updated_at: new Date().toISOString(),
    });
    if (healthError) throw healthError;
    return response({ ok: true, settlements: settlementResults, evaluations: evaluationResults, email, state: await activeState(supabase) });
  } catch (err) {
    return response({ error: "iNeed sync failed", detail: String(err) }, 500);
  }
});
