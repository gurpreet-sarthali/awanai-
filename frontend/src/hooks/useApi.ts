import { useEffect, useState } from 'react';

export function useApi<T>(loader: () => Promise<T>, dependencies: unknown[] = []) {
  const [data, setData] = useState<T | null>(null); const [loading, setLoading] = useState(true); const [error, setError] = useState('');
  useEffect(() => { let active = true; setLoading(true); setError(''); loader().then(value => { if (active) setData(value); }).catch(reason => { if (active) setError(reason instanceof Error ? reason.message : 'Unable to load data.'); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, dependencies);
  return { data, loading, error };
}
