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

function stepDepth(run: LlmObsRun, runs: LlmObsRun[]): number {
  let depth = 0
  let parent = run.parent_id
  const seen = new Set<string>()
  while (parent) {
    if (seen.has(parent)) break
    seen.add(parent)
    depth += 1
    const next = runs.find((item) => item.external_id === parent)
    parent = next?.parent_id ?? null
  }
  return depth
}

function StepBody({ run }: { run: LlmObsRun }) {
  return (
    <div className="llm-step-body">
      <header className="llm-run-head">
        <span className={`llm-type llm-type--${run.type}`}>{run.type}</span>
        <strong>{run.name}</strong>
        {run.model ? <span className="muted">{run.model}</span> : null}
        <span className={run.status === 'error' ? 'llm-status llm-status--error' : 'llm-status'}>{run.status}</span>
        {run.latency_ms != null ? <span className="muted">{run.latency_ms} ms</span> : null}
        {run.total_tokens != null ? <span className="muted">{run.total_tokens} tokens</span> : null}
      </header>
      {run.error ? <p className="llm-error">{run.error}</p> : null}
      {run.system_prompt ? (
        <label className="llm-block">
          System prompt
          <pre>{run.system_prompt}</pre>
        </label>
      ) : null}
      {run.input ? (
        <label className="llm-block">
          Input
          <pre>{run.input}</pre>
        </label>
      ) : null}
      {run.output ? (
        <label className="llm-block">
          Output
          <pre>{run.output}</pre>
        </label>
      ) : null}
      {!run.error && !run.system_prompt && !run.input && !run.output ? (
        <p className="muted">This step has no prompt or output.</p>
      ) : null}
    </div>
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
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null)
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

  const selectedRun = detail?.runs.find((run) => run.id === selectedRunId) ?? null
  const ingestUrl = `${window.location.origin}/api/llm-obs/ingest`

  function openTrace(traceId: number) {
    setError(null)
    void fetchLlmObsTrace(traceId)
      .then((next) => {
        const failed = next.runs.find((run) => run.status === 'error')
        setDetail(next)
        setSelectedRunId(failed?.id ?? next.runs[0]?.id ?? null)
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
                  setSelectedRunId(null)
                }}
              >
                Back to traces
              </button>
              <h2>{detail.name}</h2>
              <p className="muted-block">
                {detail.project} · {formatWhen(detail.started_at)}
                {detail.error ? ` · ${detail.error}` : ''}
              </p>
            </div>
          </div>
          <div className="llm-trace">
            <ol className="llm-steps">
              {detail.runs.map((run) => (
                <li key={run.id}>
                  <button
                    type="button"
                    className={`llm-step${run.id === selectedRunId ? ' llm-step--open' : ''}${run.status === 'error' ? ' llm-step--error' : ''}`}
                    style={{ paddingLeft: `${0.75 + stepDepth(run, detail.runs) * 0.9}rem` }}
                    onClick={() => setSelectedRunId(run.id)}
                  >
                    <span className="llm-type">{run.type}</span>
                    <strong>{run.name}</strong>
                    <span className={run.status === 'error' ? 'llm-status llm-status--error' : 'llm-status'}>
                      {run.status}
                    </span>
                    {run.latency_ms != null ? <span className="muted">{run.latency_ms} ms</span> : null}
                  </button>
                </li>
              ))}
            </ol>
            {selectedRun ? <StepBody run={selectedRun} /> : <p className="muted">Select a step.</p>}
          </div>
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
