// Basic Service Worker to satisfy Android PWA installation requirements

self.addEventListener('install', (event) => {
    // Skip waiting to activate immediately
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    // Take control of all pages immediately
    event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
    // A simple pass-through fetch handler is required by Chrome for PWA installability
    event.respondWith(fetch(event.request).catch(() => {
        // Fallback for offline (optional)
        return new Response('Offline mode not supported');
    }));
});
