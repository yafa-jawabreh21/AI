
async function send(){
  const p = document.getElementById('prompt').value;
  const r = await fetch('/api/ask',{method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text:p})});
  const j = await r.json(); document.getElementById('out').textContent = j.reply || JSON.stringify(j);
}
async function loadCatalog(){
  const r = await fetch('/api/catalog'); const cats = await r.json(); const el = document.getElementById('catalog'); el.innerHTML='';
  cats.forEach(c=>{ const d=document.createElement('div'); d.className='card'; d.innerHTML=`<strong>${c.name}</strong><div class="badge">${c.key}</div><p>${c.desc||''}</p>`; el.appendChild(d); });
}
async function upload(){
  const f = document.getElementById('fileup').files[0]; if(!f) return;
  const fd = new FormData(); fd.append('file', f);
  const r = await fetch('/api/memory/upload', {method:'POST', body: fd}); const j = await r.json();
  document.getElementById('uplog').textContent = 'تم الرفع: ' + (j.stored_as||'');
}
loadCatalog();
