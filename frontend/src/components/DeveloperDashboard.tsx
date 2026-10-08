import { useCallback, useEffect, useState } from 'react';
import {
  API_SCOPES,
  WEBHOOK_EVENTS,
  createApiKey,
  createWebhook,
  deleteWebhook,
  getDeveloperUsage,
  listApiKeys,
  listWebhookDeliveries,
  listWebhooks,
  revokeApiKey,
  rotateApiKey,
  rotateWebhookSecret,
  testWebhook,
  updateWebhook,
  type ApiKey,
  type ApiKeyCreateResult,
  type UsageSummary,
  type WebhookCreateResult,
  type WebhookDelivery,
  type WebhookEndpoint,
} from '../services/developerApi';

/* ═══════════════════════════════════════════════════════════════════════════
   Developer Dashboard — API Keys, Webhooks & Usage
   ═══════════════════════════════════════════════════════════════════════════ */

interface Props {
  workspaceId: string;
}

type Tab = 'keys' | 'webhooks' | 'usage' | 'docs';

export function DeveloperDashboard({ workspaceId }: Props) {
  const [tab, setTab] = useState<Tab>('keys');

  return (
    <div className="dev-dashboard">
      <div className="dev-dashboard-header">
        <h2>Developer Settings</h2>
        <p className="dev-subtitle">Manage API keys, webhooks, and monitor API usage for your workspace.</p>
      </div>

      <div className="dev-tabs">
        {([['keys', '🔑 API Keys'], ['webhooks', '🔔 Webhooks'], ['usage', '📊 Usage'], ['docs', '📖 Documentation']] as const).map(([key, label]) => (
          <button key={key} className={`dev-tab${tab === key ? ' dev-tab-active' : ''}`} onClick={() => setTab(key)}>{label}</button>
        ))}
      </div>

      <div className="dev-tab-content">
        {tab === 'keys' && <ApiKeysPanel workspaceId={workspaceId} />}
        {tab === 'webhooks' && <WebhooksPanel workspaceId={workspaceId} />}
        {tab === 'usage' && <UsagePanel workspaceId={workspaceId} />}
        {tab === 'docs' && <DocsPanel />}
      </div>
    </div>
  );
}

/* ─── API Keys Panel ───────────────────────────────────────────────────────── */

function ApiKeysPanel({ workspaceId }: { workspaceId: string }) {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const [newKeyResult, setNewKeyResult] = useState<ApiKeyCreateResult | null>(null);
  const [copied, setCopied] = useState(false);

  // Create form
  const [keyName, setKeyName] = useState('');
  const [selectedScopes, setSelectedScopes] = useState<string[]>([]);
  const [expiresIn, setExpiresIn] = useState('');

  const loadKeys = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      setKeys(await listApiKeys(workspaceId));
    } catch (e: any) {
      setError(e.message || 'Failed to load API keys');
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => { loadKeys(); }, [loadKeys]);

  const handleCreate = async () => {
    if (!keyName.trim() || selectedScopes.length === 0) return;
    try {
      setError('');
      let expiresAt: string | undefined;
      if (expiresIn) {
        const days = parseInt(expiresIn, 10);
        if (days > 0) {
          const d = new Date();
          d.setDate(d.getDate() + days);
          expiresAt = d.toISOString();
        }
      }
      const result = await createApiKey(workspaceId, keyName.trim(), selectedScopes, expiresAt);
      setNewKeyResult(result);
      setCopied(false);
      setKeyName('');
      setSelectedScopes([]);
      setExpiresIn('');
      setCreating(false);
      loadKeys();
    } catch (e: any) {
      setError(e.message || 'Failed to create API key');
    }
  };

  const handleRevoke = async (keyId: string) => {
    if (!confirm('Revoke this API key? It will stop working immediately.')) return;
    try {
      await revokeApiKey(workspaceId, keyId);
      loadKeys();
    } catch (e: any) {
      setError(e.message || 'Failed to revoke key');
    }
  };

  const handleRotate = async (keyId: string) => {
    const grace = prompt('Grace period in seconds for the old key (0 for immediate, max 86400):', '3600');
    if (grace === null) return;
    try {
      const result = await rotateApiKey(workspaceId, keyId, parseInt(grace, 10) || 0);
      setNewKeyResult(result);
      setCopied(false);
      loadKeys();
    } catch (e: any) {
      setError(e.message || 'Failed to rotate key');
    }
  };

  const copyKey = (key: string) => {
    navigator.clipboard.writeText(key);
    setCopied(true);
    setTimeout(() => setCopied(false), 3000);
  };

  const toggleScope = (scope: string) => {
    setSelectedScopes(prev => prev.includes(scope) ? prev.filter(s => s !== scope) : [...prev, scope]);
  };

  const activeKeys = keys.filter(k => !k.revoked_at);
  const revokedKeys = keys.filter(k => k.revoked_at);

  return (
    <div className="dev-panel">
      {/* New key reveal */}
      {newKeyResult && (
        <div className="dev-key-reveal">
          <div className="dev-key-reveal-header">
            <span className="dev-key-reveal-icon">🔑</span>
            <strong>New API Key Created</strong>
          </div>
          <p className="dev-key-reveal-warning">Copy this key now — it cannot be retrieved again.</p>
          <div className="dev-key-reveal-value">
            <code>{newKeyResult.api_key}</code>
            <button className="dev-btn dev-btn-sm" onClick={() => copyKey(newKeyResult.api_key)}>
              {copied ? '✓ Copied' : '📋 Copy'}
            </button>
          </div>
          <button className="dev-btn dev-btn-ghost" onClick={() => setNewKeyResult(null)}>Dismiss</button>
        </div>
      )}

      {error && <div className="dev-error">{error}</div>}

      <div className="dev-panel-header">
        <h3>API Keys {activeKeys.length > 0 && <span className="dev-badge">{activeKeys.length}</span>}</h3>
        <button className="dev-btn dev-btn-primary" onClick={() => setCreating(c => !c)}>
          {creating ? '✕ Cancel' : '+ Create Key'}
        </button>
      </div>

      {creating && (
        <div className="dev-create-form">
          <div className="dev-form-group">
            <label>Key Name</label>
            <input type="text" value={keyName} onChange={e => setKeyName(e.target.value)} placeholder="e.g. Production Integration" maxLength={128} className="dev-input" />
          </div>
          <div className="dev-form-group">
            <label>Expiration (days from now, leave empty for no expiration)</label>
            <input type="number" value={expiresIn} onChange={e => setExpiresIn(e.target.value)} placeholder="e.g. 90" min={1} max={3650} className="dev-input dev-input-sm" />
          </div>
          <div className="dev-form-group">
            <label>Scopes</label>
            <div className="dev-scope-grid">
              {API_SCOPES.map(scope => (
                <label key={scope.value} className={`dev-scope-item${selectedScopes.includes(scope.value) ? ' dev-scope-selected' : ''}`}>
                  <input type="checkbox" checked={selectedScopes.includes(scope.value)} onChange={() => toggleScope(scope.value)} />
                  <div>
                    <span className="dev-scope-name">{scope.label}</span>
                    <span className="dev-scope-desc">{scope.description}</span>
                  </div>
                </label>
              ))}
            </div>
          </div>
          <button className="dev-btn dev-btn-primary" onClick={handleCreate} disabled={!keyName.trim() || selectedScopes.length === 0}>
            Create API Key
          </button>
        </div>
      )}

      {loading ? (
        <div className="dev-loading">Loading API keys...</div>
      ) : (
        <>
          {activeKeys.length === 0 && !creating && (
            <div className="dev-empty">No active API keys. Create one to get started.</div>
          )}
          {activeKeys.map(key => (
            <div key={key.id} className="dev-key-card">
              <div className="dev-key-info">
                <strong>{key.name}</strong>
                <code className="dev-key-prefix">{key.key_prefix}...</code>
                <div className="dev-key-scopes">
                  {key.scopes.map(s => <span key={s} className="dev-scope-badge">{s}</span>)}
                </div>
                <div className="dev-key-meta">
                  Created {new Date(key.created_at).toLocaleDateString()}
                  {key.expires_at && <> · Expires {new Date(key.expires_at).toLocaleDateString()}</>}
                  {key.last_used_at && <> · Last used {new Date(key.last_used_at).toLocaleDateString()}</>}
                </div>
              </div>
              <div className="dev-key-actions">
                <button className="dev-btn dev-btn-sm" onClick={() => handleRotate(key.id)} title="Rotate key">🔄 Rotate</button>
                <button className="dev-btn dev-btn-sm dev-btn-danger" onClick={() => handleRevoke(key.id)} title="Revoke key">🚫 Revoke</button>
              </div>
            </div>
          ))}

          {revokedKeys.length > 0 && (
            <details className="dev-revoked-section">
              <summary>Revoked Keys ({revokedKeys.length})</summary>
              {revokedKeys.map(key => (
                <div key={key.id} className="dev-key-card dev-key-revoked">
                  <div className="dev-key-info">
                    <strong>{key.name}</strong>
                    <code className="dev-key-prefix">{key.key_prefix}...</code>
                    <div className="dev-key-meta">Revoked {key.revoked_at ? new Date(key.revoked_at).toLocaleDateString() : ''}</div>
                  </div>
                </div>
              ))}
            </details>
          )}
        </>
      )}
    </div>
  );
}

/* ─── Webhooks Panel ───────────────────────────────────────────────────────── */

function WebhooksPanel({ workspaceId }: { workspaceId: string }) {
  const [webhooks, setWebhooks] = useState<WebhookEndpoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const [secretResult, setSecretResult] = useState<{ id: string; secret: string } | null>(null);
  const [copiedSecret, setCopiedSecret] = useState(false);
  const [deliveries, setDeliveries] = useState<{ webhookId: string; items: WebhookDelivery[] } | null>(null);

  // Create form
  const [webhookUrl, setWebhookUrl] = useState('');
  const [webhookDesc, setWebhookDesc] = useState('');
  const [webhookEvents, setWebhookEvents] = useState<string[]>([]);

  const loadWebhooks = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      setWebhooks(await listWebhooks(workspaceId));
    } catch (e: any) {
      setError(e.message || 'Failed to load webhooks');
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => { loadWebhooks(); }, [loadWebhooks]);

  const handleCreate = async () => {
    if (!webhookUrl.trim() || webhookEvents.length === 0) return;
    try {
      setError('');
      const result: WebhookCreateResult = await createWebhook(workspaceId, webhookUrl.trim(), webhookEvents, webhookDesc.trim() || undefined);
      setSecretResult({ id: result.id, secret: result.secret });
      setCopiedSecret(false);
      setWebhookUrl('');
      setWebhookDesc('');
      setWebhookEvents([]);
      setCreating(false);
      loadWebhooks();
    } catch (e: any) {
      setError(e.message || 'Failed to create webhook');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this webhook? This action cannot be undone.')) return;
    try {
      await deleteWebhook(workspaceId, id);
      loadWebhooks();
    } catch (e: any) {
      setError(e.message || 'Failed to delete webhook');
    }
  };

  const handleToggle = async (wh: WebhookEndpoint) => {
    try {
      await updateWebhook(workspaceId, wh.id, { active: !wh.active });
      loadWebhooks();
    } catch (e: any) {
      setError(e.message || 'Failed to update webhook');
    }
  };

  const handleRotateSecret = async (id: string) => {
    try {
      const result = await rotateWebhookSecret(workspaceId, id);
      setSecretResult({ id, secret: result.secret });
      setCopiedSecret(false);
    } catch (e: any) {
      setError(e.message || 'Failed to rotate secret');
    }
  };

  const handleTest = async (id: string) => {
    try {
      const result = await testWebhook(workspaceId, id);
      alert(`Test event queued (${result.queued_deliveries} delivery).`);
    } catch (e: any) {
      setError(e.message || 'Failed to send test event');
    }
  };

  const handleViewDeliveries = async (webhookId: string) => {
    if (deliveries?.webhookId === webhookId) {
      setDeliveries(null);
      return;
    }
    try {
      const items = await listWebhookDeliveries(workspaceId, webhookId, 20);
      setDeliveries({ webhookId, items });
    } catch (e: any) {
      setError(e.message || 'Failed to load deliveries');
    }
  };

  const toggleEvent = (event: string) => {
    setWebhookEvents(prev => prev.includes(event) ? prev.filter(e => e !== event) : [...prev, event]);
  };

  const copySecret = (secret: string) => {
    navigator.clipboard.writeText(secret);
    setCopiedSecret(true);
    setTimeout(() => setCopiedSecret(false), 3000);
  };

  return (
    <div className="dev-panel">
      {secretResult && (
        <div className="dev-key-reveal">
          <div className="dev-key-reveal-header">
            <span className="dev-key-reveal-icon">🔐</span>
            <strong>Webhook Signing Secret</strong>
          </div>
          <p className="dev-key-reveal-warning">Copy this secret now — it cannot be retrieved again.</p>
          <div className="dev-key-reveal-value">
            <code>{secretResult.secret}</code>
            <button className="dev-btn dev-btn-sm" onClick={() => copySecret(secretResult.secret)}>
              {copiedSecret ? '✓ Copied' : '📋 Copy'}
            </button>
          </div>
          <button className="dev-btn dev-btn-ghost" onClick={() => setSecretResult(null)}>Dismiss</button>
        </div>
      )}

      {error && <div className="dev-error">{error}</div>}

      <div className="dev-panel-header">
        <h3>Webhooks {webhooks.length > 0 && <span className="dev-badge">{webhooks.length}</span>}</h3>
        <button className="dev-btn dev-btn-primary" onClick={() => setCreating(c => !c)}>
          {creating ? '✕ Cancel' : '+ Create Webhook'}
        </button>
      </div>

      {creating && (
        <div className="dev-create-form">
          <div className="dev-form-group">
            <label>Endpoint URL (HTTPS only)</label>
            <input type="url" value={webhookUrl} onChange={e => setWebhookUrl(e.target.value)} placeholder="https://your-app.com/webhooks/askmydata" className="dev-input" />
          </div>
          <div className="dev-form-group">
            <label>Description (optional)</label>
            <input type="text" value={webhookDesc} onChange={e => setWebhookDesc(e.target.value)} placeholder="Production webhook" maxLength={255} className="dev-input" />
          </div>
          <div className="dev-form-group">
            <label>Events</label>
            <div className="dev-scope-grid">
              {WEBHOOK_EVENTS.map(event => (
                <label key={event.value} className={`dev-scope-item${webhookEvents.includes(event.value) ? ' dev-scope-selected' : ''}`}>
                  <input type="checkbox" checked={webhookEvents.includes(event.value)} onChange={() => toggleEvent(event.value)} />
                  <span className="dev-scope-name">{event.label}</span>
                </label>
              ))}
            </div>
          </div>
          <button className="dev-btn dev-btn-primary" onClick={handleCreate} disabled={!webhookUrl.trim() || webhookEvents.length === 0}>
            Create Webhook
          </button>
        </div>
      )}

      {loading ? (
        <div className="dev-loading">Loading webhooks...</div>
      ) : (
        <>
          {webhooks.length === 0 && !creating && (
            <div className="dev-empty">No webhooks configured. Create one to receive event notifications.</div>
          )}
          {webhooks.map(wh => (
            <div key={wh.id} className={`dev-webhook-card${!wh.active ? ' dev-webhook-inactive' : ''}`}>
              <div className="dev-webhook-info">
                <div className="dev-webhook-url">
                  <span className={`dev-status-dot${wh.active ? ' dev-status-active' : ' dev-status-inactive'}`} />
                  <code>{wh.url}</code>
                </div>
                {wh.description && <p className="dev-webhook-desc">{wh.description}</p>}
                <div className="dev-key-scopes">
                  {wh.events.map(e => <span key={e} className="dev-scope-badge">{e}</span>)}
                </div>
                <div className="dev-key-meta">
                  Created {new Date(wh.created_at).toLocaleDateString()}
                  {wh.last_delivery_at && <> · Last delivery {new Date(wh.last_delivery_at).toLocaleDateString()}</>}
                  {wh.failure_count > 0 && <> · <span className="dev-failure-count">{wh.failure_count} failures</span></>}
                </div>
              </div>
              <div className="dev-webhook-actions">
                <button className="dev-btn dev-btn-sm" onClick={() => handleToggle(wh)}>{wh.active ? '⏸ Disable' : '▶ Enable'}</button>
                <button className="dev-btn dev-btn-sm" onClick={() => handleTest(wh.id)} title="Send test event">🧪 Test</button>
                <button className="dev-btn dev-btn-sm" onClick={() => handleRotateSecret(wh.id)} title="Rotate signing secret">🔄 Secret</button>
                <button className="dev-btn dev-btn-sm" onClick={() => handleViewDeliveries(wh.id)}>{deliveries?.webhookId === wh.id ? '▴ Hide' : '📜 Deliveries'}</button>
                <button className="dev-btn dev-btn-sm dev-btn-danger" onClick={() => handleDelete(wh.id)}>🗑 Delete</button>
              </div>
              {deliveries?.webhookId === wh.id && (
                <div className="dev-deliveries">
                  <h4>Recent Deliveries</h4>
                  {deliveries.items.length === 0 ? (
                    <p className="dev-empty">No deliveries yet.</p>
                  ) : (
                    <table className="dev-deliveries-table">
                      <thead>
                        <tr>
                          <th>Event</th>
                          <th>Status</th>
                          <th>Code</th>
                          <th>Duration</th>
                          <th>Attempts</th>
                          <th>Time</th>
                        </tr>
                      </thead>
                      <tbody>
                        {deliveries.items.map(d => (
                          <tr key={d.id} className={`dev-delivery-${d.status}`}>
                            <td><code>{d.event_type}</code></td>
                            <td><span className={`dev-delivery-status dev-delivery-${d.status}`}>{d.status}</span></td>
                            <td>{d.response_code ?? '—'}</td>
                            <td>{d.duration_ms != null ? `${d.duration_ms}ms` : '—'}</td>
                            <td>{d.attempt_count}</td>
                            <td>{new Date(d.created_at).toLocaleString()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              )}
            </div>
          ))}
        </>
      )}
    </div>
  );
}

/* ─── Usage Panel ──────────────────────────────────────────────────────────── */

function UsagePanel({ workspaceId }: { workspaceId: string }) {
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [period, setPeriod] = useState('30');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadUsage = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const since = new Date();
      since.setDate(since.getDate() - parseInt(period, 10));
      setUsage(await getDeveloperUsage(workspaceId, since.toISOString()));
    } catch (e: any) {
      setError(e.message || 'Failed to load usage');
    } finally {
      setLoading(false);
    }
  }, [workspaceId, period]);

  useEffect(() => { loadUsage(); }, [loadUsage]);

  return (
    <div className="dev-panel">
      {error && <div className="dev-error">{error}</div>}
      <div className="dev-panel-header">
        <h3>API Usage</h3>
        <select className="dev-select" value={period} onChange={e => setPeriod(e.target.value)}>
          <option value="1">Last 24 hours</option>
          <option value="7">Last 7 days</option>
          <option value="30">Last 30 days</option>
          <option value="90">Last 90 days</option>
        </select>
      </div>

      {loading ? (
        <div className="dev-loading">Loading usage data...</div>
      ) : usage ? (
        <div className="dev-usage-grid">
          <div className="dev-usage-card">
            <div className="dev-usage-value">{Number(usage.request_count).toLocaleString()}</div>
            <div className="dev-usage-label">Total Requests</div>
          </div>
          <div className="dev-usage-card">
            <div className="dev-usage-value dev-usage-error">{Number(usage.error_count).toLocaleString()}</div>
            <div className="dev-usage-label">Errors</div>
          </div>
          <div className="dev-usage-card">
            <div className="dev-usage-value">{Math.round(Number(usage.average_response_time_ms))}ms</div>
            <div className="dev-usage-label">Avg Response Time</div>
          </div>
          <div className="dev-usage-card">
            <div className="dev-usage-value">
              {usage.request_count > 0 ? ((Number(usage.error_count) / Number(usage.request_count)) * 100).toFixed(1) : '0.0'}%
            </div>
            <div className="dev-usage-label">Error Rate</div>
          </div>
        </div>
      ) : null}

      <div className="dev-rate-info">
        <h4>Rate Limits</h4>
        <table className="dev-deliveries-table">
          <thead><tr><th>Plan</th><th>Standard (req/hr)</th><th>Analytics (req/hr)</th></tr></thead>
          <tbody>
            <tr><td>Free</td><td>100</td><td>20</td></tr>
            <tr><td>Pro</td><td>1,000</td><td>200</td></tr>
            <tr><td>Team</td><td>5,000</td><td>1,000</td></tr>
            <tr><td>Enterprise</td><td>10,000</td><td>2,000</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ─── Documentation Panel ──────────────────────────────────────────────────── */

function DocsPanel() {
  return (
    <div className="dev-panel dev-docs-panel">
      <h3>Quick Start</h3>

      <div className="dev-docs-section">
        <h4>1. Create an API key</h4>
        <p>Go to the <strong>API Keys</strong> tab and create a key with the scopes you need. Copy the key immediately — it won't be shown again.</p>
      </div>

      <div className="dev-docs-section">
        <h4>2. Authenticate requests</h4>
        <div className="dev-code-block">
          <div className="dev-code-lang">cURL</div>
          <pre><code>{`curl -H "Authorization: Bearer ask_live_YOUR_KEY_HERE" \\
  https://your-domain.com/api/v1/public/datasets`}</code></pre>
        </div>
      </div>

      <div className="dev-docs-section">
        <h4>3. Run analytics</h4>
        <div className="dev-code-block">
          <div className="dev-code-lang">cURL</div>
          <pre><code>{`curl -X POST \\
  -H "Authorization: Bearer ask_live_YOUR_KEY_HERE" \\
  -H "Content-Type: application/json" \\
  -d '{"operation":"placement_by_internship","dataset_id":"demo-placement"}' \\
  https://your-domain.com/api/v1/public/analytics/query`}</code></pre>
        </div>
      </div>

      <div className="dev-docs-section">
        <h4>4. Ask a question</h4>
        <div className="dev-code-block">
          <div className="dev-code-lang">Python</div>
          <pre><code>{`import requests

resp = requests.post(
    "https://your-domain.com/api/v1/public/analytics/question",
    headers={"Authorization": "Bearer ask_live_YOUR_KEY_HERE"},
    json={
        "dataset_id": "demo-placement",
        "question": "What is the average CGPA of placed students?"
    }
)
print(resp.json()["data"])`}</code></pre>
        </div>
      </div>

      <div className="dev-docs-section">
        <h4>5. Verify webhook signatures</h4>
        <div className="dev-code-block">
          <div className="dev-code-lang">Python</div>
          <pre><code>{`import hashlib, hmac

def verify(payload: bytes, header: str, secret: str) -> bool:
    parts = dict(kv.split("=", 1) for kv in header.split(","))
    computed = hmac.new(
        secret.encode(),
        parts["t"].encode() + b"." + payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed, parts["v1"])`}</code></pre>
        </div>
      </div>

      <div className="dev-docs-section">
        <h4>Available Scopes</h4>
        <table className="dev-deliveries-table">
          <thead><tr><th>Scope</th><th>Description</th></tr></thead>
          <tbody>
            {API_SCOPES.map(s => <tr key={s.value}><td><code>{s.value}</code></td><td>{s.description}</td></tr>)}
          </tbody>
        </table>
      </div>

      <div className="dev-docs-section">
        <h4>Webhook Events</h4>
        <table className="dev-deliveries-table">
          <thead><tr><th>Event</th><th>Description</th></tr></thead>
          <tbody>
            {WEBHOOK_EVENTS.map(e => <tr key={e.value}><td><code>{e.value}</code></td><td>{e.label}</td></tr>)}
          </tbody>
        </table>
      </div>
    </div>
  );
}
