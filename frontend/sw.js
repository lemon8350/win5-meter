const CACHE_NAME = 'win5-meter-v1';
const urlsToCache = [
    '/',
    '/index.html',
    '/style.css',
    '/app.js',
    '/manifest.json'
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
        .then(cache => {
            return cache.addAll(urlsToCache);
        })
    );
});

self.addEventListener('fetch', event => {
    // API呼び出しはキャッシュしない（ネットワーク優先）
    if (event.request.url.includes('/api/')) {
        event.respondWith(fetch(event.request));
        return;
    }
    
    // 静的ファイルはキャッシュ優先
    event.respondWith(
        caches.match(event.request)
        .then(response => {
            if (response) return response;
            return fetch(event.request);
        })
    );
});
