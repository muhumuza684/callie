self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
self.addEventListener("fetch", () => {}); // network-only for now; a fetch handler keeps the app installable
self.addEventListener("notificationclick", e => { e.notification.close(); e.waitUntil(self.clients.openWindow("/")); });
