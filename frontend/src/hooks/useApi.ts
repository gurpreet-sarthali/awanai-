import { useEffect, useState } from 'react';

// Lightweight in-memory cache across tab switches so views don't blink/reload
const apiCache = new Map<string, unknown>();

/**
 * Clear the API cache (e.g. after uploading or deleting a dataset).
 */
export function clearApiCache(prefix?: string) {
  if (!prefix) {
    apiCache.clear();
    return;
  }
  for (const key of apiCache.keys()) {
    if (key.includes(prefix)) {
      apiCache.delete(key);
    }
  }
}

export function useApi<T>(loader: () => Promise<T>, dependencies: unknown[] = []) {
  const cacheKey = dependencies.length > 0 ? JSON.stringify(dependencies) : '';
  const cachedValue = cacheKey ? (apiCache.get(cacheKey) as T | undefined) : undefined;

  const [data, setData] = useState<T | null>(() => (cachedValue !== undefined ? cachedValue : null));
  const [loading, setLoading] = useState(() => cachedValue === undefined);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    const hasCache = cacheKey ? apiCache.has(cacheKey) : false;
    if (!hasCache) {
      setLoading(true);
    }
    setError('');

    loader()
      .then(value => {
        if (cacheKey) {
          apiCache.set(cacheKey, value);
        }
        if (active) {
          setData(value);
          setLoading(false);
        }
      })
      .catch(reason => {
        if (active) {
          setError(reason instanceof Error ? reason.message : 'Unable to load data.');
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, dependencies);

  return { data, loading, error };
}
