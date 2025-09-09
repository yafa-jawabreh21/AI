// ===============================
// Admin Functions — Updated Backend
// ===============================

const API_BASE = "https://ai-2-wfa2.onrender.com"; // your Render backend

// -------------------------------
// Change admin password
// -------------------------------
async function changePwd() {
  const pwd = document.getElementById('pwd').value;
  const newpwd = document.getElementById('newpwd').value;

  try {
    const r = await fetch(`${API_BASE}/api/admin/update`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: pwd, new_password: newpwd })
    });

    const j = await r.json();
    alert(j.ok ? 'تم' : 'فشل');
  } catch (err) {
    console.error(err);
    alert('حدث خطأ في الاتصال بالخادم');
  }
}

// -------------------------------
// Update AI configuration
// -------------------------------
async function setAI() {
  const pwd = document.getElementById('pwd').value;
  const mode = document.getElementById('mode').value;
  const endpoint = document.getElementById('endpoint').value;
  const apikey = document.getElementById('apikey').value;

  try {
    const r = await fetch(`${API_BASE}/api/admin/update`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        password: pwd,
        llm_mode: mode,
        llm_endpoint: endpoint,
        llm_api_key: apikey
      })
    });

    const j = await r.json();
    alert(j.ok ? 'تم' : 'فشل');
  } catch (err) {
    console.error(err);
    alert('حدث خطأ في الاتصال بالخادم');
  }
}

// -------------------------------
// Add a service to catalog
// -------------------------------
async function addService() {
  const pwd = document.getElementById('pwd').value;
  const key = document.getElementById('key').value;
  const name = document.getElementById('name').value;
  const desc = document.getElementById('desc').value;

  const fd = new FormData();
  fd.append('password', pwd);
  fd.append('key', key);
  fd.append('name', name);
  fd.append('desc', desc);

  try {
    const r = await fetch(`${API_BASE}/api/catalog/add`, { method: 'POST', body: fd });
    const j = await r.json();
    alert(j.ok ? 'أُضيف' : 'موجود/فشل');
    location.reload();
  } catch (err) {
    console.error(err);
    alert('حدث خطأ في الاتصال بالخادم');
  }
}

// -------------------------------
// Remove a service from catalog
// -------------------------------
async function removeService() {
  const pwd = document.getElementById('pwd').value;
  const key = document.getElementById('rmkey').value;

  const fd = new FormData();
  fd.append('password', pwd);
  fd.append('key', key);

  try {
    const r = await fetch(`${API_BASE}/api/catalog/remove`, { method: 'POST', body: fd });
    const j = await r.json();
    alert(j.ok ? 'حُذف' : 'فشل');
    location.reload();
  } catch (err) {
    console.error(err);
    alert('حدث خطأ في الاتصال بالخادم');
  }
}
