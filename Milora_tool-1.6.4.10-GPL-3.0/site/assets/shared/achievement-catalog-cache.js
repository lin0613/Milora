(function () {
 'use strict';
 const DATABASE = 'achievement-hub-catalog-cache-v1';
 const STORE = 'catalogs';
 const LEGACY_KEYS = {
  wuwa: ['鳴潮正式成就資料_官方ID_v19', '鳴潮正式成就同步資訊_官方ID_v19'],
  hsr: ['崩鐵成就資料_v2_官方順序', '崩鐵成就同步資訊_v2_官方順序'],
  genshin: ['原神成就資料_v1_官方順序', '原神成就同步資訊_v1_官方順序'],
  zzz: ['絕區零成就資料_v1_官方順序', '絕區零成就同步資訊_v1_官方順序'],
  nte: ['異環成就資料_v1_官方順序', '異環成就同步資訊_v1_官方順序']
 };
 let connection = null;
 let queue = Promise.resolve();
 let warned = false;
 const validItems = items => Array.isArray(items) && items.every(item => item && typeof item === 'object' && !Array.isArray(item));
 function warn() {
  if (!warned) console.warn('Achievement catalog cache unavailable; live catalog rendering is unaffected.');
  warned = true;
 }
 function legacy(game) {
  if (!Object.hasOwn(LEGACY_KEYS, game)) return null;
  try {
   const [dataKey, metaKey] = LEGACY_KEYS[game];
   const raw = localStorage.getItem(dataKey);
   if (raw === null) return null;
   const items = JSON.parse(raw);
   if (!validItems(items)) return null;
   const rawMeta = localStorage.getItem(metaKey);
   let meta = {};
   try { meta = JSON.parse(rawMeta || '{}'); } catch {}
   return {game, items, meta, raw, rawMeta};
  } catch { return null; }
 }
 function openDatabase() {
  if (connection) return connection;
  connection = new Promise(resolve => {
   let settled = false;
   let timer;
   const finish = db => { if (!settled) { settled = true; clearTimeout(timer); resolve(db); } };
   try {
    const request = indexedDB.open(DATABASE, 1);
    timer = setTimeout(() => finish(null), 2000);
    request.onupgradeneeded = () => {
     if (!request.result.objectStoreNames.contains(STORE)) request.result.createObjectStore(STORE, {keyPath: 'game'});
    };
    request.onsuccess = () => {
     const db = request.result;
     if (settled) { db.close(); return; }
     db.onversionchange = () => { db.close(); connection = null; };
     finish(db);
    };
    request.onerror = request.onblocked = () => finish(null);
   } catch { finish(null); }
  });
  return connection;
 }
 function transaction(db, mode, action) {
  return new Promise(resolve => {
   let tx;
   let timer;
   let result = null;
   let settled = false;
   const finish = ok => { if (!settled) { settled = true; clearTimeout(timer); resolve({ok, value: result}); } };
   try {
    tx = db.transaction(STORE, mode);
    tx.oncomplete = () => finish(true);
    tx.onabort = tx.onerror = () => finish(false);
    timer = setTimeout(() => { try { tx.abort(); } catch {} finish(false); }, 3000);
    action(tx.objectStore(STORE), value => { result = value; });
   } catch { try { tx?.abort(); } catch {} finish(false); }
  });
 }
 function removeLegacy(record) {
  // Delete only the exact cache snapshots successfully committed, never progress or preferences.
  try {
   const [dataKey, metaKey] = LEGACY_KEYS[record.game];
   if (localStorage.getItem(dataKey) === record.raw) {
    localStorage.removeItem(dataKey);
    if (localStorage.getItem(metaKey) === record.rawMeta) localStorage.removeItem(metaKey);
   }
  } catch {}
 }
 async function migrateLegacy(db) {
  const records = Object.keys(LEGACY_KEYS).map(legacy).filter(Boolean);
  if (!records.length) return;
  const outcome = await transaction(db, 'readwrite', store => {
   for (const record of records) {
    // A previously committed IndexedDB catalog is preferred over an old tab's local cache.
    const request = store.get(record.game);
    request.onsuccess = () => {
     if (!validItems(request.result?.items) || request.result?.format !== 1) {
      store.put({game: record.game, items: record.items, meta: record.meta, format: 1});
     }
    };
   }
  });
  if (outcome.ok) records.forEach(removeLegacy);
  else warn();
 }
 function enqueue(action) {
  const result = queue.then(action).catch(() => { warn(); return null; });
  queue = result.then(() => undefined);
  return result;
 }
 window.AchievementCatalogCache = Object.freeze({
  readLegacy(game) { return legacy(game)?.items || []; },
  load(game) {
   if (!Object.hasOwn(LEGACY_KEYS, game)) return Promise.resolve([]);
   return enqueue(async () => {
    const db = await openDatabase();
    if (!db) { warn(); return legacy(game)?.items || []; }
    // Migrate all five large keys together to free their shared localStorage budget.
    await migrateLegacy(db);
    const outcome = await transaction(db, 'readonly', (store, receive) => {
     const request = store.get(game);
     request.onsuccess = () => receive(request.result);
    });
    if (!outcome.ok) warn();
    const record = outcome.value;
    return outcome.ok && record?.format === 1 && record.game === game && validItems(record.items) ? record.items : (legacy(game)?.items || []);
   });
  },
  save(game, items, meta = {}) {
   if (!Object.hasOwn(LEGACY_KEYS, game) || !validItems(items)) return Promise.resolve(false);
   const old = legacy(game);
   return enqueue(async () => {
    const db = await openDatabase();
    if (!db) { warn(); return false; }
    const outcome = await transaction(db, 'readwrite', store => store.put({game, items, meta, format: 1}));
    if (outcome.ok && old) removeLegacy(old);
    if (!outcome.ok) warn();
    return outcome.ok;
   });
  }
 });
})();
