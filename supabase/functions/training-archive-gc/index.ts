import { createClient } from "jsr:@supabase/supabase-js@2.116.0";
import { createRemoteJWKSet, jwtVerify } from "npm:jose@6.2.12";

const BUCKET = "tenis-ai-training-archive-private";
const AUDIENCE = "tenis-ai-training-archive-gc";
const CONTRACT_REVISION = "sha256:35602d6b005e10d2fc56d566efc06c56b5fffed128a478ab9e4ffa80ca0ab331";
const REPOSITORY = "Abeel87/tenis-ai";
const REPOSITORY_ID = "1339352577";
const REPOSITORY_OWNER_ID = "198365428";
const REF = "refs/heads/main";
const WORKFLOW = ".github/workflows/training-archive-gc.yml";
const EXPECTED_WORKFLOW_REF = `${REPOSITORY}/${WORKFLOW}@${REF}`;
const ISSUER = "https://token.actions.githubusercontent.com";
const JWKS = createRemoteJWKSet(new URL(`${ISSUER}/.well-known/jwks`));
const ALLOWED_EVENTS = new Set(["schedule", "workflow_dispatch"]);
const KEEP_LATEST = 2;
const GRACE_HOURS = 168;
const BATCH_LIMIT = 100;
const MAX_ERROR_MESSAGE = 400;

type SafeError = { code: string | null; message: string };
type Claims = { runId: number; runAttempt: number; sha: string };
type ApplyObject = {
  sha256: string;
  storage_path: string;
  size_bytes: number;
  deleted_at: string | null;
  skipped_at: string | null;
};

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}

function safeError(err: unknown): SafeError {
  const value = err as { code?: unknown; message?: unknown } | null | undefined;
  const code = typeof value?.code === "string" ? value.code.slice(0, 80) : null;
  const raw = typeof value?.message === "string" ? value.message : String(err);
  return { code, message: raw.slice(0, MAX_ERROR_MESSAGE) };
}

function serviceKey(): string {
  const modern = Deno.env.get("SUPABASE_SECRET_KEYS");
  if (modern) {
    try {
      const parsed = JSON.parse(modern);
      if (typeof parsed?.default === "string" && parsed.default) return parsed.default;
    } catch {}
  }
  const legacy = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!legacy) throw new Error("Supabase secret key is unavailable");
  return legacy;
}

async function authorize(req: Request): Promise<Claims> {
  const header = req.headers.get("authorization") || "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : "";
  if (!token) throw new Error("Missing GitHub OIDC bearer token");
  const { payload } = await jwtVerify(token, JWKS, { issuer: ISSUER, audience: AUDIENCE });
  if (payload.repository !== REPOSITORY) throw new Error("OIDC repository mismatch");
  if (String(payload.repository_id || "") !== REPOSITORY_ID) throw new Error("OIDC repository_id mismatch");
  if (String(payload.repository_owner_id || "") !== REPOSITORY_OWNER_ID) throw new Error("OIDC owner_id mismatch");
  if (payload.ref !== REF) throw new Error("OIDC ref mismatch");
  if (payload.workflow_ref !== EXPECTED_WORKFLOW_REF) throw new Error("OIDC workflow mismatch");
  if (!ALLOWED_EVENTS.has(String(payload.event_name || ""))) throw new Error("OIDC event is not allowed");
  const runId = Number(payload.run_id || 0);
  const runAttempt = Number(payload.run_attempt || 0);
  const sha = String(payload.sha || "");
  if (!Number.isSafeInteger(runId) || runId <= 0) throw new Error("OIDC run_id mismatch");
  if (!Number.isSafeInteger(runAttempt) || runAttempt <= 0) throw new Error("OIDC run_attempt mismatch");
  if (!/^[0-9a-f]{40}$/.test(sha)) throw new Error("OIDC sha mismatch");
  return { runId, runAttempt, sha };
}

async function rpcOne(supabase: any, name: string, args: Record<string, unknown>) {
  const { data, error } = await supabase.rpc(name, args);
  if (error) throw error;
  if (Array.isArray(data)) return data[0] || null;
  return data;
}

async function preview(supabase: any) {
  const row = await rpcOne(supabase, "training_archive_retention_observe", {
    p_keep_latest: KEEP_LATEST,
    p_grace_hours: GRACE_HOURS,
  });
  return {
    ok: true,
    contract_revision: CONTRACT_REVISION,
    action: "preview",
    policy: { keep_latest: KEEP_LATEST, grace_hours: GRACE_HOURS },
    observation: row,
  };
}

async function apply(supabase: any, claims: Claims) {
  const prepared = await rpcOne(supabase, "training_archive_gc_prepare", {
    p_archive_run_id: claims.runId,
    p_archive_run_attempt: claims.runAttempt,
    p_source_sha: claims.sha,
    p_keep_latest: KEEP_LATEST,
    p_grace_hours: GRACE_HOURS,
    p_batch_limit: BATCH_LIMIT,
  });
  if (!prepared || !Number.isFinite(Number(prepared.apply_id))) {
    throw new Error("training archive GC prepare returned no apply_id");
  }

  const applyId = Number(prepared.apply_id);
  const { data: objects, error: objectsError } = await supabase
    .from("training_archive_gc_apply_objects")
    .select("sha256,storage_path,size_bytes,deleted_at,skipped_at")
    .eq("apply_id", applyId)
    .order("sha256", { ascending: true });
  if (objectsError) throw objectsError;

  for (const item of (objects || []) as ApplyObject[]) {
    if (item.deleted_at || item.skipped_at) continue;
    const claimed = await rpcOne(supabase, "training_archive_gc_claim_object", {
      p_apply_id: applyId,
      p_sha256: item.sha256,
    });
    const state = String(claimed?.state || "unknown");

    if (state === "terminal") continue;
    if (state === "referenced" || state === "not_ready") {
      const skipped = await rpcOne(supabase, "training_archive_gc_skip_object", {
        p_apply_id: applyId,
        p_sha256: item.sha256,
        p_reason: state,
      });
      if (skipped !== true) throw new Error(`failed to skip ${item.sha256} after ${state}`);
      continue;
    }
    if (state === "resume_finalize") {
      const finalized = await rpcOne(supabase, "training_archive_gc_finalize_object", {
        p_apply_id: applyId,
        p_sha256: item.sha256,
      });
      if (finalized !== true) throw new Error(`failed to resume finalize for ${item.sha256}`);
      continue;
    }
    if (state !== "delete") {
      throw new Error(`unsafe training archive GC object state ${state} for ${item.sha256}`);
    }

    const path = String(claimed.storage_path || "");
    if (!path || path !== item.storage_path) throw new Error(`storage path mismatch for ${item.sha256}`);
    const { error: removeError } = await supabase.storage.from(BUCKET).remove([path]);
    if (removeError) throw removeError;

    const finalized = await rpcOne(supabase, "training_archive_gc_finalize_object", {
      p_apply_id: applyId,
      p_sha256: item.sha256,
    });
    if (finalized !== true) throw new Error(`failed to finalize ${item.sha256}`);
  }

  const finalStatus = await rpcOne(supabase, "training_archive_gc_finish_apply", {
    p_apply_id: applyId,
  });
  const { data: audit, error: auditError } = await supabase
    .from("training_archive_gc_apply_audit")
    .select("apply_id,status,expired_manifests,planned_objects,planned_bytes,deleted_objects,deleted_bytes,skipped_objects")
    .eq("apply_id", applyId)
    .single();
  if (auditError) throw auditError;

  return {
    ok: finalStatus === "complete" || finalStatus === "noop",
    contract_revision: CONTRACT_REVISION,
    action: "apply",
    policy: { keep_latest: KEEP_LATEST, grace_hours: GRACE_HOURS, batch_limit: BATCH_LIMIT },
    audit,
  };
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return response({ error: "POST required" }, 405);
  let claims: Claims;
  try {
    claims = await authorize(req);
  } catch {
    return response({ error: "unauthorized" }, 401);
  }
  try {
    const supabase = createClient(Deno.env.get("SUPABASE_URL")!, serviceKey(), {
      auth: { persistSession: false, autoRefreshToken: false },
    });
    const body = await req.json().catch(() => ({}));
    if (body.action === "preview") return response(await preview(supabase));
    if (body.action === "apply") return response(await apply(supabase, claims));
    return response({ error: "Unknown action" }, 400);
  } catch (err) {
    const detail = safeError(err);
    console.error("training-archive-gc", detail);
    return response({ error: "training archive GC failed", detail }, 500);
  }
});
