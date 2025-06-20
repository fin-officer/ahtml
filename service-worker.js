const CACHE_NAME = 'mcp-client-v1';
const CACHE_FILES = [
    '/',
    '/mcp/index.html',
    '/mcp/styles.css',
    '/mcp/app.js'
];

self.addEventListener('install', event => {
    console.log('Service Worker zainstalowany');
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(CACHE_FILES))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', event => {
    console.log('Service Worker aktywowany');
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.filter(cacheName => {
                    return cacheName.startsWith('mcp-client-') && cacheName !== CACHE_NAME;
                }).map(cacheName => {
                    return caches.delete(cacheName);
                })
            );
        })
    );
    self.clients.claim();
});

self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request)
            .then(response => {
                if (response) {
                    return response;
                }
                return fetch(event.request)
                    .then(response => {
                        if (!response || response.status !== 200 || response.type !== 'basic') {
                            return response;
                        }
                        const responseToCache = response.clone();
                        caches.open(CACHE_NAME)
                            .then(cache => {
                                cache.put(event.request, responseToCache);
                            });
                        return response;
                    });
            })
    );
});

// Obsługa żądań MCP
self.addEventListener('message', event => {
    if (event.data.type === 'MCP_REQUEST') {
        console.log('Otrzymano żądanie MCP:', event.data);
        const { method, params } = event.data;
        
        // Tu można dodać logikę obsługi żądań MCP w tle
        switch (method) {
            case 'initialize':
                // Obsługa inicjalizacji
                break;
            case 'getServices':
                // Obsługa pobierania usług
                break;
            case 'sendMessage':
                // Obsługa wysyłania wiadomości
                break;
        }
    }
});

// Obsługa synchronizacji w tle
self.addEventListener('sync', event => {
    if (event.tag === 'sync-messages') {
        console.log('Synchronizacja wiadomości w tle');
        // Tu można dodać logikę synchronizacji wiadomości
    }
});
