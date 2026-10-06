/* 개구리 점프 — 서비스 워커
 * - 핵심 파일은 설치 시 미리 캐시(precache) → 오프라인 실행
 * - 페이지(index.html): 네트워크 우선(3초 제한) → 실패하면 캐시 (업데이트가 바로 반영됨)
 * - 그 외 같은 출처 파일(assets/ 스프라이트 등): 캐시 먼저 보여주고 뒤에서 갱신(stale-while-revalidate)
 * 새 버전을 배포할 때는 아래 VERSION 값을 올리세요. */
const VERSION = 'v1.0.0';
const CACHE = 'frog-jump-' + VERSION;
const PRECACHE = [
  './',
  './index.html',
  './manifest.webmanifest',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/icon-maskable-512.png',
  './icons/apple-touch-icon.png',
  './icons/favicon-32.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k.startsWith('frog-jump-') && k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

function timeout(ms) {
  return new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), ms));
}

async function pageRequest(request) {
  const cache = await caches.open(CACHE);
  try {
    const res = await Promise.race([fetch(request), timeout(3000)]);
    if (res && res.ok) cache.put('./index.html', res.clone()); // ?seed= 같은 쿼리와 무관하게 한 벌만 보관
    return res;
  } catch (err) {
    return (await cache.match('./index.html')) || (await cache.match('./')) || Response.error();
  }
}

async function assetRequest(event) {
  const cache = await caches.open(CACHE);
  const cached = await cache.match(event.request);
  const network = fetch(event.request)
    .then((res) => {
      if (res && res.ok) cache.put(event.request, res.clone());
      return res;
    })
    .catch(() => null);
  if (cached) {
    event.waitUntil(network);
    return cached;
  }
  return (await network) || Response.error();
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (req.mode === 'navigate') {
    event.respondWith(pageRequest(req));
  } else {
    event.respondWith(assetRequest(event));
  }
});
