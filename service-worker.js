// نسخه‌ی کش رو هر بار که فایل‌ها رو آپدیت می‌کنی (مخصوصاً database.js) عوض کن
// تا کاربرهایی که اپ رو نصب کردن نسخه‌ی جدید رو بگیرن.
var CACHE_NAME = "course-app-v1";
var APP_SHELL = [
  "./",
  "./index.html",
  "./manifest.json",
  "./database.js",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/icon-192-maskable.png",
  "./icons/icon-512-maskable.png"
];

self.addEventListener("install", function(event){
  event.waitUntil(
    caches.open(CACHE_NAME).then(function(cache){ return cache.addAll(APP_SHELL); })
      .then(function(){ return self.skipWaiting(); })
  );
});

self.addEventListener("activate", function(event){
  event.waitUntil(
    caches.keys().then(function(keys){
      return Promise.all(keys.filter(function(k){ return k !== CACHE_NAME; }).map(function(k){ return caches.delete(k); }));
    }).then(function(){ return self.clients.claim(); })
  );
});

self.addEventListener("fetch", function(event){
  var req = event.request;
  if(req.method !== "GET") return;

  // database.js: اول از شبکه بگیر (تا دیتای تازه باشه)، اگه نبود از کش برگردون
  if(req.url.indexOf("database.js") > -1){
    event.respondWith(
      fetch(req).then(function(res){
        var copy = res.clone();
        caches.open(CACHE_NAME).then(function(cache){ cache.put(req, copy); });
        return res;
      }).catch(function(){ return caches.match(req); })
    );
    return;
  }

  // بقیه فایل‌ها: اول کش، بعد شبکه (cache-first برای سرعت و کارکرد آفلاین)
  event.respondWith(
    caches.match(req).then(function(cached){
      return cached || fetch(req).then(function(res){
        var copy = res.clone();
        caches.open(CACHE_NAME).then(function(cache){ cache.put(req, copy); });
        return res;
      });
    }).catch(function(){ return caches.match("./index.html"); })
  );
});
