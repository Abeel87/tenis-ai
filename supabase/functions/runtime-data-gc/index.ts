import { createClient } from "jsr:@supabase/supabase-js@2.116.0";
import { createRemoteJWKSet, jwtVerify } from "npm:jose@6.2.12";

const BUCKET = "tenis-ai-runtime-private";
const AUDIENCE = "tenis-ai-runtime-gc";
const REPOSITORY = "Abeel87/tenis-ai";
const REPOSITORY_ID = "1339352577";
const REPOSITORY_OWNER_ID = "198365428";
const REF = "refs/heads/main";
const WORKFLOW = ".github/workflows/runtime-private-delivery.yml";
const EXPECTED_WORKFLOW_REF = `${REPOSITORY}/${WORKFLOW}@${REF}`;
const ISSUER = "https://token.actions.githubusercontent.com";
const JWKS = createRemoteJWKSet(new URL(`${ISSUER}/.well-known/jwks`));
const ALLOWED_EVENTS = new Set(["workflow_run", "workflow_dispatch", "push"]);
const RETIRED_KEEP_PER_LAYER = 1;
const STAGED_GRACE_MS = 6 * 60 * 60 * 1000;
const REMOVE_BATCH = 100;

type Generation = {
  layer: string;
  generation: string;
  status: string;
  created_at: string;
  activated_at: string | null;
};

type RuntimeObject = {
  layer: string;
  generation: string;
  storage_path: string;
};

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
    } catch {}
  }
  const legacy = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!legacy) throw new Error("Supabase secret key is unavailable");
  return legacy;
}

async function authorize(req: Request) {
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
}

function key(layer: string, generation: string) {
  return `${layer}:${generation}`;
}

function newestFirst(a: Generation, b: Generation) {
  return Date.parse(b.activated_at || b.created_at) - Date.parse(a.activated_at || a.created_at);
}

async function collect(supabase: any, dryRun: boolean) {
  const [{ data: generations, error: generationError }, { data: heads, error: headError }, { data: objects, error: objectError }] = await Promise.all([
    supabase.from("runtime_data_generations").select("layer,generation,status,created_at,activated_at"),
    supabase.from("runtime_data_heads").select("layer,generation"),
    supabase.from("runtime_data_objects").select("layer,generation,storage_path"),
  ]);
  if (generationError) throw generationError;
  if (headError) throw headError;
  if (objectError) throw objectError;

  const rows = (generations || []) as Generation[];
  const allObjects = (objects || []) as RuntimeObject[];
  const keep = new Set<string>((heads || []).map((h: any) => key(h.layer, h.generation)));
  const now = Date.now();

  const retiredByLayer = new Map<string, Generation[]>();
  for (const row of rows) {
    if (row.status !== "retired") continue;
    const list = retiredByLayer.get(row.layer) || [];
    list.push(row);
    retiredByLayer.set(row.layer, list);
  }
  for (const list of retiredByLayer.values()) {
    list.sort(newestFirst);
    for (const row of list.slice(0, RETIRED_KEEP_PER_LAYER)) keep.add(key(row.layer, row.generation));
  }

  for (const row of rows) {
    if (row.status !== "staged") continue;
    const age = now - Date.parse(row.created_at);
    if (!Number.isFinite(age) || age < STAGED_GRACE_MS) keep.add(key(row.layer, row.generation));
  }

  const deletable = rows.filter((row) => {
    const k = key(row.layer, row.generation);
    return !keep.has(k) && (row.status === "retired" || row.status === "staged");
  });
  const deleteKeys = new Set(deletable.map((row) => key(row.layer, row.generation)));
  const candidatePaths = new Set(
    allObjects.filter((obj) => deleteKeys.has(key(obj.layer, obj.generation))).map((obj) => obj.storage_path),
  );
  const retainedPaths = new Set(
    allObjects.filter((obj) => !deleteKeys.has(key(obj.layer, obj.generation))).map((obj) => obj.storage_path),
  );
  const orphanPaths = [...candidatePaths].filter((path) => !retainedPaths.has(path)).sort();

  if (!dryRun) {
    for (const row of deletable) {
      const { error } = await supabase
        .from("runtime_data_generations")
        .delete()
        .eq("layer", row.layer)
        .eq("generation", row.generation)
        .in("status", ["retired", "staged"]);
      if (error) throw error;
    }
    for (let i = 0; i < orphanPaths.length; i += REMOVE_BATCH) {
      const { error } = await supabase.storage.from(BUCKET).remove(orphanPaths.slice(i, i + REMOVE_BATCH));
      if (error) throw error;
    }
  }

  return {
    ok: true,
    dry_run: dryRun,
    retained_generations: rows.length - deletable.length,
    deleted_generations: deletable.length,
    deleted_storage_objects: orphanPaths.length,
    policy: {
      active: "always",
      retired_per_layer: RETIRED_KEEP_PER_LAYER,
      staged_grace_hours: STAGED_GRACE_MS / 3600000,
    },
  };
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return response({ error: "POST required" }, 405);
  try {
    await authorize(req);
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
    if (body.action !== "collect") return response({ error: "Unknown action" }, 400);
    return response(await collect(supabase, body.dry_run === true));
  } catch (err) {
    console.error(err);
    return response({ error: "runtime gc failed" }, 500);
  }
});
