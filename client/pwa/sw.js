// Keeps Callie installable and lets it open even when the server is asleep or offline.
// The app files and the last contact list are kept on the device; calls themselves always need the server.
const CACHE = "callie-v32";
const SHELL = ["/", "/app.js", "/style.css", "/worklet.js", "/manifest.json",
  "/icons/icon-192.png", "/icons/icon-512.png", "/icons/maskable-512.png", "/icons/apple-touch-icon.png"];
const KEEP_API = ["/api/state"];                       // the contact list, so the app is not empty while waiting
const WAIT_MS = 4000;                                  // a sleeping server can take a minute: show what we have meanwhile

self.addEventListener("install", e => {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then(c => Promise.all(SHELL.map(u => c.add(u).catch(() => {})))));
});
self.addEventListener("activate", e => e.waitUntil(
  caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())));

async function fresh(req, cache) {
  const res = await fetch(req);
  if (res.ok && !res.redirected) cache.put(req, res.clone());      // never keep a sign-in redirect or an error
  return res;
}

self.addEventListener("fetch", e => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin) return;
  const isShell = req.mode === "navigate" || SHELL.includes(url.pathname);
  if (!isShell && !KEEP_API.includes(url.pathname)) return;        // calls, pings, setup and sign-in always go to the network
  e.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const key = req.mode === "navigate" ? "/" : req;
    const net = fresh(req.mode === "navigate" ? "/" : req, cache);
    try {
      return await Promise.race([net, new Promise((_, no) => setTimeout(no, WAIT_MS))]);
    } catch (_) {
      const old = await cache.match(key);
      if (old) { net.catch(() => {}); return old; }               // slow or offline: show the saved copy
      return net;                                                 // nothing saved yet: wait for the server
    }
  })());
});

self.addEventListener("notificationclick", e => { e.notification.close(); e.waitUntil(self.clients.openWindow("/")); });
