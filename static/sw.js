/* Offline shell: cache core pages, queue draft reports in localStorage (see form draft autosave). */
self.addEventListener("install", (e) => { self.skipWaiting(); });
self.addEventListener("fetch", (e) => { /* network-first passthrough for MVP */ });
