import { Download, History } from 'lucide-react'
import { useState } from 'react'
import { dateLabel, useResource } from './api'
import { planEndpoint, type PlanHistoryResponse } from './planApi'
import { Badge, Busy, Warning } from './ui'

interface Props { projectId: string; activeRevision: number; working: boolean; restore: (revision: number) => void }

function VersionList({ projectId, activeRevision, working, restore }: Props) {
  const [before, setBefore] = useState<number | null>(null)
  const base = `${planEndpoint(projectId)}/history`
  const resource = useResource<PlanHistoryResponse>(before ? `${base}?before=${before}` : base)
  if (resource.error) return <Warning retry={() => resource.reload()}>{resource.error}</Warning>
  if (resource.loading || !resource.data) return <Busy>Reading saved versions…</Busy>
  const { versions, next_before: next } = resource.data
  return <>
    {versions.length > 0 ? <ul className="plan-versions">{versions.map(version => <li key={version.revision}>
      <div className="version-label"><strong>Revision {version.revision}</strong> <Badge tone={version.approved_at ? 'mint' : 'quiet'}>{version.approved_at ? 'Approved at save' : 'Previous draft'}</Badge><small>{dateLabel(version.saved_at)}</small></div>
      <div className="plan-primary-actions">
        {version.revision === activeRevision ? <small>Current plan</small> : version.can_restore ? <button type="button" className="button button-secondary button-small" disabled={working} onClick={() => restore(version.revision)}>Restore as draft</button> : <small>Reference only</small>}
        <a className="button button-secondary button-small" href={`${base}/${version.revision}`} download aria-label={`Download revision ${version.revision} as JSON`}><Download size={14} aria-hidden="true"/> JSON</a>
      </div>
    </li>)}</ul> : <p className="inline-empty">No snapshots yet. Approve the plan or replace a saved draft to keep a copy here.</p>}
    {(before || next) && <div className="plan-primary-actions version-pagination">{before && <button type="button" className="button button-secondary button-small" onClick={() => setBefore(null)}>Latest versions</button>}{next && <button type="button" className="button button-secondary button-small" onClick={() => setBefore(next)}>Older versions</button>}</div>}
  </>
}

export function PlanHistory(props: Props) {
  const [open, setOpen] = useState(false)
  return <details className="scene-details plan-history" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary><History size={15} aria-hidden="true"/> Saved versions</summary>
    {open && <div className="details-body"><p className="inline-empty">Koma saves a snapshot when you approve, regenerate, or restore a plan. A version can be restored to an active project when its story and profile match.</p><VersionList key={props.activeRevision} {...props}/></div>}
  </details>
}
