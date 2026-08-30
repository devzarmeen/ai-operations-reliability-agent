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

function getStatusColor(status: string): string {
  const s = status.toLowerCase()
  if (s === 'healthy' || s === 'recovered') return '#166534'
  if (s === 'degraded') return '#ca8a04'
  if (s === 'down' || s === 'failed') return '#991b1b'
  return '#4b5563'
}

function getSeverityColor(severity: string): string {
  const s = severity.toLowerCase()
  if (s === 'low') return '#166534'
  if (s === 'medium') return '#ca8a04'
  if (s === 'high') return '#dc2626'
  if (s === 'critical') return '#7f1d1d'
  return '#4b5563'
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
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load operations data')
    }
  }, [])

  useEffect(() => {
    void refresh()
    const timer = window.setInterval(() => void refresh(), 8000)
    return () => window.clearInterval(timer)
  }, [refresh])

  const investigation = payload?.investigation
  const pending = payload?.approvals.find((item) => item.status === 'pending')
  const canDecide =
    Boolean(investigation?.approval_required) &&
    investigation?.approval_status === 'pending' &&
    Boolean(pending)

  async function decide(path: 'approve' | 'reject') {
    if (!investigation || !canDecide) return
    setBusy(true)
    setLastAction(null)
    try {
      const updated = await api<Payload>(
        `/api/investigations/${investigation.id}/${path}`,
        {
          method: 'POST',
          body: JSON.stringify({ operator, note: note || `${path} from dashboard` }),
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
        body: JSON.stringify({ query: 'Manual investigation trigger from dashboard' }),
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

  const latestRecovery = payload?.recoveries[0]
  const latestApproval = payload?.approvals[0]

  return (
    <main className="ops-shell">
      <header className="ops-header">
        <div>
          <p className="eyebrow">Operations Reliability Agent</p>
          <h1>Incident command</h1>
        </div>
        <div className="header-actions">
          <button 
            type="button" 
            className="counter" 
            onClick={() => void refresh()}
            disabled={busy}
          >
            {busy ? 'Refreshing...' : 'Refresh'}
          </button>
          <button 
            type="button" 
            className="counter secondary" 
            onClick={() => void triggerInvestigation()}
            disabled={busy}
          >
            {busy ? 'Analyzing...' : 'New Investigation'}
          </button>
        </div>
      </header>

      {error ? <p className="error-banner">{error}</p> : null}
      
      {lastAction && (
        <p className={`action-banner ${lastAction.success ? 'success' : 'error'}`}>
          {lastAction.success ? '✓' : '✗'} {lastAction.type} {lastAction.success ? 'completed successfully' : 'failed'}
        </p>
      )}

      <section className="summary-grid">
        {['total', 'healthy', 'degraded', 'down', 'critical'].map((key) => (
          <article key={key} className="summary-card">
            <span>{key}</span>
            <strong>{summary?.[key] ?? '—'}</strong>
          </article>
        ))}
      </section>

      <section className="ops-grid">
        <article className="panel">
          <h2>Active investigation</h2>
          {investigation ? (
            <>
              <div className="investigation-header">
                <span className={`status-badge ${investigation.status.toLowerCase()}`}>
                  {investigation.status}
                </span>
                <span className={`stage-badge ${investigation.stage.toLowerCase()}`}>
                  {investigation.stage}
                </span>
              </div>
              
              <dl className="investigation-details">
                <div><dt>Incident ID</dt><dd>#{investigation.incident_id ?? 'n/a'}</dd></div>
                <div><dt>Service</dt><dd>{investigation.service_name}</dd></div>
                <div><dt>Likely cause</dt><dd>{investigation.likely_cause || 'Determining...'}</dd></div>
                <div><dt>Confidence</dt><dd>{investigation.confidence ? `${(investigation.confidence * 100).toFixed(1)}%` : 'n/a'}</dd></div>
                <div><dt>Approval status</dt><dd>
                  <span className={`approval-status ${investigation.approval_status.toLowerCase()}`}>
                    {investigation.approval_status}
                  </span>
                  {investigation.approval_required && <span className="required-badge">Required</span>}
                </dd></div>
              </dl>

              <div className="diagnosis-section">
                <h3>Diagnosis</h3>
                <p className="diagnosis">{investigation.diagnosis || 'Analysis in progress...'}</p>
              </div>

              <div className="action-section">
                <h3>Recommended action</h3>
                <p className="recommended-action">
                  <strong>{investigation.recommended_action_type || 'None'}</strong>: {investigation.recommended_action || 'No action required'}
                </p>
              </div>

              {pending ? (
                <div className="approval-box">
                  <h3>⚠️ Approval required</h3>
                  <p><strong>{pending.action_type.toUpperCase()}</strong> is blocked until a human approves it.</p>
                  <p className="impact">{pending.expected_impact}</p>
                  
                  <div className="approval-evidence">
                    <h4>Evidence summary:</h4>
                    <p>{pending.evidence_summary.substring(0, 200)}...</p>
                  </div>

                  <label>
                    Operator name
                    <input 
                      value={operator} 
                      onChange={(event) => setOperator(event.target.value)} 
                      placeholder="Enter your name"
                    />
                  </label>
                  
                  <label>
                    Decision note (optional)
                    <input 
                      value={note}
                      onChange={(event) => setNote(event.target.value)}
                      placeholder="Add a note for the audit trail"
                    />
                  </label>

                  <div className="actions">
                    <button
                      type="button"
                      className="approve"
                      disabled={!canDecide || busy}
                      onClick={() => void decide('approve')}
                    >
                      {busy ? 'Processing...' : '✓ Approve'}
                    </button>
                    <button
                      type="button"
                      className="reject"
                      disabled={!canDecide || busy}
                      onClick={() => void decide('reject')}
                    >
                      {busy ? 'Processing...' : '✗ Reject'}
                    </button>
                  </div>
                  <p className="hint">High-impact actions cannot run without explicit human approval.</p>
                </div>
              ) : latestApproval ? (
                <div className="approval-history">
                  <h3>Recent approval decision</h3>
                  <p><strong>{latestApproval.action_type.toUpperCase()}</strong> - {latestApproval.status}</p>
                  <p>Execution: {latestApproval.execution_status}</p>
                  {latestApproval.decided_by && <p>Decided by: {latestApproval.decided_by}</p>}
                  {latestApproval.decision_note && <p>Note: {latestApproval.decision_note}</p>}
                </div>
              ) : (
                <p className="hint">No pending approval. System operating normally.</p>
              )}
            </>
          ) : (
            <div className="no-investigation">
              <p>No active investigation. System is operating normally.</p>
              <button 
                type="button" 
                className="counter"
                onClick={() => void triggerInvestigation()}
                disabled={busy}
              >
                Start new investigation
              </button>
            </div>
          )}
        </article>

        <article className="panel">
          <h2>Recovery status & audit trail</h2>
          
          {latestRecovery && (
            <div className={`recovery-status ${latestRecovery.recovered ? 'recovered' : 'failed'}`}>
              <h3>Latest verification</h3>
              <p><strong>Status:</strong> {latestRecovery.recovered ? '✓ Recovered' : '✗ Not recovered'}</p>
              <p><strong>System status:</strong> {latestRecovery.status}</p>
            </div>
          )}

          <h3>Investigation timeline</h3>
          <ol className="timeline">
            {(payload?.events || []).map((event) => (
              <li key={event.id} className={`timeline-item ${event.event_type.toLowerCase()}`}>
                <span className="event-type">{event.event_type}</span>
                <small className="event-time">{new Date(event.timestamp).toLocaleString()}</small>
                {event.tool_name && <span className="event-tool">Tool: {event.tool_name}</span>}
                {event.hypothesis && <span className="event-hypothesis">Hypothesis: {event.hypothesis}</span>}
                {event.hypothesis_status && (
                  <span className={`event-hypothesis-status ${event.hypothesis_status.toLowerCase()}`}>
                    {event.hypothesis_status}
                  </span>
                )}
                {event.decision && <span className="event-decision">Decision: {event.decision}</span>}
                {event.details && <span className="event-details">{event.details.substring(0, 100)}...</span>}
              </li>
            ))}
          </ol>
        </article>
      </section>

      <section className="ops-grid">
        <article className="panel">
          <h2>Recent incidents</h2>
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Status</th>
                <th>Severity</th>
                <th>Service</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {incidents.map((incident) => (
                <tr key={incident.id}>
                  <td>#{incident.id}</td>
                  <td>
                    <span className="status-badge" style={{ color: getStatusColor(incident.status) }}>
                      {incident.status}
                    </span>
                  </td>
                  <td>
                    <span className="severity-badge" style={{ color: getSeverityColor(incident.severity) }}>
                      {incident.severity}
                    </span>
                  </td>
                  <td>{incident.service_name}</td>
                  <td>{new Date(incident.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
        <article className="panel">
          <h2>Live diagnostics</h2>
          <div className="diagnostics-summary">
            <div className="diagnostic-item">
              <span className="diagnostic-label">Overall status</span>
              <span className={`diagnostic-value ${(diagnostics?.overall_status as string)?.toLowerCase() || 'unknown'}`}>
                {(diagnostics?.overall_status as string) || 'Unknown'}
              </span>
            </div>
            <div className="diagnostic-item">
              <span className="diagnostic-label">Service</span>
              <span className="diagnostic-value">{diagnostics?.service as string || 'Unknown'}</span>
            </div>
          </div>
          <details className="diagnostics-details">
            <summary>Full diagnostic data</summary>
            <pre>{JSON.stringify(diagnostics, null, 2)}</pre>
          </details>
        </article>
      </section>
    </main>
  )
}

export default App
