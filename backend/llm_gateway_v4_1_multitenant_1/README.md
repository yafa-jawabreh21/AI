# LLM Gateway v4.1 — Multi-tenant + OTLP
Generated: 2025-09-08T18:20:38.824985Z

## الميزات الجديدة
- **مفاتيح متعددة (Multi-tenant)** عبر `api_keys.json` (مفتاح لكل عميل/منصة مع `rps`/`burst`/`quota_daily`).
- **حدود وحصص لكل مفتاح** (Token Bucket + حصة يومية)، مع إحصاءات عامة `/metrics`.
- **OpenTelemetry OTLP Exporter**: تصدير التتبّع (Spans) إلى Jaeger/Tempo/OTLP (gRPC أو HTTP).
- تبقى كل مزايا v4 السابقة (مزودات متعددة، إلخ).

## بدء التشغيل
```bash
cd backend_v4_1
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# انسخ config.env و api_keys.json بجذر المشروع (أو عدّل المسارات)
set -a; source ../config.env; set +a
uvicorn app.main:app --host 0.0.0.0 --port 8000
# افتح: http://127.0.0.1:8000/
```

## التهيئة
- `API_KEYS_FILE=./api_keys.json` → يفعّل وضع multi-tenant ويجبر على هيدر `X-API-KEY` من ملف المفاتيح.
- إذا حذفت `API_KEYS_FILE` ولم تضع مفاتيح متعددة → يمكن استخدام `BACKEND_API_KEY` كحماية عامة.
- التتبع (اختياري):
  - `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317`
  - `OTEL_EXPORTER_OTLP_PROTOCOL=grpc`  (أو `http/protobuf`)
  - `OTEL_RESOURCE_SERVICE_NAME=llm-gateway-v4_1`
  - `OTEL_HEADERS=api-key=...`  لو مزوّد الـ OTEL يحتاج هيدر.

## المتركس
- `GET /metrics` يرجّع counters بسيطة (requests/errors/latency + per-endpoint). يمكن جمعها بـ Prometheus.

## ملاحظات
- الحصص اليومية في الذاكرة (تُصفّر عند إعادة تشغيل الخدمة). لو أردت تخزينًا دائمًا، نربط Redis/DB.
- إذا أردت بثًا متدفقًا وحماية بالمفاتيح للـ SSE، استخدم Nginx لحقن `X-API-KEY` كما في v3.1/v4.

موفّق.
