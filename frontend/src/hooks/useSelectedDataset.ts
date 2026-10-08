import { useCallback, useEffect, useState } from 'react';

const STORAGE_KEY = 'askmydata.selectedDatasetId';
export const DEFAULT_DATASET_ID = 'demo-placement';

export function useSelectedDataset() {
  const [datasetId, setDatasetIdState] = useState(() => localStorage.getItem(STORAGE_KEY) || DEFAULT_DATASET_ID);

  const setDatasetId = useCallback((value: string) => {
    setDatasetIdState(value);
    localStorage.setItem(STORAGE_KEY, value);
  }, []);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && stored !== datasetId) {
      setDatasetIdState(stored);
    }
  }, [datasetId]);

  return { datasetId, setDatasetId };
}
