
self.addEventListener('install', e=>{e.waitUntil(caches.open('unified-v3').then(c=>c.addAll(['/','/index.html','/admin.html','/assets/app.js','/assets/admin.js','/manifest.json'])))});
self.addEventListener('fetch', e=>{e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request))) });
