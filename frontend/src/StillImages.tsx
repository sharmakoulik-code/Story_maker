import { Archive, ArrowUpRight, Download, History, Image as ImageIcon, ImageUp } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { dateLabel, describeError, useResource } from './api'
import { Badge, Busy, Warning, useWorkspaceMode } from './ui'
import { imageBytes, imageUrl, maxImageBytes, type StillHistory, type StillVersion } from './visualApi'

export function StillImage({ version, alt, full = false, fallback = 'No image yet' }: {
  version?: StillVersion | null; alt: string; full?: boolean; fallback?: string;
}) {
  const [failed, setFailed] = useState<string | null>(null)
  if (!version?.available || version.id === failed) return <span className="still-empty"><ImageIcon size={25} aria-hidden="true"/><small>{version ? 'File unavailable' : fallback}</small></span>
  return <img src={imageUrl(version.id, !full)} alt={alt} loading={full ? 'eager' : 'lazy'} onError={() => setFailed(version.id)}/>
}

export function StillImport({ label, disabled, submit }: { label: string; disabled: boolean; submit: (body: FormData) => Promise<void> }) {
  const [open, setOpen] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const preview = useWorkspaceMode() === 'preview'
  function close() { setOpen(false); setError('') }
  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (disabled || uploading) return
    const form = new FormData(event.currentTarget)
    const file = form.get('image')
    if (!(file instanceof File) || !file.size) { setError('Choose a still image to import.'); return }
    if (file.size > maxImageBytes) { setError('Choose a file of 16 MiB or less.'); return }
    setUploading(true); setError('')
    try { await submit(form); close() }
    catch (problem) { setError(describeError(problem)) }
    finally { setUploading(false) }
  }
  if (!open) return <button type="button" className="button button-secondary button-small" disabled={disabled} onClick={() => setOpen(true)}><ImageUp size={15} aria-hidden="true"/> {label}</button>
  return <form className="still-import" onSubmit={send}>
    <fieldset className="plan-fields" disabled={disabled || uploading}>
      <label className="field"><span>Still image file</span><input name="image" type="file" accept="image/png,image/jpeg,image/webp,.png,.jpg,.jpeg,.webp" required /></label>
      <small>PNG, JPEG or WebP · up to 16 MiB and 12 megapixels. The source file is not modified.</small>
      {preview && <small>Files you select are copied to the temporary demo sandbox. Use non-personal test images only.</small>}
      <div className="two-fields plot-fields"><label className="field"><span>Asset source</span><input name="source" maxLength={300} placeholder="e.g. My illustration" spellCheck={false} autoComplete="off"/></label>
        <label className="field"><span>License or usage rights</span><input name="license_note" maxLength={300} placeholder="e.g. My original work" spellCheck={false} autoComplete="off"/></label></div>
      <div className="plan-primary-actions"><button type="submit" className="button button-primary button-small"><ImageUp size={15} aria-hidden="true"/> Save local image</button><button type="button" className="button button-secondary button-small" onClick={close}>Cancel import</button></div>
    </fieldset>
    {uploading && <Busy>Reading and saving the image locally…</Busy>}
    {error && <Warning>{error}</Warning>}
  </form>
}

export function StillCredit({ version }: { version: StillVersion }) {
  return <div className="still-credit"><strong>{version.original_name}</strong><span>{version.width} × {version.height} · {imageBytes(version.bytes)}</span><small>{version.source} · {version.license_note}</small></div>
}

interface HistoryProps {
  path: string
  activeId: string | null
  count: number
  epoch?: number
  choose?: (id: string) => void
  disabled?: boolean
  label?: string
}

function HistoryContent({ path, activeId, choose, disabled }: HistoryProps) {
  const [before, setBefore] = useState<number | null>(null)
  const resource = useResource<StillHistory>(before ? `${path}?before=${before}` : path)
  if (resource.error) return <Warning retry={() => resource.reload()}>{resource.error}</Warning>
  if (!resource.data || resource.loading) return <Busy>Reading local versions…</Busy>
  const { versions, next_before } = resource.data
  return <>
    {versions.length ? <ol className="still-versions">{versions.map(version => <li key={version.id}>
      <div className="version-thumb"><StillImage version={version} alt="" /></div>
      <div className="version-copy"><div><strong>Version {version.number}</strong> {version.id === activeId && <Badge tone="mint">Active</Badge>}</div><StillCredit version={version}/><small>{dateLabel(version.created_at)}{version.last_approved_at ? ' · Previously approved' : ''}</small></div>
      <div className="version-actions">
        {version.available && <a className="button button-small button-secondary icon-only" href={`${imageUrl(version.id)}?download=true`} download aria-label={`Download version ${version.number}`}><Download size={14} aria-hidden="true"/></a>}
        {choose && version.id !== activeId && <button type="button" className="button button-small button-secondary" disabled={disabled || !version.available} onClick={() => choose(version.id)}>Use version {version.number}</button>}
      </div>
    </li>)}</ol> : <p className="inline-empty">No reference images are saved yet.</p>}
    {(before || next_before) && <div className="plan-primary-actions version-pagination">{before && <button type="button" className="button button-secondary button-small" onClick={() => setBefore(null)}>Latest versions</button>}{next_before && <button type="button" className="button button-secondary button-small" onClick={() => setBefore(next_before)}>Older versions</button>}</div>}
  </>
}

export function StillVersions(props: HistoryProps) {
  const [expanded, setExpanded] = useState(false)
  return <details className="scene-details still-history" onToggle={event => setExpanded(event.currentTarget.open)}>
    <summary><History size={15} aria-hidden="true"/> {props.label ?? 'Image versions'} <span className="version-count">{props.count}</span></summary>
    {expanded && <div className="details-body"><HistoryContent key={`${props.path}-${props.epoch ?? 0}`} {...props}/></div>}
  </details>
}

export function OpenStill({ version, children = 'Open full image' }: { version: StillVersion; children?: string }) {
  if (!version.available) return null
  return <a className="button button-secondary button-small" href={imageUrl(version.id)} target="_blank" rel="noreferrer"><ArrowUpRight size={14} aria-hidden="true"/> {children}</a>
}

export function ImageCountBadge({ count }: { count: number }) {
  return <Badge><Archive size={13} aria-hidden="true"/> {count} {count === 1 ? 'version' : 'versions'}</Badge>
}
