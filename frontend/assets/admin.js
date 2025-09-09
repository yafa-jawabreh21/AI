
async function changePwd(){
  const pwd = document.getElementById('pwd').value;
  const newpwd = document.getElementById('newpwd').value;
  const r = await fetch('/api/admin/update',{method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({password:pwd, new_password:newpwd})});
  const j = await r.json(); alert(j.ok?'تم':'فشل');
}
async function setAI(){
  const pwd = document.getElementById('pwd').value;
  const mode = document.getElementById('mode').value;
  const endpoint = document.getElementById('endpoint').value;
  const apikey = document.getElementById('apikey').value;
  const r = await fetch('/api/admin/update',{method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({password:pwd, llm_mode:mode, llm_endpoint:endpoint, llm_api_key:apikey})});
  const j = await r.json(); alert(j.ok?'تم':'فشل');
}
async function addService(){
  const pwd = document.getElementById('pwd').value;
  const key = document.getElementById('key').value;
  const name = document.getElementById('name').value;
  const desc = document.getElementById('desc').value;
  const fd = new FormData(); fd.append('password', pwd); fd.append('key', key); fd.append('name', name); fd.append('desc', desc);
  const r = await fetch('/api/catalog/add',{method:'POST', body: fd}); const j = await r.json(); alert(j.ok?'أُضيف':'موجود/فشل'); location.reload();
}
async function removeService(){
  const pwd = document.getElementById('pwd').value;
  const key = document.getElementById('rmkey').value;
  const fd = new FormData(); fd.append('password', pwd); fd.append('key', key);
  const r = await fetch('/api/catalog/remove',{method:'POST', body: fd}); const j = await r.json(); alert(j.ok?'حُذف':'فشل'); location.reload();
}
