import { createClient } from "jsr:@supabase/supabase-js@2.116.0";

const BUCKET = "tenis-ai-runtime-private";
const SIGNED_URL_TTL_SECONDS = 60;
const ALLOWED_ORIGINS = new Set([
  "https://abeel87.github.io",
  "http://127.0.0.1:8000",
  "http://localhost:8000",
]);

function corsHeaders(req: Request) {
  const origin = req.headers.get("origin") || "";
  return {
    "access-control-allow-origin": ALLOWED_ORIGINS.has(origin) ? origin : "https://abeel87.github.io",
    "access-control-allow-headers": "authorization, apikey, content-type",
    "access-control-allow-methods": "POST, OPTIONS",
    "vary": "origin",
  };
}

function response(req: Request, body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      ...corsHeaders(req),
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

function cleanLogicalPath(value: unknown): string {
  const path = String(value || "");
  if (!/^data\/[A-Za-z0-9_./-]+\.json$/.test(path) || path.includes("..")) {
    throw new Error("Invalid logical path");
  }
  return path;
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders(req) });
  if (req.method !== "POST") return response(req, { error: "POST required" }, 405);

  try {
    const header = req.headers.get("authorization") || "";
    const token = header.startsWith("Bearer ") ? header.slice(7) : "";
    if (!token) return response(req, { error: "unauthorized" }, 401);

    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      serviceKey(),
      { auth: { persistSession: false, autoRefreshToken: false } },
    );

    // getUser performs a server-side Auth check; decoded client claims are not trusted.
    const { data: userData, error: userError } = await supabase.auth.getUser(token);
    if (userError || !userData.user) return response(req, { error: "unauthorized" }, 401);

    const { data: profile, error: profileError } = await supabase
      .from("profiles")
      .select("role,banned_at")
      .eq("id", userData.user.id)
      .maybeSingle();
    if (profileError) throw profileError;
    if (!profile || profile.banned_at) return response(req, { error: "forbidden" }, 403);

    const body = await req.json().catch(() => ({}));
    let logicalPath: string;
    try {
      logicalPath = cleanLogicalPath(body.path);
    } catch {
      return response(req, { error: "invalid path" }, 400);
    }

    const { data: heads, error: headsError } = await supabase
      .from("runtime_data_heads")
      .select("layer,generation,source_run_id,updated_at");
    if (headsError) throw headsError;

    const lookups = await Promise.all(
      (heads || []).map(async (head: any) => {
        const { data, error } = await supabase
          .from("runtime_data_objects")
          .select("layer,generation,logical_path,storage_path,access_tier,sha256,size_bytes")
          .eq("layer", head.layer)
          .eq("generation", head.generation)
          .eq("logical_path", logicalPath)
          .maybeSingle();
        if (error) throw error;
        return data ? { ...data, head_updated_at: head.updated_at, source_run_id: head.source_run_id } : null;
      }),
    );
    const candidates = lookups.filter(Boolean) as any[];
    if (!candidates.length) return response(req, { error: "not found" }, 404);

    candidates.sort((a, b) => {
      const byTime = Date.parse(b.head_updated_at) - Date.parse(a.head_updated_at);
      if (byTime !== 0) return byTime;
      return Number(b.source_run_id) - Number(a.source_run_id);
    });
    const target = candidates[0];

    // Never fall back to an older, less restrictive copy of the same logical path.
    if (target.access_tier === "c" && profile.role !== "admin") {
      return response(req, { error: "admin required" }, 403);
    }

    const { data: signed, error: signedError } = await supabase.storage
      .from(BUCKET)
      .createSignedUrl(target.storage_path, SIGNED_URL_TTL_SECONDS);
    if (signedError) throw signedError;

    return response(req, {
      path: logicalPath,
      layer: target.layer,
      generation: target.generation,
      sha256: target.sha256,
      size_bytes: target.size_bytes,
      expires_in: SIGNED_URL_TTL_SECONDS,
      url: signed.signedUrl,
    });
  } catch (err) {
    console.error(err);
    return response(req, { error: "runtime reader failed" }, 500);
  }
});
