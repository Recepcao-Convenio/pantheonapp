// Pantheon na Mão — service worker
// Troque a versão quando publicar mudanças no app para os celulares atualizarem.
const VERSAO = 'pantheon-v13';
const BASE = ['./', 'index.html', 'manifest.webmanifest', 'icons/logo.png',
  'icons/icon-192.png', 'icons/icon-512.png', 'icons/apple-touch-icon.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(VERSAO).then(c => c.addAll(BASE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(ks => Promise.all(ks.filter(k => k !== VERSAO).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  // Firebase/Firestore: sempre rede, nunca cache
  if (/googleapis\.com\/(google\.firestore|identitytoolkit)|firestore\.googleapis|script\.google(usercontent)?\.com/.test(url.href)) return;
  // Dados e páginas: rede primeiro (para pegar a versão nova), cache se estiver offline
  const redePrimeiro = url.origin === location.origin &&
    (req.mode === 'navigate' || url.pathname.endsWith('data.enc.json') || url.pathname.endsWith('.html'));
  if (redePrimeiro) {
    e.respondWith(fetch(req, {cache:'no-store'}).then(r => {
      // guarda uma única cópia (sem o ?v=...) para uso offline
      const chave = url.pathname.endsWith('data.enc.json') ? new Request(url.origin + url.pathname) : req;
      const copia = r.clone(); caches.open(VERSAO).then(c => c.put(chave, copia)); return r;
    }).catch(() => caches.match(req, {ignoreSearch:true}).then(r => r || caches.match('index.html'))));
    return;
  }
  // Ícones, fontes, bibliotecas: cache primeiro
  e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(r => {
    if (r.ok && (url.origin === location.origin || /fonts\.(googleapis|gstatic)\.com|gstatic\.com\/firebasejs/.test(url.href))) {
      const copia = r.clone(); caches.open(VERSAO).then(c => c.put(req, copia));
    }
    return r;
  })));
});
