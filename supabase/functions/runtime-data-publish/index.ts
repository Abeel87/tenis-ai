import { createClient } from "jsr:@supabase/supabase-js@2.116.0";
import { createRemoteJWKSet, jwtVerify } from "npm:jose@6.2.12";

const BUCKET = "tenis-ai-runtime-private";
const AUDIENCE = "tenis-ai-runtime-publisher";
const REPOSITORY = "Abeel87/tenis-ai";
const REPOSITORY_ID = "1339352577";
const REPOSITORY_OWNER_ID = "198365428";
const REF = "refs/heads/main";
const WORKFLOW = ".github/workflows/runtime-private-delivery.yml";
const EXPECTED_WORKFLOW_REF = `${REPOSITORY}/${WORKFLOW}@${REF}`;
const ISSUER = "https://token.actions.githubusercontent.com";
const JWKS = createRemoteJWKSet(new URL(`${ISSUER}/.well-known/jwks`));
const ALLOWED_EVENTS = new Set(["workflow_run", "workflow_dispatch"]);

type Layer = "core" | "market" | "dna" | "neuron";
type AccessTier = "b" | "c";
type RuntimeFile = {
  path: string;
  tier: AccessTier;
  sha256: string;
  size_bytes: number;
};

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function serviceKey(): string {
  const modern = Deno.env.get("SUPABASE_SECRET_KEYS");
  if (modern) {
    try {
      const parsed = JSON.parse(modern);
      if (typeof parsed?.default === "string" && parsed.default) return parsed.default;
    } catch {
      // Legacy fallback below.
    }
  }
  const legacy = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!legacy) throw new Error("Supabase secret key is unavailable");
  return legacy;
}

function layerOf(value: unknown): Layer {
  if (value === "core" || value === "market" || value === "dna" || value === "neuron") return value;
  throw new Error("Invalid layer");
}

function cleanLogicalPath(value: unknown): string {
  const path = String(value || "");
  if (!/^data\/[A-Za-z0-9_./-]+\.json$/.test(path) || path.includes("..")) {
    throw new Error(`Invalid logical path: ${path}`);
  }
  return path;
}

function cleanFile(value: unknown): RuntimeFile {
  const file = (value || {}) as Record<string, unknown>;
  const path = cleanLogicalPath(file.path);
  const tier = file.tier;
  if (tier !== "b" && tier !== "c") throw new Error(`Invalid access tier for ${path}`);
  const sha256 = String(file.sha256 || "").toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(sha256)) throw new Error(`Invalid sha256 for ${path}`);
  const sizeBytes = Number(file.size_bytes);
  if (!Number.isSafeInteger(sizeBytes) || sizeBytes < 0 || sizeBytes > 104857600) {
    throw new Error(`Invalid size for ${path}`);
  }
  return { path, tier, sha256, size_bytes: sizeBytes };
}

async function authorize(req: Request) {
  const header = req.headers.get("authorization") || "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : "";
  if (!token) throw new Error("Missing GitHub OIDC bearer token");

  const { payload } = await jwtVerify(token, JWKS, {
    issuer: ISSUER,
    audience: AUDIENCE,
  });
  if (payload.repository !== REPOSITORY) throw new Error("OIDC repository mismatch");
  if (String(payload.repository_id || "") !== REPOSITORY_ID) throw new Error("OIDC repository_id mismatch");
  if (String(payload.repository_owner_id || "") !== REPOSITORY_OWNER_ID) throw new Error("OIDC owner_id mismatch");
  if (payload.ref !== REF) throw new Error("OIDC ref mismatch");
  if (payload.workflow_ref !== EXPECTED_WORKFLOW_REF) throw new Error("OIDC workflow mismatch");
  if (!ALLOWED_EVENTS.has(String(payload.event_name || ""))) throw new Error("OIDC event is not allowed");

  const sha = String(payload.sha || "").toLowerCase();
  if (!/^[0-9a-f]{40}$/.test(sha)) throw new Error("OIDC sha is invalid");
  const runId = Number(payload.run_id);
  if (!Number.isSafeInteger(runId) || runId <= 0) throw new Error("OIDC run_id is invalid");
  return { payload, sha, runId };
}

async function activeHashes(supabase: any): Promise<Set<string>> {
  const { data: heads, error: headsError } = await supabase
    .from("runtime_data_heads")
    .select("layer,generation");
  if (headsError) throw headsError;

  const hashes = new Set<string>();
  for (const head of heads || []) {
    const { data, error } = await supabase
      .from("runtime_data_objects")
      .select("sha256")
      .eq("layer", head.layer)
      .eq("generation", head.generation);
    if (error) throw error;
    for (const row of data || []) hashes.add(String(row.sha256));
  }
  return hashes;
}

async function prepare(supabase: any, auth: Awaited<ReturnType<typeof authorize>>, body: any) {
  const layer = layerOf(body.layer);
  const rawFiles = Array.isArray(body.files) ? body.files : [];
  if (!rawFiles.length || rawFiles.length > 2000) {
    return response({ error: "files must contain 1..2000 items" }, 400);
  }

  const files = rawFiles.map(cleanFile);
  if (new Set(files.map((file) => file.path)).size !== files.length) {
    return response({ error: "duplicate logical path" }, 400);
  }

  const generation = crypto.randomUUID();
  const { data: head, error: headError } = await supabase
    .from("runtime_data_heads")
    .select("generation,revision")
    .eq("layer", layer)
    .maybeSingle();
  if (headError) throw headError;

  const { error: generationError } = await supabase
    .from("runtime_data_generations")
    .insert({
      layer,
      generation,
      source_sha: auth.sha,
      source_run_id: auth.runId,
      source_workflow: WORKFLOW,
      status: "staged",
    });
  if (generationError) throw generationError;

  const rows = files.map((file) => ({
    layer,
    generation,
    logical_path: file.path,
    storage_path: `objects/${file.sha256}.json`,
    access_tier: file.tier,
    sha256: file.sha256,
    size_bytes: file.size_bytes,
  }));
  const { error: objectError } = await supabase.from("runtime_data_objects").insert(rows);
  if (objectError) throw objectError;

  const existing = await activeHashes(supabase);
  const uploadByHash = new Map<string, any>();
  for (const file of files) {
    if (existing.has(file.sha256) || uploadByHash.has(file.sha256)) continue;
    const storagePath = `objects/${file.sha256}.json`;
    const { data, error } = await supabase.storage
      .from(BUCKET)
      .createSignedUploadUrl(storagePath, { upsert: false });
    if (error) throw error;
    uploadByHash.set(file.sha256, {
      sha256: file.sha256,
      storage_path: storagePath,
      signed_url: data.signedUrl,
      token: data.token,
    });
  }

  return response({
    ok: true,
    action: "prepare",
    layer,
    generation,
    source_sha: auth.sha,
    expected_generation: head?.generation ?? null,
    expected_revision: head?.revision ?? 0,
    uploads: [...uploadByHash.values()],
  });
}

async function activate(supabase: any, auth: Awaited<ReturnType<typeof authorize>>, body: any) {
  const layer = layerOf(body.layer);
  const generation = String(body.generation || "");
  if (!/^[0-9a-f-]{36}$/.test(generation)) return response({ error: "Invalid generation" }, 400);
  const expected = body.expected_generation == null ? null : String(body.expected_generation);
  if (expected !== null && !/^[0-9a-f-]{36}$/.test(expected)) {
    return response({ error: "Invalid expected_generation" }, 400);
  }

  const { data: generationRow, error: generationError } = await supabase
    .from("runtime_data_generations")
    .select("source_run_id,source_sha,source_workflow,status")
    .eq("layer", layer)
    .eq("generation", generation)
    .maybeSingle();
  if (generationError) throw generationError;
  if (!generationRow) return response({ error: "Unknown generation" }, 404);
  if (
    Number(generationRow.source_run_id) !== auth.runId ||
    generationRow.source_sha !== auth.sha ||
    generationRow.source_workflow !== WORKFLOW
  ) {
    return response({ error: "Generation belongs to another workflow run" }, 403);
  }

  const { data: ready, error: readyError } = await supabase.rpc(
    "runtime_data_generation_ready",
    { p_layer: layer, p_generation: generation },
  );
  if (readyError) throw readyError;
  if (!ready) return response({ error: "Generation is incomplete" }, 409);

  const { data: activated, error: activateError } = await supabase.rpc(
    "runtime_data_activate_generation",
    {
      p_layer: layer,
      p_generation: generation,
      p_expected_generation: expected,
    },
  );
  if (activateError) throw activateError;
  if (!activated) return response({ error: "Activation rejected by CAS guard" }, 409);

  return response({ ok: true, action: "activate", layer, generation });
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return response({ error: "POST required" }, 405);

  let auth;
  try {
    auth = await authorize(req);
  } catch {
    return response({ error: "unauthorized" }, 401);
  }

  try {
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      serviceKey(),
      { auth: { persistSession: false, autoRefreshToken: false } },
    );
    const body = await req.json().catch(() => ({}));
    if (body.action === "prepare") return await prepare(supabase, auth, body);
    if (body.action === "activate") return await activate(supabase, auth, body);
    return response({ error: "Unknown action" }, 400);
  } catch (err) {
    console.error(err);
    return response({ error: "runtime publisher failed" }, 500);
  }
});
