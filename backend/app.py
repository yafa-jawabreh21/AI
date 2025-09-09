
import os, json, datetime, hashlib, re, time
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(BASE, ".."))
FRONT = os.path.join(ROOT, "frontend")
DATA = os.path.join(BASE, "data")
os.makedirs(DATA, exist_ok=True)

SETTINGS = os.path.join(BASE, "settings.json")
CATALOG = os.path.join(BASE, "catalog.json")
MEMORY = os.path.join(DATA, "memory.jsonl")

# Initialize defaults
if not os.path.exists(SETTINGS):
    with open(SETTINGS, "w", encoding="utf-8") as f:
        json.dump({"admin_password":"1234","title":"Future Crown Ultimate — Unified v3",
                   "llm_mode":"local_stub","llm_endpoint":"","llm_api_key":""}, f, ensure_ascii=False, indent=2)
if not os.path.exists(CATALOG):
    with open(CATALOG, "w", encoding="utf-8") as f:
        json.dump([
            {"key":"evm","name":"EVM Analyzer","desc":"حساب SPI/CPI/EAC (stub)"},
            {"key":"ifrs15","name":"IFRS‑15 Engine","desc":"جدول الاعتراف الشهري CSV (stub)"},
            {"key":"procure","name":"Procurement Trigger","desc":"تنبيه سابق 15 يوم (☠️)"},
            {"key":"reports","name":"Report Builder","desc":"HTML/PDF لاحقًا"},
            {"key":"ai","name":"AI Orchestrator","desc":"مساعد نص/صوت/كاميرا + أدوات"},
        ], f, ensure_ascii=False, indent=2)

def load(p): 
    with open(p,"r",encoding="utf-8") as f: return json.load(f)
def save(p, d):
    with open(p,"w",encoding="utf-8") as f: json.dump(d,f,ensure_ascii=False,indent=2)

app = FastAPI(title="Future Crown Ultimate — Unified v3", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.mount("/", StaticFiles(directory=FRONT, html=True), name="static")

# ===== Models =====
class AskPayload(BaseModel):
    text: str
    use_voice: Optional[bool] = False

class AdminUpdate(BaseModel):
    password: str
    new_password: Optional[str] = None
    llm_mode: Optional[str] = None
    llm_endpoint: Optional[str] = None
    llm_api_key: Optional[str] = None

# ===== Endpoints =====
@app.get("/api/healthz")
def healthz():
    return {"ok":True,"time":datetime.datetime.utcnow().isoformat()+"Z"}

@app.get("/api/catalog")
def catalog_list():
    return load(CATALOG)

@app.post("/api/catalog/add")
def catalog_add(password: str = Form(...), key: str = Form(...), name: str = Form(...), desc: str = Form("")):
    st = load(SETTINGS)
    if password != st.get("admin_password"): raise HTTPException(401, "bad password")
    cats = load(CATALOG)
    if any(c.get("key")==key for c in cats): return {"ok": False, "reason":"exists"}
    cats.append({"key":key,"name":name,"desc":desc})
    save(CATALOG, cats)
    return {"ok": True}

@app.post("/api/catalog/remove")
def catalog_remove(password: str = Form(...), key: str = Form(...)):
    st = load(SETTINGS)
    if password != st.get("admin_password"): raise HTTPException(401, "bad password")
    cats = [c for c in load(CATALOG) if c.get("key")!=key]
    save(CATALOG, cats)
    return {"ok": True}

@app.post("/api/admin/update")
def admin_update(payload: AdminUpdate):
    st = load(SETTINGS)
    if payload.password != st.get("admin_password"): raise HTTPException(401, "bad password")
    changed = False
    for k in ["llm_mode","llm_endpoint","llm_api_key"]:
        v = getattr(payload, k)
        if v is not None: st[k]=v; changed=True
    if payload.new_password:
        st["admin_password"]=payload.new_password; changed=True
    if changed: save(SETTINGS, st)
    return {"ok": True, "changed": changed}

@app.post("/api/ask")
def ask(payload: AskPayload):
    text = payload.text.strip()
    ts = datetime.datetime.utcnow().isoformat()+"Z"
    with open(MEMORY, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts":ts,"type":"ask","text":text}, ensure_ascii=False)+"\n")
    t = text.lower()
    if "evm" in t:
        reply = "EVM: SPI/CPI/EAC متاحين عبر الأدوات أو إدخال بياناتك لاحقًا."
    elif "ifrs" in t:
        reply = "IFRS‑15: توليد جدول اعتراف مبسّط ضمن الأدوات."
    elif "procure" in t or "شراء" in t:
        reply = "Procurement: إنذار 15 يوم (☠️) — اضبطه من الإدارة."
    else:
        reply = "Future Unified: الأمر سُجّل وسيُوجَّه للأدوات/الموصلات عند تفعيلها."
    return {"ok": True, "reply": reply, "ts": ts}

@app.post("/api/memory/upload")
async def memory_upload(file: UploadFile = File(...)):
    content = await file.read()
    h = hashlib.sha256(content).hexdigest()[:16]
    path = os.path.join(DATA, f"up_{h}_{file.filename}")
    with open(path, "wb") as f: f.write(content)
    return {"ok": True, "stored_as": os.path.basename(path)}

@app.get("/api/memory/logs")
def memory_logs(limit: int = 100):
    items = []
    if os.path.exists(MEMORY):
        with open(MEMORY,"r",encoding="utf-8") as f:
            items = [json.loads(l) for l in f.readlines()[-limit:]]
    return {"ok": True, "items": items}

# ===== Basic Tools (merged) =====
@app.post("/api/tools/run_evm")
def run_evm(boq_total: float=0.0, ev: float=0.0, ac: float=0.0, pv: float=0.0):
    spi = (ev/pv) if pv else None
    cpi = (ev/ac) if ac else None
    return {"ok": True, "SPI": spi, "CPI": cpi}

@app.post("/api/tools/run_ifrs15")
def run_ifrs15(contract_value: float, months: int):
    per = contract_value/months if months>0 else 0
    schedule = [{"month":i+1,"recognition":per} for i in range(months)]
    return {"ok": True, "schedule": schedule}

@app.post("/api/tools/report_build")
def report_build(title: str, items: str):
    html = "<h1>"+title+"</h1><ul>" + "".join(f"<li>{x}</li>" for x in items.split("|")) + "</ul>"
    fname = re.sub(r"[^a-zA-Z0-9_-]+","_",title) or "report"
    out = os.path.join(DATA, f"{fname}_{int(time.time())}.html")
    with open(out,"w",encoding="utf-8") as f: f.write(html)
    return {"ok": True, "html": os.path.basename(out)}
