import { useEffect, useRef, useState, type RefObject } from 'react'
import { Clapperboard, Download, Film, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api, describeError, useResource, type HardwareReport } from './api'
import { activeJob, duration, exportPath, json, videoUrl, type EncoderMode, type ExportJob } from './motionApi'
import { Badge, Busy, Warning } from './ui'

export function MotionExport({ dialog, id, revision, dirty, hasArt }: { dialog: RefObject<HTMLDialogElement | null>; id: string; revision: number; dirty: boolean; hasArt: boolean }) {
  const jobs = useResource<ExportJob[]>(exportPath(id))
  const hardware = useResource<HardwareReport>('/api/hardware')
  const [mode,setMode] = useState<EncoderMode>('auto')
  const [latest,setLatest] = useState<ExportJob | null>(null)
  const [watch,setWatch] = useState<string | null>(null)
  const [work,setWork] = useState(false)
  const [error,setError] = useState('')
  const [playError,setPlayError] = useState(false)
  const reloadRef = useRef(jobs.reload)
  reloadRef.current = jobs.reload
  const rows = latest ? [latest,...(jobs.data ?? []).filter(job => job.id !== latest.id)] : jobs.data ?? []
  const running = rows.find(activeJob)
  const runningId = running?.id
  useEffect(() => {
    if (!runningId) return
    let open = true, busy = false
    const timer = window.setInterval(async () => {
      if (busy) return
      busy = true
      try {
        const next = await api<ExportJob>(exportPath(id,runningId))
        if (!open) return
        setLatest(next); setError('')
        if (!activeJob(next)) reloadRef.current()
      } catch (e) { if (open) setError(describeError(e)) }
      finally { busy = false }
    },750)
    return () => { open = false; window.clearInterval(timer) }
  }, [id,runningId])
  const ready = hardware.data?.media.ffmpeg.state === 'ready' && hardware.data?.media.ffprobe.state === 'ready'
  async function run(cancel?: string) {
    setWork(true); setError('')
    try {
      const next = cancel ? await api<ExportJob>(`${exportPath(id,cancel)}/cancel`, {method:'POST'}) : await api<ExportJob>(exportPath(id),json('POST',{revision,mode}))
      setLatest(next)
      reloadRef.current()
    } catch (e) { setError(describeError(e)) }
    finally { setWork(false) }
  }
  return <dialog className="motion-export" ref={dialog} aria-labelledby="motion-export-title" onClose={() => { setWatch(null); setPlayError(false) }}>
    <div className="motion-export-top"><span className="panel-symbol"><Clapperboard size={20}/></span><div><p className="eyebrow">Local renderer</p><h2 id="motion-export-title">Export MP4</h2></div><button type="button" className="motion-icon" aria-label="Close export" onClick={() => dialog.current?.close()}><X size={19}/></button></div>
    <div className="motion-export-spec"><Badge tone="mint">H.264</Badge><span>1080 × 1920</span><span>30 FPS</span><span>9:16 · silent</span></div>
    {hardware.loading && !hardware.data && <Busy>Checking local video tools…</Busy>}
    {hardware.data && !ready && <Warning>Export needs FFmpeg and FFprobe. Install a local build with libx264 and set the executable paths in <Link to="/settings">System & models</Link>. Preview and editing still work.</Warning>}
    {hardware.error && <Warning retry={() => hardware.reload()}>{hardware.error}</Warning>}
    {error && <Warning>{error}</Warning>}
    {dirty && <p className="motion-help">Save timeline edits before exporting a new revision.</p>}
    {!hasArt && <p className="motion-help">Add artwork to every shot before exporting.</p>}
    <div className="motion-export-controls"><label className="field motion-field"><span>Encoding</span><select value={mode} disabled={Boolean(running)} onChange={event => setMode(event.target.value as EncoderMode)}><option value="auto">Auto / hardware when verified</option><option value="software">Software / libx264</option></select></label><button type="button" className="button button-primary" disabled={!ready || Boolean(running) || dirty || !hasArt || work} onClick={() => void run()}><Film size={16}/> Render MP4</button></div>
    {watch && <div className="motion-export-player"><video controls playsInline preload="metadata" aria-label="Exported MP4" src={videoUrl(id,watch)} onError={() => setPlayError(true)}/>{playError && <Warning>This browser couldn't decode the MP4. Download it to play in your local media player.</Warning>}</div>}
    <div className="motion-exports" aria-label="Local exports">
      {!rows.length && <p className="motion-help">No exports yet. Render the saved timeline to your configured Outputs folder.</p>}
      {jobs.error && <Warning retry={() => jobs.reload()}>{jobs.error}</Warning>}
      {rows.slice(0,8).map(job => <article key={job.id} className="motion-job">
        <div><Badge tone={job.state==='complete' ? 'mint' : job.state==='failed' ? 'amber' : 'quiet'}>{job.state === 'complete' ? 'Complete' : job.state}</Badge><strong>{job.filename}</strong></div>
        <p>{job.message} · {duration(job.frames)} · revision {job.revision}{job.encoder ? ` · ${job.encoder}` : ''}</p>
        {activeJob(job) && <div className="motion-progress"><progress aria-label="Render progress" max={job.frames} value={job.done}/><small>{job.done}/{job.frames} frames</small><button type="button" className="button button-secondary button-small" disabled={work || job.state==='cancelling'} onClick={() => void run(job.id)}>Cancel render</button></div>}
        {job.state==='complete' && <><div className="motion-job-actions"><button type="button" className="button button-secondary button-small" onClick={() => { setPlayError(false); setWatch(job.id) }}>Watch export</button><a className="button button-secondary button-small" href={`${videoUrl(id,job.id)}?download=true`}><Download size={14}/> Download MP4</a></div>{job.output_path && <code className="motion-output-path">{job.output_path}</code>}</>}
      </article>)}
    </div>
  </dialog>
}
