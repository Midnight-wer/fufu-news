/**
 * IndexedDB 本地缓存层 — 新闻数据持久化
 *
 * 功能:
 * - CRUD 操作（按分类/时间查询）
 * - TTL 7 天自动过期
 * - 上限 1000 条，超出按时间从旧到新清理
 */
export interface ArticleCache {
  id?: number;
  title: string;
  summary: string;
  source: string;
  sourceId: number;
  category: string;
  url: string;
  publishedAt: string;
  cachedAt: number;
}

interface CacheQuery {
  category?: string;
  since?: number;
  limit?: number;
  offset?: number;
}

const DB_NAME = 'fufu-cache';
const DB_VERSION = 1;
const STORE = 'articles';
const TTL_MS = 7 * 24 * 3600 * 1000;
const MAX_ITEMS = 1000;

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        const store = db.createObjectStore(STORE, { keyPath: 'url' });
        store.createIndex('category', 'category', { unique: false });
        store.createIndex('cachedAt', 'cachedAt', { unique: false });
        store.createIndex('publishedAt', 'publishedAt', { unique: false });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function purgeExpired(db: IDBDatabase): Promise<void> {
  const tx = db.transaction(STORE, 'readwrite');
  const store = tx.objectStore(STORE);
  const now = Date.now();
  const expired: string[] = [];

  await new Promise<void>((resolve) => {
    const cursorReq = store.openCursor();
    cursorReq.onsuccess = () => {
      const cursor = cursorReq.result;
      if (cursor) {
        if (now - cursor.value.cachedAt > TTL_MS) {
          expired.push(cursor.value.url);
        }
        cursor.continue();
      } else {
        resolve();
      }
    };
    cursorReq.onerror = () => resolve();
  });

  for (const url of expired) {
    store.delete(url);
  }

  // 上限 1000 条 → 删最旧的
  const count = await new Promise<number>((resolve) => {
    const r = store.count();
    r.onsuccess = () => resolve(r.result);
    r.onerror = () => resolve(0);
  });

  if (count > MAX_ITEMS) {
    const toDelete: string[] = [];
    await new Promise<void>((resolve) => {
      const idx = store.index('cachedAt');
      const cursorReq = idx.openCursor();
      cursorReq.onsuccess = () => {
        const cursor = cursorReq.result;
        if (cursor && toDelete.length < count - MAX_ITEMS) {
          toDelete.push(cursor.value.url);
          cursor.continue();
        } else {
          resolve();
        }
      };
      cursorReq.onerror = () => resolve();
    });
    for (const url of toDelete) {
      store.delete(url);
    }
  }
}

// ====== 公开 API ======

export async function cacheUpsert(articles: ArticleCache[]): Promise<void> {
  const db = await openDB();
  const tx = db.transaction(STORE, 'readwrite');
  const store = tx.objectStore(STORE);
  for (const a of articles) {
    if (!a.url) continue;
    store.put({ ...a, cachedAt: Date.now() });
  }
  await new Promise<void>((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  await purgeExpired(db);
  db.close();
}

export async function cacheGet(
  query: CacheQuery = {},
): Promise<ArticleCache[]> {
  const db = await openDB();
  const tx = db.transaction(STORE, 'readonly');
  const store = tx.objectStore(STORE);
  const results: ArticleCache[] = [];

  await new Promise<void>((resolve) => {
    const idx = query.category
      ? store.index('category')
      : store.index('publishedAt');
    const range = query.category
      ? IDBKeyRange.only(query.category)
      : undefined;

    const cursorReq = idx.openCursor(range, query.category ? 'next' : 'prev');
    let skipped = 0;
    const offset = query.offset || 0;
    const limit = query.limit || 50;
    const since = query.since || 0;

    cursorReq.onsuccess = () => {
      const cursor = cursorReq.result;
      if (!cursor || results.length >= limit) {
        resolve();
        return;
      }
      const item = cursor.value;
      if (item.publishedAt) {
        const ts = new Date(item.publishedAt).getTime();
        if (since && ts < since) {
          cursor.continue();
          return;
        }
      }
      if (skipped < offset) {
        skipped++;
        cursor.continue();
        return;
      }
      results.push(item);
      cursor.continue();
    };
    cursorReq.onerror = () => resolve();
  });

  db.close();
  return results;
}

export async function cacheCount(): Promise<number> {
  const db = await openDB();
  const tx = db.transaction(STORE, 'readonly');
  const store = tx.objectStore(STORE);
  const count = await new Promise<number>((resolve) => {
    const r = store.count();
    r.onsuccess = () => resolve(r.result);
    r.onerror = () => resolve(0);
  });
  db.close();
  return count;
}

export async function cacheDelete(urls: string[]): Promise<void> {
  const db = await openDB();
  const tx = db.transaction(STORE, 'readwrite');
  const store = tx.objectStore(STORE);
  for (const url of urls) store.delete(url);
  await new Promise<void>((resolve) => { tx.oncomplete = () => resolve(); });
  db.close();
}

export async function cacheClear(): Promise<void> {
  const db = await openDB();
  const tx = db.transaction(STORE, 'readwrite');
  tx.objectStore(STORE).clear();
  await new Promise<void>((resolve) => { tx.oncomplete = () => resolve(); });
  db.close();
}

/** 自检：读写测试一条临时数据 */
export async function cacheSelfCheck(): Promise<boolean> {
  try {
    const db = await openDB();
    const tx = db.transaction(STORE, 'readwrite');
    const store = tx.objectStore(STORE);
    const testItem = {
      url: '__self_check__',
      title: 'test',
      summary: '',
      source: '',
      sourceId: 0,
      category: '',
      publishedAt: new Date().toISOString(),
      cachedAt: Date.now(),
    };
    store.put(testItem);
    await new Promise<void>((r) => { tx.oncomplete = () => r(); });
    const tx2 = db.transaction(STORE, 'readonly');
    const getReq = tx2.objectStore(STORE).get('__self_check__');
    const result = await new Promise<ArticleCache | undefined>((resolve) => {
      getReq.onsuccess = () => resolve(getReq.result);
      getReq.onerror = () => resolve(undefined);
    });
    const tx3 = db.transaction(STORE, 'readwrite');
    tx3.objectStore(STORE).delete('__self_check__');
    db.close();
    return result?.title === 'test';
  } catch {
    return false;
  }
}

/** 检查缓存数据完整性 */
export async function cacheIntegrityCheck(): Promise<{ total: number; corrupt: number }> {
  const db = await openDB();
  const tx = db.transaction(STORE, 'readonly');
  const store = tx.objectStore(STORE);
  let total = 0;
  let corrupt = 0;
  const requiredFields = ['title', 'url', 'publishedAt', 'cachedAt'];

  await new Promise<void>((resolve) => {
    const cursorReq = store.openCursor();
    cursorReq.onsuccess = () => {
      const cursor = cursorReq.result;
      if (!cursor) { resolve(); return; }
      total++;
      const item = cursor.value;
      for (const f of requiredFields) {
        if (!item[f]) { corrupt++; break; }
      }
      cursor.continue();
    };
    cursorReq.onerror = () => resolve();
  });

  db.close();
  return { total, corrupt };
}
