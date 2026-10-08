import { useEffect, useState } from 'react';
import { listDatasets, type ManagedDatasetSummary } from '../services/datasetsApi';
import { DEFAULT_DATASET_ID } from '../hooks/useSelectedDataset';

type Props = {
  datasetId: string;
  onChange: (datasetId: string) => void;
};

export function DatasetSelector({ datasetId, onChange }: Props) {
  const [datasets, setDatasets] = useState<ManagedDatasetSummary[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    listDatasets()
      .then(items => setDatasets(items.filter(item => item.status !== 'DELETED')))
      .catch(reason => setError(reason instanceof Error ? reason.message : 'Could not load datasets.'));
  }, [datasetId]);

  return (
    <label className="dataset-selector">
      <span>Dataset</span>
      <select value={datasetId} onChange={event => onChange(event.target.value)}>
        {datasets.length === 0 && <option value={DEFAULT_DATASET_ID}>Demo Placement Dataset</option>}
        {datasets.map(item => (
          <option key={item.dataset_id} value={item.dataset_id}>
            {item.dataset_name}
            {item.is_builtin ? ' (demo)' : ''}
            {item.status !== 'READY' ? ` · ${item.status}` : ''}
          </option>
        ))}
      </select>
      {error && <small className="inline-error">{error}</small>}
    </label>
  );
}
