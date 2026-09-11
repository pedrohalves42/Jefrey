/*
  Jefrey PWA Service Worker — CIPHER-206/209
  Estratégia: Cache First para app shell, Stale While Revalidate para APIs,
  Network First para web resources, Fallback offline para tudo o resto.
*/

const CACHE_NAME = "jefrey-pwa-v1";
const OFFLINE_URL = "/offline";

// App shell e assets estáticos que queremos cachear imediatamente
const PRECACHE_URLS = [
  "/",
  "/index.html",
  "/manifest.json",
  "/favicon.ico",
  "/assets/index-C3IVC57I.js",
  "/assets/vendor-bqwUVvIr.js",
  "/assets/ui-C3IVC57I.js",
  "/assets/charts-CHlcCXGD.js",
  "/assets/index-BjnhgmMz.js",
  "/assets/query-DXK-ByBE.js",
  "/assets/index-DFi9T4_N.css",
];

// Install — precache the app shell
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_URLS).then(() => {
        // Force the waiting service worker to become the active service worker
        return self.skipWaiting();
      });
    })
  );
});

// Activate — clean up old caches
self.addEventListener("activate", (event) => {
  const currentCaches = [CACHE_NAME];
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (currentCaches.indexOf(cacheName) === -1) {
            // Delete old cache
            return caches.delete(cacheName);
          }
        })
      );
    })
  );

  // Take control of the client immediately
  return self.clients.claim();
});

// Fetch — routing strategy
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Only handle same-origin requests for our API and assets
  if (url.origin !== self.location.origin) return;

  // Offline fallback routing
  if (url.pathname === "/offline") {
    event.respondWith(fetch(OFFLINE_URL));
    return;
  }

  // API routes — Network First with fallback to cache
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/mcp/")) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          // Clone the response and store in cache for later
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            // Don't cache error responses
            if (response.ok) {
              cache.put(event.request, responseClone);
            }
          });
          return response;
        })
        .catch(() => {
          // Fallback to cache if network fails
          return caches.match(event.request).then((cached) => {
            return cached || fetch(OFFLINE_URL);
          });
        })
    );
    return;
  }

  // App shell e assets — Cache First
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      if (cachedResponse) {
        return cachedResponse;
      }

      // Try network, then cache
      return fetch(event.request).then((networkResponse) => {
        // Don't cache non-200 responses or non-GET requests
        if (networkResponse.ok && event.request.method === "GET") {
          const responseClone = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseClone);
          });
        }
        return networkResponse;
      }).catch(() => {
        // Network failed — try cache
        return caches.match(event.request).then((cached) => {
          if (cached) return cached;
          // Last resort — offline page
          return caches.match("/offline");
        });
      });
    })
  );
});