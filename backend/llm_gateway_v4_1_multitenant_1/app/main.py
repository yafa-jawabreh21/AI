from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse, PlainTextResponse, JSONResponse
from pydantic import BaseModel
import os, httpx, typing as t, json, asyncio, time, uuid
from collections import defaultdict
from datetime import datetime

# -------- OpenTelemetry (optional) --------
def _init_tracing():
    try:
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT","").strip()
        if not endpoint:
            return None
        protocol = os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL","grpc").strip().lower()
        service_name = os.getenv("OTEL_RESOURCE_SERVICE_NAME","llm-gateway")
        headers = os.getenv("OTEL_HEADERS","")
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        if protocol == "grpc":
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=endpoint, headers=dict([h.split("=",1) for h in headers.split(",") if "=" in h]) if headers else None)
        else:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=endpoint, headers=dict([h.split("=",1) for h in headers.split(",") if "=" in h]) if headers else None)
        provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        return trace.get_tracer(__name__)
    except Exception as e:
        print("Tracing init failed:", e)
        return None

tracer = _init_tracing()

app = FastAPI(title="LLM Gateway v4.1 — Multi-tenant + OTLP", version="4.1.0")

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def env(name: str, default: str = "") -> str:
    return os.getenv(name, default)

# ---------- Multi-tenant keys ----------
API_KEYS_FILE = env("API_KEYS_FILE", "").strip()
MULTI_TENANT = False
TENANT_KEYS: dict[str, dict] = {}   # key -> {tenant, rps, burst, quota_daily}
if API_KEYS_FILE and os.path.exists(API_KEYS_FILE):
    try:
        with open(API_KEYS_FILE, "r", encoding="utf-8") as f:
            arr = json.load(f)
        for item in arr:
            TENANT_KEYS[str(item["key"])] = {
                "tenant": item["tenant"],
                "rps": float(item.get("rps", 5)),
                "burst": float(item.get("burst", 20)),
                "quota_daily": int(item.get("quota_daily", 10000)),
            }
        MULTI_TENANT = True
        print(f"Multi-tenant mode ON. Tenants: {[v['tenant'] for v in TENANT_KEYS.values()]}")
    except Exception as e:
        print("Failed loading API_KEYS_FILE:", e)

BACKEND_KEY = env("BACKEND_API_KEY", "") if not MULTI_TENANT else ""

# ---------- Rate limit + quotas ----------
GLOBAL_RPS = float(env("RATE_LIMIT_RPS", "5") or "5")
GLOBAL_BURST = float(env("RATE_LIMIT_BURST", "20") or "20")

# token buckets
TOKENS = defaultdict(lambda: {"tokens": GLOBAL_BURST, "ts": time.time(), "rps": GLOBAL_RPS, "burst": GLOBAL_BURST})
# daily quotas per key {date_str: {key: used_count}}
QUOTAS: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

def _id_for_request(req: Request, key: str | None) -> str:
    if MULTI_TENANT:
        return f"key:{key or 'unknown'}"
    if key:
        return f"key:{key}"
    ip = req.client.host if req.client else "unknown"
    return f"ip:{ip}"

def rate_limit_and_quota(req: Request, key: str | None):
    # choose limits
    rps, burst = GLOBAL_RPS, GLOBAL_BURST
    if MULTI_TENANT and key in TENANT_KEYS:
        rps = TENANT_KEYS[key]["rps"]
        burst = TENANT_KEYS[key]["burst"]

    ident = _id_for_request(req, key)
    b = TOKENS[ident]
    now = time.time()
    # update RPS/BURST if changed
    b["rps"] = rps
    b["burst"] = burst
    # refill
    elapsed = now - b["ts"]
    b["tokens"] = min(b["burst"], b["tokens"] + elapsed * b["rps"])
    b["ts"] = now
    if b["tokens"] < 1.0:
        raise HTTPException(429, "Rate limit exceeded")
    b["tokens"] -= 1.0

    # quota (per day, simple count of requests)
    if MULTI_TENANT and key in TENANT_KEYS:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        used = QUOTAS[today][key]
        if used >= TENANT_KEYS[key]["quota_daily"]:
            raise HTTPException(403, "Daily quota exceeded for this API key")
        QUOTAS[today][key] = used + 1

# ---------- Metrics & logs ----------
METRICS = {
    "requests_total": 0,
    "errors_total": 0,
    "latency_sum_ms": 0.0,
    "latency_count": 0,
    "endpoint_requests": defaultdict(int),
    "endpoint_errors": defaultdict(int),
}

def record_metrics(path: str, start_ts: float, ok: bool):
    METRICS["requests_total"] += 1
    METRICS["endpoint_requests"][path] += 1
    if not ok:
        METRICS["errors_total"] += 1
        METRICS["endpoint_errors"][path] += 1
    METRICS["latency_sum_ms"] += (time.time() - start_ts) * 1000.0
    METRICS["latency_count"] += 1

@app.middleware("http")
async def guard_and_trace(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    api_key = request.headers.get("X-API-KEY", "")

    # Multi-tenant auth
    if MULTI_TENANT:
        if request.url.path not in ("/healthz", "/metrics"):
            if api_key not in TENANT_KEYS:
                return JSONResponse({"detail":"Invalid or missing X-API-KEY"}, status_code=401)
    else:
        if env("BACKEND_API_KEY") and request.url.path not in ("/healthz", "/metrics"):
            if api_key != env("BACKEND_API_KEY"):
                return JSONResponse({"detail":"Invalid or missing X-API-KEY"}, status_code=401)

    # rate+quota
    start = time.time()
    ok = True
    status = 500
    try:
        rate_limit_and_quota(request, api_key if api_key else None)
        # tracing span
        if tracer:
            with tracer.start_as_current_span("http.request") as span:
                span.set_attribute("http.target", str(request.url.path))
                span.set_attribute("http.method", request.method)
                if MULTI_TENANT:
                    span.set_attribute("tenant", TENANT_KEYS.get(api_key,{}).get("tenant","unknown"))
                response = await call_next(request)
        else:
            response = await call_next(request)
        status = response.status_code
        ok = status < 400
    except HTTPException as e:
        status = e.status_code
        ok = False
        response = JSONResponse({"detail": e.detail}, status_code=e.status_code)
    except Exception as e:
        status = 500
        ok = False
        response = JSONResponse({"detail": "Internal Server Error"}, status_code=500)
    finally:
        record_metrics(str(request.url.path), start, ok)
        log = {
            "ts": time.time(),
            "request_id": req_id,
            "path": str(request.url.path),
            "status": status,
            "ok": ok,
            "client": request.client.host if request.client else None,
        }
        if MULTI_TENANT and api_key in TENANT_KEYS:
            log["tenant"] = TENANT_KEYS[api_key]["tenant"]
        print(json.dumps(log, ensure_ascii=False))
        if hasattr(response, "headers"):
            response.headers["X-Request-ID"] = req_id
        return response

# ---------- Schemas ----------
class CompleteIn(BaseModel):
    prompt: str
    model: t.Optional[str] = None
    temperature: t.Optional[float] = 0.2
    max_tokens: t.Optional[int] = 512

class CompleteOut(BaseModel):
    provider: str
    model: str
    text: str

def get_provider() -> str:
    return env("LLM_PROVIDER", "local_stub").lower()

def get_model(override: t.Optional[str]) -> str:
    return override or env("LLM_MODEL", "gpt-4o-mini")

@app.get("/healthz")
async def healthz():
    return {"ok": True, "multi_tenant": MULTI_TENANT}

@app.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    lines = []
    lines.append(f"requests_total {METRICS['requests_total']}")
    lines.append(f"errors_total {METRICS['errors_total']}")
    avg = 0.0
    if METRICS['latency_count'] > 0:
        avg = METRICS['latency_sum_ms'] / METRICS['latency_count']
    lines.append(f"latency_avg_ms {avg:.2f}")
    for path,count in METRICS['endpoint_requests'].items():
        lines.append(f'endpoint_requests{{path="{path}"}} {count}')
    for path,count in METRICS['endpoint_errors'].items():
        lines.append(f'endpoint_errors{{path="{path}"}} {count}')
    return "\n".join(lines) + "\n"

# ---------- Core LLM proxy ----------
@app.post("/llm/complete", response_model=CompleteOut)
async def llm_complete(body: CompleteIn, request: Request):
    provider = get_provider()
    model = get_model(body.model)
    prompt = body.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Empty prompt")

    if tracer:
        with tracer.start_as_current_span("llm.complete") as span:
            span.set_attribute("provider", provider)
            span.set_attribute("model", model)
            text = await _call_provider(provider, model, prompt, body.temperature, body.max_tokens)
    else:
        text = await _call_provider(provider, model, prompt, body.temperature, body.max_tokens)

    return CompleteOut(provider=provider, model=model, text=text)

async def _call_provider(provider: str, model: str, prompt: str, temperature: float, max_tokens: int) -> str:
    if provider == "openai":
        endpoint = env("LLM_ENDPOINT", "https://api.openai.com/v1").rstrip("/")
        api_key = env("LLM_API_KEY")
        if not api_key:
            raise HTTPException(400, "Missing LLM_API_KEY for OpenAI")
        url = f"{endpoint}/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}"}
        payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": temperature, "max_tokens": max_tokens}
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, headers=headers, json=payload)
        if r.status_code >= 400:
            raise HTTPException(r.status_code, r.text)
        data = r.json()
        return data["choices"][0]["message"]["content"]

    elif provider == "azure":
        base = env("LLM_ENDPOINT").rstrip("/")
        api_key = env("LLM_API_KEY")
        deploy = env("AZURE_DEPLOYMENT")
        api_version = env("AZURE_API_VERSION", "2024-02-15-preview")
        if not (base and api_key and deploy):
            raise HTTPException(400, "Missing one of LLM_ENDPOINT, LLM_API_KEY, AZURE_DEPLOYMENT")
        url = f"{base}/openai/deployments/{deploy}/chat/completions?api-version={api_version}"
        headers = {"api-key": api_key}
        payload = {"messages": [{"role": "user", "content": prompt}], "temperature": temperature, "max_tokens": max_tokens}
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, headers=headers, json=payload)
        if r.status_code >= 400:
            raise HTTPException(r.status_code, r.text)
        data = r.json()
        return data["choices"][0]["message"]["content"]

    elif provider == "vllm":
        endpoint = env("LLM_ENDPOINT", "http://127.0.0.1:8000/v1").rstrip("/")
        api_key = env("LLM_API_KEY", "")
        url = f"{endpoint}/chat/completions"
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": temperature, "max_tokens": max_tokens}
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, headers=headers, json=payload)
        if r.status_code >= 400:
            raise HTTPException(r.status_code, r.text)
        data = r.json()
        return data["choices"][0]["message"]["content"]

    elif provider == "ollama":
        base = env("LLM_ENDPOINT", "http://localhost:11434").rstrip("/")
        url = f"{base}/api/generate"
        payload = {"model": model, "prompt": prompt, "stream": False}
        async with httpx.AsyncClient(timeout=180) as client:
            r = await client.post(url, json=payload)
        if r.status_code >= 400:
            raise HTTPException(r.status_code, r.text)
        data = r.json()
        return data.get("response", "")

    elif provider == "local_stub":
        return f"[STUB REPLY] {prompt[:80]}..."

    else:
        raise HTTPException(400, f"Unsupported provider: {provider}")

# ---------- Simple UI kept minimal ----------
HTML = """<!doctype html><html dir="rtl" lang="ar"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>LLM Gateway v4.1 — Multi-tenant</title>
<style>body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu;max-width:860px;margin:20px auto;padding:16px}
.card{border:1px solid #ddd;border-radius:14px;padding:16px;margin:12px 0;box-shadow:0 2px 8px rgba(0,0,0,0.04)}
label{display:block;margin:8px 0 4px}input,textarea,button{width:100%;padding:10px;border:1px solid #ccc;border-radius:10px}
button{cursor:pointer}pre{white-space:pre-wrap;background:#fafafa;border:1px dashed #ddd;padding:12px;border-radius:10px;min-height:100px}</style>
</head><body>
<h2>LLM Gateway v4.1 — Multi-tenant</h2>
<div class="card">
<label>API Key</label><input id="xkey" placeholder="X-API-KEY (من api_keys.json)">
<label>النموذج (اختياري)</label><input id="model">
<label>النص</label><textarea id="prompt" rows="4" placeholder="اسألني..."></textarea>
<button onclick="go()">/llm/complete</button>
<pre id="out"></pre>
</div>
<script>
async function go(){
  const out=document.getElementById('out');
  const key=document.getElementById('xkey').value.trim();
  const model=document.getElementById('model').value.trim();
  const prompt=document.getElementById('prompt').value;
  out.textContent='...';
  const r=await fetch('/llm/complete',{method:'POST',headers:{'Content-Type':'application/json','X-API-KEY':key},body:JSON.stringify({prompt,model})});
  const j=await r.json();
  out.textContent=JSON.stringify(j,null,2);
}
</script>
</body></html>"""

@app.get("/", response_class=HTMLResponse)
async def root():
    return HTML
@app.post("/api/admin/update")
async def admin_update(payload: dict):
    password = payload.get("password")
    new_password = payload.get("new_password")
    # implement your logic here
    if password != "your_old_pwd":
        return JSONResponse({"ok": False, "detail": "Invalid password"})
    # Update password logic...
    return {"ok": True}
