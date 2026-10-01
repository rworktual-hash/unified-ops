import { useCallback, useEffect, useState } from 'react'
import {
  createLlmObsKey,
  createLlmObsProject,
  fetchLlmObsSummary,
  fetchLlmObsTrace,
  listLlmObsKeys,
  listLlmObsProjects,
  listLlmObsTraces,
  revokeLlmObsKey,
  type LlmObsApiKey,
  type LlmObsProject,
  type LlmObsRun,
  type LlmObsSummary,
  type LlmObsTrace,
  type LlmObsTraceDetail,
} from '../api'
import { formatWhen } from '../formatWhen'

const EMPTY_SUMMARY: LlmObsSummary = {
  total: 0,
  success: 0,
  error: 0,
  avg_latency_ms: null,
  total_tokens: 0,
  models: [],
}

type View = 'traces' | 'trace' | 'projects'

function dayStart(day: string): string {
  return `${day}T00:00:00+05:30`
}

function dayEnd(day: string): string {
  return `${day}T23:59:59+05:30`
}

type FlowItem = { run: LlmObsRun; n: number; children: FlowItem[] }

function byStarted(a: LlmObsRun, b: LlmObsRun): number {
  const left = a.started_at ? Date.parse(a.started_at) : 0
  const right = b.started_at ? Date.parse(b.started_at) : 0
  if (left !== right) return left - right
  return a.id - b.id
}

function buildFlow(runs: LlmObsRun[]): FlowItem[] {
  const ordered = [...runs].sort(byStarted)
  const ids = new Set(ordered.map((run) => run.external_id))
  const byParent = new Map<string | null, LlmObsRun[]>()
  for (const run of ordered) {
    const parent = run.parent_id && ids.has(run.parent_id) ? run.parent_id : null
    const group = byParent.get(parent) ?? []
    group.push(run)
    byParent.set(parent, group)
  }
  const walk = (parent: string | null, counter: { n: number }): FlowItem[] =>
    (byParent.get(parent) ?? []).map((run) => {
      const n = counter.n
      counter.n += 1
      return { run, n, children: walk(run.external_id, counter) }
    })
  return walk(null, { n: 1 })
}

function tokenLine(run: LlmObsRun): string | null {
  if (run.input_tokens == null && run.output_tokens == null && run.total_tokens == null) return null
  const parts: string[] = []
  if (run.input_tokens != null) parts.push(`${run.input_tokens} input tokens`)
  if (run.output_tokens != null) parts.push(`${run.output_tokens} output tokens`)
  if (run.total_tokens != null) parts.push(`${run.total_tokens} total`)
  return parts.join(' · ')
}

function FlowBlock({ label, text }: { label: string; text: string }) {
  return (
    <label className="llm-block">
      {label}
      <pre>{text}</pre>
    </label>
  )
}

function FlowCard({ item }: { item: FlowItem }) {
  const { run, children } = item
  const nested = children.length > 0
  const tokens = tokenLine(run)
  const inputLabel = run.type === 'tool' ? 'Tool input' : run.type === 'llm' ? 'Prompt' : 'Request'
  const outputLabel = nested ? 'Final response' : run.type === 'tool' ? 'Tool output' : 'Response'
  return (
    <li className={`llm-flow-item${run.status === 'error' ? ' llm-flow-item--error' : ''}`}>
      <article className="llm-flow-card">
        <header className="llm-run-head">
          <span className="llm-flow-num">{item.n}</span>
          <span className="llm-type">{run.type}</span>
          <strong>{run.name}</strong>
          {run.model ? <span className="muted">{run.model}</span> : null}
          <span className={run.status === 'error' ? 'llm-status llm-status--error' : 'llm-status'}>{run.status}</span>
          {run.latency_ms != null ? <span className="muted">{run.latency_ms} ms</span> : null}
        </header>
        {tokens ? <p className="llm-tokens">{tokens}</p> : null}
        {run.system_prompt ? <FlowBlock label="System prompt" text={run.system_prompt} /> : null}
        {run.input ? <FlowBlock label={inputLabel} text={run.input} /> : null}
        {nested ? (
          <ol className="llm-flow">
            {children.map((child) => (
              <FlowCard key={child.run.id} item={child} />
            ))}
          </ol>
        ) : null}
        {run.error ? <p className="llm-error">{run.error}</p> : null}
        {run.output ? <FlowBlock label={outputLabel} text={run.output} /> : null}
      </article>
    </li>
  )
}

export function LlmObsPanel() {
  const [view, setView] = useState<View>('traces')
  const [projects, setProjects] = useState<LlmObsProject[]>([])
  const [projectName, setProjectName] = useState('')
  const [selectedProject, setSelectedProject] = useState<number | ''>('')
  const [keys, setKeys] = useState<LlmObsApiKey[]>([])
  const [freshKey, setFreshKey] = useState<string | null>(null)
  const [model, setModel] = useState('')
  const [status, setStatus] = useState('')
  const [fromDay, setFromDay] = useState('')
  const [toDay, setToDay] = useState('')
  const [summary, setSummary] = useState<LlmObsSummary>(EMPTY_SUMMARY)
  const [traces, setTraces] = useState<LlmObsTrace[]>([])
  const [detail, setDetail] = useState<LlmObsTraceDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const filters = {
    projectId: selectedProject === '' ? undefined : selectedProject,
    model: model || undefined,
    status: status || undefined,
    from: fromDay ? dayStart(fromDay) : undefined,
    to: toDay ? dayEnd(toDay) : undefined,
  }

  const loadBoard = useCallback(async () => {
    const [nextSummary, nextTraces] = await Promise.all([
      fetchLlmObsSummary(filters),
      listLlmObsTraces(filters),
    ])
    setSummary(nextSummary)
    setTraces(nextTraces)
  }, [selectedProject, model, status, fromDay, toDay])

  const loadProjects = useCallback(async () => {
    setProjects(await listLlmObsProjects())
  }, [])

  useEffect(() => {
    void loadProjects().catch((err) => setError(err instanceof Error ? err.message : 'Failed to load projects'))
  }, [loadProjects])

  useEffect(() => {
    if (view === 'projects') return
    void loadBoard().catch((err) => setError(err instanceof Error ? err.message : 'Failed to load traces'))
  }, [loadBoard, view])

  useEffect(() => {
    if (selectedProject === '') {
      setKeys([])
      return
    }
    void listLlmObsKeys(selectedProject)
      .then(setKeys)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load API keys'))
  }, [selectedProject])

  const ingestUrl = `${window.location.origin}/api/llm-obs/ingest`
  const flow = detail ? buildFlow(detail.runs) : []

  function openTrace(traceId: number) {
    setError(null)
    void fetchLlmObsTrace(traceId)
      .then((next) => {
        setDetail(next)
        setView('trace')
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load trace'))
  }

  return (
    <div className="llm-obs">
      {view !== 'trace' ? (
        <div className="domain-tabs">
          <button
            type="button"
            className={`domain-tab${view === 'traces' ? ' active' : ''}`}
            onClick={() => setView('traces')}
          >
            Traces
          </button>
          <button
            type="button"
            className={`domain-tab${view === 'projects' ? ' active' : ''}`}
            onClick={() => setView('projects')}
          >
            Projects
          </button>
        </div>
      ) : null}
      {error ? <p className="banner error">{error}</p> : null}

      {view === 'traces' ? (
        <section className="panel">
          <div className="llm-filters">
            <label className="field-label">
              Project
              <select
                value={selectedProject}
                onChange={(event) => setSelectedProject(event.target.value ? Number(event.target.value) : '')}
              >
                <option value="">All projects</option>
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.display_name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field-label">
              Model
              <select value={model} onChange={(event) => setModel(event.target.value)}>
                <option value="">All models</option>
                {summary.models.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field-label">
              Status
              <select value={status} onChange={(event) => setStatus(event.target.value)}>
                <option value="">All</option>
                <option value="success">Success</option>
                <option value="error">Failed</option>
              </select>
            </label>
            <label className="field-label">
              From
              <input type="date" value={fromDay} onChange={(event) => setFromDay(event.target.value)} />
            </label>
            <label className="field-label">
              To
              <input type="date" value={toDay} onChange={(event) => setToDay(event.target.value)} />
            </label>
          </div>
          <div className="host-kpis">
            <div className="host-kpi">
              <span>Traces</span>
              <strong>{summary.total}</strong>
            </div>
            <div className="host-kpi">
              <span>Succeeded</span>
              <strong>{summary.success}</strong>
            </div>
            <div className="host-kpi">
              <span>Failed</span>
              <strong>{summary.error}</strong>
            </div>
            <div className="host-kpi">
              <span>Avg latency</span>
              <strong>{summary.avg_latency_ms != null ? `${summary.avg_latency_ms} ms` : '—'}</strong>
            </div>
            <div className="host-kpi">
              <span>Tokens</span>
              <strong>{summary.total_tokens}</strong>
            </div>
          </div>
          {traces.length === 0 ? (
            <p className="muted">No traces for this filter. Open Projects to create a key, then send a chat turn.</p>
          ) : (
            <div className="table-wrap">
              <table className="users-table">
                <thead>
                  <tr>
                    <th>When</th>
                    <th>Project</th>
                    <th>Chat turn</th>
                    <th>Agent</th>
                    <th>Model</th>
                    <th>Tools</th>
                    <th>Status</th>
                    <th>Latency</th>
                    <th>Tokens</th>
                  </tr>
                </thead>
                <tbody>
                  {traces.map((trace) => (
                    <tr key={trace.id} onClick={() => openTrace(trace.id)}>
                      <td>{formatWhen(trace.started_at)}</td>
                      <td>{trace.project}</td>
                      <td>{trace.name}</td>
                      <td>{trace.agents.join(', ') || '—'}</td>
                      <td>{trace.models.join(', ') || '—'}</td>
                      <td>
                        {trace.tools.length}
                        {trace.failed_tools.length ? ` · ${trace.failed_tools.length} failed` : ''}
                      </td>
                      <td className={trace.status === 'error' ? 'llm-status llm-status--error' : 'llm-status'}>
                        {trace.status}
                      </td>
                      <td>{trace.latency_ms != null ? `${trace.latency_ms} ms` : '—'}</td>
                      <td>{trace.total_tokens}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ) : null}

      {view === 'trace' && detail ? (
        <section className="panel">
          <div className="panel-head">
            <div>
              <button
                type="button"
                className="btn ghost"
                onClick={() => {
                  setView('traces')
                  setDetail(null)
                }}
              >
                Back to traces
              </button>
              <h2>{detail.name}</h2>
              <p className="muted-block">
                {detail.project} · {formatWhen(detail.started_at)}
                {detail.latency_ms != null ? ` · ${detail.latency_ms} ms` : ''}
                {detail.error ? ` · ${detail.error}` : ''}
              </p>
            </div>
          </div>
          <ol className="llm-flow">
            {flow.map((item) => (
              <FlowCard key={item.run.id} item={item} />
            ))}
          </ol>
        </section>
      ) : null}

      {view === 'projects' ? (
        <section className="panel">
          <div className="panel-head">
            <div>
              <h2>Projects</h2>
              <p className="muted-block">One project per app, such as crm, ccaas, or ticketing.</p>
            </div>
          </div>
          <form
            className="llm-create"
            onSubmit={async (event) => {
              event.preventDefault()
              setBusy(true)
              setError(null)
              try {
                const created = await createLlmObsProject(projectName.trim())
                setProjectName('')
                setSelectedProject(created.id)
                setFreshKey(null)
                await loadProjects()
              } catch (err) {
                setError(err instanceof Error ? err.message : 'Could not create project')
              } finally {
                setBusy(false)
              }
            }}
          >
            <label className="field-label">
              Project name
              <input
                value={projectName}
                onChange={(event) => setProjectName(event.target.value)}
                placeholder="crm"
                pattern="[a-z0-9][a-z0-9-]{0,62}"
                required
              />
            </label>
            <button type="submit" className="btn primary" disabled={busy}>
              Create project
            </button>
          </form>
          {projects.length === 0 ? (
            <p className="muted">No projects yet.</p>
          ) : (
            <div className="table-wrap">
              <table className="users-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {projects.map((project) => (
                    <tr
                      key={project.id}
                      className={selectedProject === project.id ? 'llm-row-open' : undefined}
                      onClick={() => {
                        setFreshKey(null)
                        setSelectedProject(project.id)
                      }}
                    >
                      <td>{project.display_name}</td>
                      <td>{formatWhen(project.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {selectedProject !== '' ? (
            <div className="llm-keys">
              <div className="panel-head">
                <h2>API key</h2>
                <button
                  type="button"
                  className="btn primary"
                  disabled={busy}
                  onClick={async () => {
                    setBusy(true)
                    setError(null)
                    try {
                      const created = await createLlmObsKey(selectedProject, 'default')
                      setFreshKey(created.api_key)
                      setKeys(await listLlmObsKeys(selectedProject))
                    } catch (err) {
                      setError(err instanceof Error ? err.message : 'Could not create key')
                    } finally {
                      setBusy(false)
                    }
                  }}
                >
                  Create key
                </button>
              </div>
              {freshKey ? (
                <p className="banner llm-key-once">
                  Copy this key now. It will not be shown again.
                  <code>{freshKey}</code>
                </p>
              ) : (
                <p className="muted">The full key is shown only at the moment you create it.</p>
              )}
              {keys.length === 0 ? (
                <p className="muted">No keys yet.</p>
              ) : (
                <ul className="llm-key-list">
                  {keys.map((key) => (
                    <li key={key.id}>
                      <code>{key.key_prefix}…</code>
                      <span className="muted">{key.name}</span>
                      <span className={key.revoked ? 'llm-status llm-status--error' : 'llm-status'}>
                        {key.revoked ? 'revoked' : 'active'}
                      </span>
                      {!key.revoked ? (
                        <button
                          type="button"
                          className="btn ghost"
                          onClick={async () => {
                            setError(null)
                            try {
                              await revokeLlmObsKey(selectedProject, key.id)
                              setKeys(await listLlmObsKeys(selectedProject))
                              if (freshKey?.startsWith(key.key_prefix)) setFreshKey(null)
                            } catch (err) {
                              setError(err instanceof Error ? err.message : 'Could not revoke key')
                            }
                          }}
                        >
                          Revoke
                        </button>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
              <label className="llm-block">
                Ingest URL
                <pre>{ingestUrl}</pre>
              </label>
              <label className="llm-block">
                Env for the app
                <pre>{`LLM_OBS_ENDPOINT=${window.location.origin}\nLLM_OBS_API_KEY=`}</pre>
              </label>
            </div>
          ) : (
            <p className="muted">Select a project to manage its key.</p>
          )}
        </section>
      ) : null}
    </div>
  )
}
