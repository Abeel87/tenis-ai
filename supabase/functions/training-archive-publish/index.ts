import { createClient } from "jsr:@supabase/supabase-js@2.116.0";
import { createRemoteJWKSet, jwtVerify } from "npm:jose@6.2.12";

const BUCKET = "tenis-ai-training-archive-private";
const AUDIENCE = "tenis-ai-training-archive-publisher";
const REPOSITORY = "Abeel87/tenis-ai";
const REPOSITORY_ID = "1339352577";
const REPOSITORY_OWNER_ID = "198365428";
const REF = "refs/heads/main";
const WORKFLOW = ".github/workflows/training-archive-inventory.yml";
const EXPECTED_WORKFLOW_REF = `${REPOSITORY}/${WORKFLOW}@${REF}`;
const ISSUER = "https://token.actions.githubusercontent.com";
const JWKS = createRemoteJWKSet(new URL(`${ISSUER}/.well-known/jwks`));
const ALLOWED_EVENTS = new Set(["workflow_run", "workflow_dispatch", "push"]);
const MAX_OBJECT_BYTES = 47185920;
const MAX_BATCH_FILES = 200;
const MAX_ERROR_MESSAGE = 400;

const CLASSES = new Set(["historical_csv_raw", "pbp_match_raw", "pbp_state"]);

type ArchiveFile = {
  path: string;
  class: string;
  provider: string;
  sha256: string;
  size_bytes: number;
};

type AuthContext = {
  sha: string;
  runId: number;
  runAttempt: number;
  eventName: string;
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

function safeError(err: unknown) {
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

function positiveInteger(value: unknown, label: string): number {
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed <= 0) throw new Error(`Invalid ${label}`);
  return parsed;
}

function nonNegativeInteger(value: unknown, label: string): number {
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed) || parsed < 0) throw new Error(`Invalid ${label}`);
  return parsed;
}

function optionalPositiveInteger(value: unknown, label: string): number | null {
  if (value == null || value === "") return null;
  return positiveInteger(value, label);
}

function optionalSha(value: unknown, label: string): string | null {
  if (value == null || value === "") return null;
  const sha = String(value).toLowerCase();
  if (!/^[0-9a-f]{40}$/.test(sha)) throw new Error(`Invalid ${label}`);
  return sha;
}

function cleanLogicalPath(value: unknown): string {
  const path = String(value || "").replaceAll("\\", "/").replace(/^\.\//, "");
  if (
    path.includes("..") ||
    !/^[A-Za-z0-9_./-]+\.(?:json|json\.gz|csv\.gz)$/.test(path)
  ) {
    throw new Error(`Invalid logical path: ${path}`);
  }
  return path;
}

function cleanFile(value: unknown): ArchiveFile {
  const file = (value || {}) as Record<string, unknown>;
  const path = cleanLogicalPath(file.path ?? file.logical_path);
  const klass = String(file.class || "");
  if (!CLASSES.has(klass)) throw new Error(`Invalid archive class for ${path}`);
  const provider = String(file.provider || "");
  if (!/^[A-Za-z0-9_.:-]{1,80}$/.test(provider)) throw new Error(`Invalid provider for ${path}`);
  const sha256 = String(file.sha256 || "").toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(sha256)) throw new Error(`Invalid sha256 for ${path}`);
  const sizeBytes = nonNegativeInteger(file.size_bytes, `size for ${path}`);
  if (sizeBytes > MAX_OBJECT_BYTES) throw new Error(`Object exceeds 45 MiB limit: ${path}`);
  return { path, class: klass, provider, sha256, size_bytes: sizeBytes };
}

async function authorize(req: Request): Promise<AuthContext> {
  const header = req.headers.get("authorization") || "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : "";
  if (!token) throw new Error("Missing GitHub OIDC bearer token");

  const { payload } = await jwtVerify(token, JWKS, { issuer: ISSUER, audience: AUDIENCE });
  if (payload.repository !== REPOSITORY) throw new Error("OIDC repository mismatch");
  if (String(payload.repository_id || "") !== REPOSITORY_ID) throw new Error("OIDC repository_id mismatch");
  if (String(payload.repository_owner_id || "") !== REPOSITORY_OWNER_ID) throw new Error("OIDC owner_id mismatch");
  if (payload.ref !== REF) throw new Error("OIDC ref mismatch");
  if (payload.workflow_ref !== EXPECTED_WORKFLOW_REF) throw new Error("OIDC workflow mismatch");
  const eventName = String(payload.event_name || "");
  if (!ALLOWED_EVENTS.has(eventName)) throw new Error("OIDC event is not allowed");

  const sha = String(payload.sha || "").toLowerCase();
  if (!/^[0-9a-f]{40}$/.test(sha)) throw new Error("OIDC sha is invalid");
  return {
    sha,
    runId: positiveInteger(payload.run_id, "OIDC run_id"),
    runAttempt: positiveInteger(payload.run_attempt || 1, "OIDC run_attempt"),
    eventName,
  };
}

async function ownedManifest(supabase: any, auth: AuthContext, manifestId: string) {
  if (!/^[0-9a-f-]{36}$/.test(manifestId)) throw new Error("Invalid manifest_id");
  const { data, error } = await supabase
    .from("training_archive_manifests")
    .select("manifest_id,archive_run_id,archive_run_attempt,source_sha,status")
    .eq("manifest_id", manifestId)
    .maybeSingle();
  if (error) throw error;
  if (!data) throw new Error("Unknown manifest");
  if (
    Number(data.archive_run_id) !== auth.runId ||
    Number(data.archive_run_attempt) !== auth.runAttempt ||
    data.source_sha !== auth.sha
  ) {
    throw new Error("Manifest belongs to another workflow run");
  }
  return data;
}

async function start(supabase: any, auth: AuthContext, body: any) {
  const schemaVersion = positiveInteger(body.inventory_schema_version, "inventory_schema_version");
  const expectedFiles = positiveInteger(body.expected_files, "expected_files");
  const expectedBytes = nonNegativeInteger(body.expected_bytes, "expected_bytes");
  const expectedUniqueObjects = positiveInteger(body.expected_unique_objects, "expected_unique_objects");
  const expectedUniqueBytes = nonNegativeInteger(body.expected_unique_bytes, "expected_unique_bytes");
  if (expectedUniqueObjects > expectedFiles || expectedUniqueBytes > expectedBytes) {
    return response({ error: "Invalid archive summary" }, 400);
  }

  const { data: existing, error: existingError } = await supabase
    .from("training_archive_manifests")
    .select("manifest_id,status")
    .eq("archive_run_id", auth.runId)
    .eq("archive_run_attempt", auth.runAttempt)
    .maybeSingle();
  if (existingError) throw existingError;
  if (existing) {
    return response({ ok: true, action: "start", manifest_id: existing.manifest_id, status: existing.status, reused: true });
  }

  const manifestId = crypto.randomUUID();
  const sourceCacheKey = body.source_cache_key == null ? null : String(body.source_cache_key).slice(0, 300);
  const producerRunId = optionalPositiveInteger(body.producer_run_id, "producer_run_id");
  const producerHeadSha = optionalSha(body.producer_head_sha, "producer_head_sha");
  const { error } = await supabase.from("training_archive_manifests").insert({
    manifest_id: manifestId,
    archive_run_id: auth.runId,
    archive_run_attempt: auth.runAttempt,
    source_sha: auth.sha,
    source_workflow: WORKFLOW,
    producer_run_id: producerRunId,
    producer_head_sha: producerHeadSha,
    source_cache_key: sourceCacheKey,
    inventory_schema_version: schemaVersion,
    expected_files: expectedFiles,
    expected_bytes: expectedBytes,
    expected_unique_objects: expectedUniqueObjects,
    expected_unique_bytes: expectedUniqueBytes,
    status: "staged",
  });
  if (error) throw error;
  return response({ ok: true, action: "start", manifest_id: manifestId, status: "staged", reused: false });
}

async function prepareBatch(supabase: any, auth: AuthContext, body: any) {
  const manifestId = String(body.manifest_id || "");
  const manifest = await ownedManifest(supabase, auth, manifestId);
  if (manifest.status === "complete") return response({ error: "Manifest is already complete" }, 409);

  const rawFiles = Array.isArray(body.files) ? body.files : [];
  if (!rawFiles.length || rawFiles.length > MAX_BATCH_FILES) {
    return response({ error: `files must contain 1..${MAX_BATCH_FILES} items` }, 400);
  }
  const files = rawFiles.map(cleanFile);
  if (new Set(files.map((file) => file.path)).size !== files.length) {
    return response({ error: "duplicate logical path in batch" }, 400);
  }

  const paths = files.map((file) => file.path);
  const { data: existingEntries, error: entryReadError } = await supabase
    .from("training_archive_entries")
    .select("logical_path,object_sha256,object_class,provider,size_bytes")
    .eq("manifest_id", manifestId)
    .in("logical_path", paths);
  if (entryReadError) throw entryReadError;
  const entryByPath = new Map((existingEntries || []).map((row: any) => [row.logical_path, row]));
  const missingEntries = [];
  for (const file of files) {
    const existing = entryByPath.get(file.path) as any;
    if (existing) {
      if (
        existing.object_sha256 !== file.sha256 ||
        existing.object_class !== file.class ||
        existing.provider !== file.provider ||
        Number(existing.size_bytes) !== file.size_bytes
      ) {
        return response({ error: `immutable manifest entry mismatch: ${file.path}` }, 409);
      }
      continue;
    }
    missingEntries.push(file);
  }

  const uniqueBySha = new Map<string, ArchiveFile>();
  for (const file of files) {
    const previous = uniqueBySha.get(file.sha256);
    if (previous && previous.size_bytes !== file.size_bytes) {
      return response({ error: `sha256 size mismatch: ${file.sha256}` }, 409);
    }
    uniqueBySha.set(file.sha256, file);
  }
  const shas = [...uniqueBySha.keys()];
  const { data: existingObjects, error: objectReadError } = await supabase
    .from("training_archive_objects")
    .select("sha256,storage_path,size_bytes,verified_at")
    .in("sha256", shas);
  if (objectReadError) throw objectReadError;
  const objectBySha = new Map((existingObjects || []).map((row: any) => [row.sha256, row]));

  const newObjects = [];
  for (const [sha256, file] of uniqueBySha) {
    const expectedPath = `objects/${sha256.slice(0, 2)}/${sha256}`;
    const existing = objectBySha.get(sha256) as any;
    if (existing) {
      if (existing.storage_path !== expectedPath || Number(existing.size_bytes) !== file.size_bytes) {
        return response({ error: `immutable object mismatch: ${sha256}` }, 409);
      }
      continue;
    }
    newObjects.push({ sha256, storage_path: expectedPath, size_bytes: file.size_bytes });
  }
  if (newObjects.length) {
    const { error } = await supabase.from("training_archive_objects").insert(newObjects);
    if (error) throw error;
    for (const row of newObjects) objectBySha.set(row.sha256, { ...row, verified_at: null });
  }

  if (missingEntries.length) {
    const { error } = await supabase.from("training_archive_entries").insert(
      missingEntries.map((file) => ({
        manifest_id: manifestId,
        logical_path: file.path,
        object_sha256: file.sha256,
        object_class: file.class,
        provider: file.provider,
        size_bytes: file.size_bytes,
      })),
    );
    if (error) throw error;
  }

  const { data: objectHealth, error: healthError } = await supabase.rpc("training_archive_probe_objects", {
    p_sha256: shas,
  });
  if (healthError) throw healthError;
  const healthBySha = new Map((objectHealth || []).map((row: any) => [row.sha256, row]));
  const needsUpload = new Set<string>();
  for (const [sha256] of uniqueBySha) {
    const health = healthBySha.get(sha256) as any;
    if (!health) {
      return response({ error: `Archive object health row is missing: ${sha256}` }, 409);
    }
    if (health.present === true && health.size_matches !== true) {
      return response({ error: `Archive object has unexpected physical size: ${sha256}` }, 409);
    }
    if (health.present !== true) needsUpload.add(sha256);
  }

  const uploadCandidates = [...uniqueBySha.values()].filter((file) => needsUpload.has(file.sha256));
  const uploads = await Promise.all(uploadCandidates.map(async (file) => {
    const storagePath = `objects/${file.sha256.slice(0, 2)}/${file.sha256}`;
    const { data, error } = await supabase.storage.from(BUCKET).createSignedUploadUrl(storagePath, { upsert: false });
    if (error) throw error;
    return { sha256: file.sha256, storage_path: storagePath, signed_url: data.signedUrl };
  }));

  return response({ ok: true, action: "prepare_batch", manifest_id: manifestId, entries: files.length, uploads });
}

async function confirmBatch(supabase: any, auth: AuthContext, body: any) {
  const manifestId = String(body.manifest_id || "");
  const manifest = await ownedManifest(supabase, auth, manifestId);
  if (manifest.status === "complete") return response({ ok: true, action: "confirm_batch", confirmed: 0, complete: true });

  const raw = Array.isArray(body.sha256) ? body.sha256 : [];
  const shas = [...new Set(raw.map((value: unknown) => String(value || "").toLowerCase()))];
  if (!shas.length || shas.length > MAX_BATCH_FILES || shas.some((sha) => !/^[0-9a-f]{64}$/.test(sha))) {
    return response({ error: `sha256 must contain 1..${MAX_BATCH_FILES} unique digests` }, 400);
  }
  const { data, error } = await supabase.rpc("training_archive_confirm_objects", {
    p_manifest_id: manifestId,
    p_sha256: shas,
  });
  if (error) throw error;
  const confirmed = Number(data || 0);
  if (confirmed !== shas.length) {
    return response({ error: "Archive batch is incomplete in Storage", confirmed, expected: shas.length }, 409);
  }
  return response({ ok: true, action: "confirm_batch", manifest_id: manifestId, confirmed });
}

async function complete(supabase: any, auth: AuthContext, body: any) {
  const manifestId = String(body.manifest_id || "");
  const manifest = await ownedManifest(supabase, auth, manifestId);
  if (manifest.status === "complete") return response({ ok: true, action: "complete", manifest_id: manifestId, reused: true });
  const { data, error } = await supabase.rpc("training_archive_finalize_manifest", { p_manifest_id: manifestId });
  if (error) throw error;
  if (data !== true) return response({ error: "Manifest is not complete or verified" }, 409);
  return response({ ok: true, action: "complete", manifest_id: manifestId, reused: false });
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return response({ error: "POST required" }, 405);

  let auth: AuthContext;
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
    if (body.action === "start") return await start(supabase, auth, body);
    if (body.action === "prepare_batch") return await prepareBatch(supabase, auth, body);
    if (body.action === "confirm_batch") return await confirmBatch(supabase, auth, body);
    if (body.action === "complete") return await complete(supabase, auth, body);
    return response({ error: "Unknown action" }, 400);
  } catch (err) {
    const detail = safeError(err);
    console.error("training-archive-publish", detail);
    return response({ error: "training archive publisher failed", detail }, 500);
  }
});