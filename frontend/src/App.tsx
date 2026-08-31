import { useCallback, useEffect, useState } from 'react'
import './App.css'

const API_BASE = import.meta.env.VITE_API_BASE || ''

type Incident = {
  id: number
  status: string
  severity: string
  reason: string
  service_name: string
  request_rate: number | null
  error_rate: number | null
  p95_latency_seconds: number | null
  created_at: string
}

type Investigation = {
  id: number
  incident_id: number | null
  service_name: string
  stage: string
  status: string
  likely_cause: string | null
  confidence: number | null
  recommended_action: string | null
  recommended_action_type: string | null
  approval_required: boolean
  approval_status: string
  diagnosis: string | null
}

type EventRow = {
  id: number
  timestamp: string
  event_type: string
  tool_name?: string | null
  hypothesis?: string | null
  hypothesis_status?: string | null
  decision?: string | null
  tool_result_summary?: string | null
  details?: string | null
}

type Approval = {
  id: number
  action_type: string
  reason: string
  evidence_summary: string
  expected_impact: string
  status: string
  execution_status: string
  decided_by?: string | null
  execution_result?: string | null
  decision_note?: string | null
}

type Recovery = {
  id: number
  recovered: boolean
  status: string
  details?: string | null
}

type Payload = {
  investigation: Investigation | null
  events: EventRow[]
  approvals: Approval[]
  recoveries: Recovery[]
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || response.statusText)
  }

  return response.json() as Promise<T>
}

function normalize(value: string | null | undefined): string {
  return (value || '').toLowerCase().replace(/\s+/g, '_')
}

function formatPercent(value: number | null): string {
  if (value === null || value === undefined) return '—'
  return `${(value * 100).toFixed(1)}%`
}

function formatLatency(value: number | null): string {
  if (value === null || value === undefined) return '—'
  return `${(value * 1000).toFixed(0)} ms`
}

function formatNumber(value: number | null): string {
  if (value === null || value === undefined) return '—'
  return value.toFixed(2)
}

function formatTime(value: string): string {
  return new Date(value).toLocaleString()
}

function getStatusClass(status: string): string {
  const normalized = normalize(status)

  if (['healthy', 'recovered', 'up', 'connected', 'completed'].includes(normalized)) {
    return 'healthy'
  }

  if (['degraded', 'pending', 'awaiting_approval', 'investigating', 'diagnosing'].includes(normalized)) {
    return 'warning'
  }

  if (['down', 'failed', 'critical', 'rejected', 'error'].includes(normalized)) {
    return 'danger'
  }

  return 'neutral'
}

function getEventClass(eventType: string): string {
  const normalized = normalize(eventType)

  if (normalized.includes('alert')) return 'event-alert'
  if (normalized.includes('diagnostic') || normalized.includes('tool')) return 'event-diagnostic'
  if (normalized.includes('hypothesis')) return 'event-hypothesis'
  if (normalized.includes('diagnosis')) return 'event-diagnosis'
  if (normalized.includes('approval')) return 'event-approval'
  if (normalized.includes('action') || normalized.includes('recovery')) return 'event-recovery'

  return 'event-default'
}

function App() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [summary, setSummary] = useState<Record<string, number> | null>(null)
  const [payload, setPayload] = useState<Payload | null>(null)
  const [diagnostics, setDiagnostics] = useState<Record<string, unknown> | null>(null)

  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [operator, setOperator] = useState('operator')
  const [note, setNote] = useState('')
  const [lastAction, setLastAction] = useState<{ type: string; success: boolean } | null>(null)
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [incidentRows, summaryRow, latest, diag] = await Promise.all([
        api<Incident[]>('/api/incidents/'),
        api<Record<string, number>>('/api/incidents/summary'),
        api<Payload>('/api/investigations/latest'),
        api<Record<string, unknown>>('/api/diagnostics'),
      ])

      setIncidents(incidentRows.slice(0, 12))
      setSummary(summaryRow)
      setPayload(latest)
      setDiagnostics(diag)
      setError(null)
      setLastRefresh(new Date())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load operations data')
    }
  }, [])

  useEffect(() => {
    void refresh()

    const timer = window.setInterval(() => {
      void refresh()
    }, 8000)

    return () => window.clearInterval(timer)
  }, [refresh])

  const investigation = payload?.investigation
  const pending = payload?.approvals.find((item) => item.status.toLowerCase() === 'pending')

  const canDecide =
    Boolean(investigation?.approval_required) &&
    investigation?.approval_status.toLowerCase() === 'pending' &&
    Boolean(pending)

  const latestRecovery = payload?.recoveries[0]
  const latestApproval = payload?.approvals[0]

  const diagnosticStatus =
    typeof diagnostics?.overall_status === 'string'
      ? diagnostics.overall_status
      : 'Unknown'

  const diagnosticService =
    typeof diagnostics?.service === 'string'
      ? diagnostics.service
      : investigation?.service_name || 'Unknown'

  async function decide(path: 'approve' | 'reject') {
    if (!investigation || !canDecide) return

    setBusy(true)
    setLastAction(null)

    try {
      const updated = await api<Payload>(
        `/api/investigations/${investigation.id}/${path}`,
        {
          method: 'POST',
          body: JSON.stringify({
            operator,
            note: note || `${path} from dashboard`,
          }),
        },
      )

      setPayload(updated)
      setLastAction({ type: path, success: true })
      setNote('')
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Decision failed')
      setLastAction({ type: path, success: false })
    } finally {
      setBusy(false)
    }
  }

  async function triggerInvestigation() {
    setBusy(true)
    setLastAction(null)

    try {
      await api<{ message: string }>('/api/agent/analyze', {
        method: 'POST',
        body: JSON.stringify({
          query: 'Manual investigation trigger from dashboard',
        }),
      })

      setLastAction({ type: 'investigation', success: true })
      await refresh()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to trigger investigation')
      setLastAction({ type: 'investigation', success: false })
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="ops-shell">
      <header className="ops-header">
        <div className="brand-block">
          <div className="brand-mark">RA</div>

          <div>
            <p className="eyebrow">Operations Reliability Agent</p>
            <h1>Incident Command Center</h1>
            <p className="header-description">
              Autonomous investigation, evidence-driven diagnosis and safe recovery.
            </p>
          </div>
        </div>

        <div className="header-controls">
          <div className="system-status">
            <span className="status-dot healthy" />
            <span>System operational</span>
          </div>

          {lastRefresh && (
            <span className="last-sync">
              Last sync {lastRefresh.toLocaleTimeString()}
            </span>
          )}

          <div className="header-actions">
            <button
              type="button"
              className="button secondary-button"
              onClick={() => void refresh()}
              disabled={busy}
            >
              <span>↻</span>
              {busy ? 'Refreshing...' : 'Refresh'}
            </button>

            <button
              type="button"
              className="button primary-button"
              onClick={() => void triggerInvestigation()}
              disabled={busy}
            >
              <span>+</span>
              {busy ? 'Analyzing...' : 'New Investigation'}
            </button>
          </div>
        </div>
      </header>

      {error && (
        <div className="banner error-banner" role="alert">
          <span className="banner-icon">!</span>
          <div>
            <strong>Operation error</strong>
            <p>{error}</p>
          </div>
        </div>
      )}

      {lastAction && (
        <div
          className={`banner ${lastAction.success ? 'success-banner' : 'error-banner'}`}
        >
          <span className="banner-icon">
            {lastAction.success ? '✓' : '!'}
          </span>

          <div>
            <strong>
              {lastAction.success ? 'Operation completed' : 'Operation failed'}
            </strong>
            <p>
              {lastAction.type === 'investigation'
                ? 'Investigation request processed successfully.'
                : `${lastAction.type} decision processed successfully.`}
            </p>
          </div>
        </div>
      )}

      <section className="section-heading">
        <div>
          <p className="section-kicker">Operations overview</p>
          <h2>Incident summary</h2>
        </div>
      </section>

      <section className="summary-grid">
        {[
          { key: 'total', label: 'Total incidents', className: 'neutral' },
          { key: 'healthy', label: 'Healthy', className: 'healthy' },
          { key: 'degraded', label: 'Degraded', className: 'warning' },
          { key: 'down', label: 'Down', className: 'danger' },
          { key: 'critical', label: 'Critical', className: 'critical' },
        ].map((item) => (
          <article className={`summary-card ${item.className}`} key={item.key}>
            <div className="summary-card-top">
              <span className="summary-label">{item.label}</span>
              <span className={`summary-indicator ${item.className}`} />
            </div>

            <strong>{summary?.[item.key] ?? '—'}</strong>

            <span className="summary-caption">
              {item.key === 'total'
                ? 'Recorded incidents'
                : `${item.label} incidents`}
            </span>
          </article>
        ))}
      </section>

      <section className="main-grid">
        <article className="panel investigation-panel">
          <div className="panel-header">
            <div>
              <p className="section-kicker">Agent activity</p>
              <h2>Active investigation</h2>
            </div>

            {investigation && (
              <span className={`state-badge ${getStatusClass(investigation.status)}`}>
                <span className="state-dot" />
                {investigation.status}
              </span>
            )}
          </div>

          {investigation ? (
            <>
              <div className="investigation-identity">
                <div>
                  <span className="incident-label">
                    Incident #{investigation.incident_id ?? 'n/a'}
                  </span>

                  <h3>{investigation.service_name}</h3>
                </div>

                <span className={`stage-badge ${getStatusClass(investigation.stage)}`}>
                  {investigation.stage.replace(/_/g, ' ')}
                </span>
              </div>

              <div className="investigation-grid">
                <div className="metric-box">
                  <span className="metric-label">Likely cause</span>
                  <strong>
                    {investigation.likely_cause || 'Determining...'}
                  </strong>
                </div>

                <div className="metric-box confidence-box">
                  <div className="metric-row">
                    <span className="metric-label">Confidence</span>
                    <strong>
                      {formatPercent(investigation.confidence)}
                    </strong>
                  </div>

                  <div className="confidence-track">
                    <div
                      className="confidence-fill"
                      style={{
                        width: `${Math.min(
                          Math.max((investigation.confidence || 0) * 100, 0),
                          100,
                        )}%`,
                      }}
                    />
                  </div>
                </div>
              </div>

              <div className="evidence-card">
                <div className="card-title-row">
                  <span className="card-icon">◎</span>
                  <h3>Diagnosis</h3>
                </div>

                <p>
                  {investigation.diagnosis || 'Analysis in progress...'}
                </p>
              </div>

              <div className="recommendation-card">
                <div className="recommendation-header">
                  <div>
                    <span className="metric-label">Recommended recovery</span>
                    <strong>
                      {investigation.recommended_action_type || 'None'}
                    </strong>
                  </div>

                  <span className="action-symbol">→</span>
                </div>

                <p>
                  {investigation.recommended_action ||
                    'No recovery action required.'}
                </p>
              </div>

              {pending ? (
                <div className="approval-box">
                  <div className="approval-heading">
                    <div className="approval-warning">!</div>

                    <div>
                      <span className="section-kicker">Safety control</span>
                      <h3>Human approval required</h3>
                    </div>
                  </div>

                  <p className="approval-message">
                    <strong>{pending.action_type.toUpperCase()}</strong> is
                    blocked until an authorized operator approves the action.
                  </p>

                  <div className="approval-details">
                    <div>
                      <span>Expected impact</span>
                      <p>{pending.expected_impact}</p>
                    </div>

                    <div>
                      <span>Evidence</span>
                      <p>
                        {pending.evidence_summary
                          ? `${pending.evidence_summary.substring(0, 240)}${pending.evidence_summary.length > 240 ? '...' : ''}`
                          : 'No evidence summary available.'}
                      </p>
                    </div>
                  </div>

                  <div className="approval-form">
                    <label>
                      <span>Operator</span>
                      <input
                        value={operator}
                        onChange={(event) => setOperator(event.target.value)}
                        placeholder="Enter operator name"
                      />
                    </label>

                    <label>
                      <span>Decision note</span>
                      <input
                        value={note}
                        onChange={(event) => setNote(event.target.value)}
                        placeholder="Optional audit note"
                      />
                    </label>
                  </div>

                  <div className="approval-actions">
                    <button
                      type="button"
                      className="button approve-button"
                      disabled={!canDecide || busy}
                      onClick={() => void decide('approve')}
                    >
                      ✓ Approve action
                    </button>

                    <button
                      type="button"
                      className="button reject-button"
                      disabled={!canDecide || busy}
                      onClick={() => void decide('reject')}
                    >
                      ✕ Reject
                    </button>
                  </div>

                  <p className="safety-note">
                    High-impact actions cannot execute without explicit human
                    approval.
                  </p>
                </div>
              ) : latestApproval ? (
                <div className="approval-history">
                  <div className="card-title-row">
                    <span className="card-icon">✓</span>
                    <h3>Recent approval decision</h3>
                  </div>

                  <div className="approval-history-grid">
                    <div>
                      <span>Action</span>
                      <strong>{latestApproval.action_type}</strong>
                    </div>

                    <div>
                      <span>Status</span>
                      <strong>{latestApproval.status}</strong>
                    </div>

                    <div>
                      <span>Execution</span>
                      <strong>{latestApproval.execution_status}</strong>
                    </div>

                    {latestApproval.decided_by && (
                      <div>
                        <span>Decided by</span>
                        <strong>{latestApproval.decided_by}</strong>
                      </div>
                    )}
                  </div>

                  {latestApproval.decision_note && (
                    <p className="history-note">
                      Note: {latestApproval.decision_note}
                    </p>
                  )}
                </div>
              ) : (
                <div className="normal-operation">
                  <span className="normal-icon">✓</span>
                  <div>
                    <strong>No pending approval</strong>
                    <p>System can continue operating without intervention.</p>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="empty-state">
              <div className="empty-icon">◎</div>
              <h3>No active investigation</h3>
              <p>
                There is currently no active investigation requiring attention.
              </p>

              <button
                type="button"
                className="button primary-button"
                onClick={() => void triggerInvestigation()}
                disabled={busy}
              >
                Start new investigation
              </button>
            </div>
          )}
        </article>

        <article className="panel recovery-panel">
          <div className="panel-header">
            <div>
              <p className="section-kicker">Controlled recovery</p>
              <h2>Recovery status</h2>
            </div>

            {latestRecovery && (
              <span
                className={`state-badge ${latestRecovery.recovered ? 'healthy' : 'danger'}`}
              >
                <span className="state-dot" />
                {latestRecovery.recovered ? 'Verified' : 'Failed'}
              </span>
            )}
          </div>

          {latestRecovery ? (
            <div
              className={`recovery-result ${
                latestRecovery.recovered ? 'recovery-success' : 'recovery-failed'
              }`}
            >
              <div className="recovery-icon">
                {latestRecovery.recovered ? '✓' : '!'}
              </div>

              <div>
                <span>Latest verification</span>
                <strong>
                  {latestRecovery.recovered
                    ? 'Recovery verified'
                    : 'Recovery not verified'}
                </strong>
                <p>{latestRecovery.status}</p>
              </div>
            </div>
          ) : (
            <div className="recovery-pending">
              <span className="large-status-dot" />
              <div>
                <strong>No recovery executed</strong>
                <p>
                  Recovery verification will appear here after an approved
                  action.
                </p>
              </div>
            </div>
          )}

          <div className="divider" />

          <div className="panel-header compact">
            <div>
              <p className="section-kicker">Audit trail</p>
              <h3>Investigation timeline</h3>
            </div>

            <span className="event-count">
              {payload?.events.length || 0} events
            </span>
          </div>

          <ol className="timeline">
            {(payload?.events || []).map((event) => (
              <li
                key={event.id}
                className={`timeline-item ${getEventClass(event.event_type)}`}
              >
                <div className="timeline-marker" />

                <div className="timeline-content">
                  <div className="timeline-top">
                    <strong>{event.event_type.replace(/_/g, ' ')}</strong>
                    <time>{formatTime(event.timestamp)}</time>
                  </div>

                  {event.tool_name && (
                    <span className="timeline-meta">
                      Tool: {event.tool_name}
                    </span>
                  )}

                  {event.hypothesis && (
                    <span className="timeline-meta">
                      Hypothesis: {event.hypothesis}
                    </span>
                  )}

                  {event.hypothesis_status && (
                    <span
                      className={`hypothesis-status ${getStatusClass(event.hypothesis_status)}`}
                    >
                      {event.hypothesis_status}
                    </span>
                  )}

                  {event.decision && (
                    <span className="timeline-meta">
                      Decision: {event.decision}
                    </span>
                  )}

                  {(event.tool_result_summary || event.details) && (
                    <p className="timeline-details">
                      {event.tool_result_summary || event.details}
                    </p>
                  )}
                </div>
              </li>
            ))}

            {!payload?.events.length && (
              <li className="timeline-empty">No investigation events yet.</li>
            )}
          </ol>
        </article>
      </section>

      <section className="secondary-grid">
        <article className="panel incidents-panel">
          <div className="panel-header">
            <div>
              <p className="section-kicker">Operational history</p>
              <h2>Recent incidents</h2>
            </div>

            <span className="event-count">Latest 12</span>
          </div>

          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Status</th>
                  <th>Severity</th>
                  <th>Service</th>
                  <th>Request rate</th>
                  <th>Error rate</th>
                  <th>Time</th>
                </tr>
              </thead>

              <tbody>
                {incidents.map((incident) => (
                  <tr key={incident.id}>
                    <td className="incident-id">#{incident.id}</td>

                    <td>
                      <span className={`table-badge ${getStatusClass(incident.status)}`}>
                        {incident.status}
                      </span>
                    </td>

                    <td>
                      <span
                        className={`table-badge severity-${normalize(incident.severity)}`}
                      >
                        {incident.severity}
                      </span>
                    </td>

                    <td className="service-cell">
                      {incident.service_name}
                    </td>

                    <td className="mono-value">
                      {formatNumber(incident.request_rate)} req/s
                    </td>

                    <td className="mono-value">
                      {formatPercent(incident.error_rate)}
                    </td>

                    <td className="time-cell">
                      {formatTime(incident.created_at)}
                    </td>
                  </tr>
                ))}

                {!incidents.length && (
                  <tr>
                    <td colSpan={7} className="table-empty">
                      No incidents recorded.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </article>

        <article className="panel diagnostics-panel">
          <div className="panel-header">
            <div>
              <p className="section-kicker">Observability</p>
              <h2>Live diagnostics</h2>
            </div>

            <span
              className={`state-badge ${getStatusClass(diagnosticStatus)}`}
            >
              <span className="state-dot" />
              {diagnosticStatus}
            </span>
          </div>

          <div className="diagnostic-service">
            <span>Monitored service</span>
            <strong>{diagnosticService}</strong>
          </div>

          <div className="diagnostic-list">
            <div className="diagnostic-row">
              <span>Overall status</span>
              <strong className={getStatusClass(diagnosticStatus)}>
                {diagnosticStatus}
              </strong>
            </div>

            <div className="diagnostic-row">
              <span>Service</span>
              <strong>{diagnosticService}</strong>
            </div>

            {investigation && (
              <>
                <div className="diagnostic-row">
                  <span>Error rate</span>
                  <strong>
                    {formatPercent(
                      incidents[0]?.error_rate ?? null,
                    )}
                  </strong>
                </div>

                <div className="diagnostic-row">
                  <span>P95 latency</span>
                  <strong>
                    {formatLatency(
                      incidents[0]?.p95_latency_seconds ?? null,
                    )}
                  </strong>
                </div>

                <div className="diagnostic-row">
                  <span>Request rate</span>
                  <strong>
                    {formatNumber(
                      incidents[0]?.request_rate ?? null,
                    )}{' '}
                    req/s
                  </strong>
                </div>
              </>
            )}
          </div>

          <details className="diagnostics-details">
            <summary>
              <span>View raw diagnostic data</span>
              <span>⌄</span>
            </summary>

            <pre>{JSON.stringify(diagnostics, null, 2)}</pre>
          </details>
        </article>
      </section>

      <footer className="ops-footer">
        <span>Operations Reliability Agent</span>
        <span>Read-only diagnostics • Human-approved recovery</span>
      </footer>
    </main>
  )
}

export default App