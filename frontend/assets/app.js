// ===============================
// Config
// ===============================
const API_BASE = "https://ai-1-12fi.onrender.com"; // Render backend

// ===============================
// Send user prompt to backend
// ===============================
async function send() {
  const p = document.getElementById('prompt').value;
  if (!p.trim()) return;

  const outEl = document.getElementById('out');
  outEl.textContent = 'جارٍ الإرسال...';

  try {
    const r = await fetch(`${API_BASE}/api/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: p })
    });

    if (!r.ok) throw new Error(`HTTP error ${r.status}`);

    const j = await r.json();
    outEl.textContent = j.reply || JSON.stringify(j);
  } catch (err) {
    outEl.textContent = 'خطأ في الاتصال بالخادم';
    console.error(err);
  }
}

// ===============================
// Load catalog from backend
// ===============================
async function loadCatalog() {
  const el = document.getElementById('catalog');
  el.innerHTML = 'جارٍ التحميل...';

  try {
    const r = await fetch(`${API_BASE}/api/catalog`);
    if (!r.ok) throw new Error(`HTTP error ${r.status}`);

    const cats = await r.json();
    el.innerHTML = '';

    cats.forEach(c => {
      const d = document.createElement('div');
      d.className = 'card';
      d.innerHTML = `
        <strong>${c.name}</strong>
        <div class="badge">${c.key}</div>
        <p>${c.desc || ''}</p>
      `;
      el.appendChild(d);
    });
  } catch (err) {
    el.textContent = 'فشل تحميل الكتالوج';
    console.error(err);
  }
}

// ===============================
// Upload file to backend
// ===============================
async function upload() {
  const f = document.getElementById('fileup').files[0];
  if (!f) return;

  const uplog = document.getElementById('uplog');
  uplog.textContent = 'جارٍ الرفع...';

  const fd = new FormData();
  fd.append('file', f);

  try {
    const r = await fetch(`${API_BASE}/api/memory/upload`, { method: 'POST', body: fd });
    if (!r.ok) throw new Error(`HTTP error ${r.status}`);

    const j = await r.json();
    uplog.textContent = 'تم الرفع: ' + (j.stored_as || '');
  } catch (err) {
    uplog.textContent = 'فشل رفع الملف';
    console.error(err);
  }
}

// ===============================
// Initialize
// ===============================
loadCatalog();
