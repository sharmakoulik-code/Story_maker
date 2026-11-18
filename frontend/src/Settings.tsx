import { Check, Cpu, FolderOpen, HardDrive, LoaderCircle, Monitor, RefreshCw, Save } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { api, describeError, size, useResource, type HardwareReport, type MediaTool, type SettingsView } from './api'
import { WorkstationMetrics } from './Dashboard'
import { Badge, Busy, PageHeading, Warning, useWarnUnsaved } from './ui'

function ToolRow({ name, tool }: { name: string; tool: MediaTool }) {
  return <div className="engine-row"><div className="min-w-0"><strong>{name}{tool.version && <small> · {tool.version}</small>}</strong>{tool.path && <span title={tool.path}>{tool.path}</span>}</div><Badge tone={tool.state === 'ready' ? 'mint' : tool.state === 'error' ? 'amber' : 'quiet'}>{tool.state === 'ready' ? 'Detected' : tool.state === 'error' ? 'Probe failed' : 'Not found'}</Badge></div>
}

function Devices({ report }: { report: HardwareReport }) {
  return <>
    <div className="device-strip"><span className="panel-symbol"><Monitor size={20} aria-hidden="true"/></span><div><strong>{report.os}</strong><p>{report.architecture || 'Architecture not reported'} · Checked {new Date(report.checked_at).toLocaleTimeString()}</p></div><Badge tone="mint"><Cpu size={13} aria-hidden="true"/> CPU-first mode</Badge></div>
    <WorkstationMetrics hardware={report}/>
    <div className="settings-grid">
      <section className="panel system-panel" aria-labelledby="device-title">
        <div className="panel-heading"><span className="panel-symbol"><Cpu size={19} aria-hidden="true"/></span><div><h2 id="device-title">Hardware details</h2><p>Reported by the operating system.</p></div></div>
        <dl className="device-list">
          <div><dt>Processor</dt><dd>{report.cpu.name ?? 'Unknown'}</dd></div>
          <div><dt>CPU cores</dt><dd>{report.cpu.physical_cores ?? 'Unknown'} physical · {report.cpu.logical_cores ?? 'Unknown'} logical</dd></div>
          <div><dt>System memory</dt><dd>{size(report.memory.available_bytes)} available / {size(report.memory.total_bytes)} total</dd></div>
          <div><dt>Graphics</dt><dd>{report.gpus.length ? <ul>{report.gpus.map((gpu, index) => <li key={index}>{gpu.name}<small>{gpu.memory_bytes === null ? 'GPU memory not reported' : `${size(gpu.memory_bytes)} · ${gpu.memory_source ?? 'Reported memory'}`}</small></li>)}</ul> : 'No graphics adapter detected'}</dd></div>
        </dl>
        <p className="system-note">Acceleration isn’t enabled in this release, even if an adapter is detected.</p>
      </section>
      <section className="panel system-panel" aria-labelledby="media-title">
        <div className="panel-heading"><span className="panel-symbol panel-symbol-lilac"><HardDrive size={19} aria-hidden="true"/></span><div><h2 id="media-title">Media tools & local engines</h2><p>Detection only. No models are downloaded.</p></div></div>
        <ToolRow name="FFmpeg" tool={report.media.ffmpeg}/><ToolRow name="FFprobe" tool={report.media.ffprobe}/>
        {report.media.ffmpeg.state === 'ready' && <div className="feature-list" aria-label="FFmpeg capabilities">{Object.entries({ h264: 'libx264', aac: 'AAC', subtitles: 'libass filter' }).map(([key, label]) => { const result = report.media.features[key as keyof HardwareReport['media']['features']]; return <Badge key={key} tone={result === true ? 'mint' : result === false ? 'amber' : 'quiet'}>{label}: {result === true ? 'yes' : result === false ? 'no' : 'unknown'}</Badge> })}</div>}
        {report.engines.map(engine => <div className="engine-row" key={engine.name}><div><strong>{engine.name}{engine.version && <small> · {engine.version}</small>}</strong></div><Badge tone={engine.state === 'missing' ? 'quiet' : 'lilac'}>{engine.state === 'responding' ? 'Loopback responds' : engine.state === 'installed' ? 'Executable found' : 'Not detected'}</Badge></div>)}
        <details className="tool-help"><summary>How to configure FFmpeg</summary><p>Install a trusted Windows build that includes both executables, libx264, AAC and libass. Add its bin folder to PATH, or set the two paths below. Restart the studio after updating PATH.</p></details>
        <p className="system-note">The runtime check doesn’t verify models or voices. Generation is not enabled.</p>
      </section>
    </div>
  </>
}

const paths = [
  { key: 'projects_dir', label: 'Projects folder', hint: 'Applies to new projects only.' },
  { key: 'models_dir', label: 'Models folder', hint: 'Optional model files for later phases.' },
  { key: 'outputs_dir', label: 'Outputs folder', hint: 'Default destination for future exports.' },
  { key: 'logs_dir', label: 'Logs folder', hint: 'Reserved for future job logs.' },
  { key: 'ffmpeg_path', label: 'FFmpeg executable', hint: 'Leave blank to detect it on PATH.' },
  { key: 'ffprobe_path', label: 'FFprobe executable', hint: 'Leave blank to detect it on PATH.' },
] as const

function WorkspacePaths({ initial, report, saved }: { initial: SettingsView; report: HardwareReport | null; saved: () => void }) {
  const [settings, setSettings] = useState(initial)
  const [values, setValues] = useState(settings.values)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [working, setWorking] = useState(false)
  const dirty = paths.some(({ key }) => values[key] !== settings.values[key])
  useWarnUnsaved(settings.editable && dirty && !working, 'Leave without saving changes to these paths?')
  async function save(event: FormEvent) {
    event.preventDefault()
    if (!settings.editable || !dirty || working) return
    setWorking(true); setError(null); setNotice(null)
    try {
      const next = await api<SettingsView>('/api/settings', { method: 'PUT', body: JSON.stringify(values) })
      setSettings(next); setValues(next.values); setNotice('Local paths saved. Existing projects were not moved.'); saved()
    } catch (error) { setError(describeError(error)) } finally { setWorking(false) }
  }
  return <section className="panel settings-paths" aria-labelledby="paths-title">
    <div className="panel-heading"><span className="panel-symbol"><FolderOpen size={20} aria-hidden="true"/></span><div><h2 id="paths-title">Workspace paths</h2><p>Use folders on the local disk rather than network or synced folders.</p></div></div>
    <div className="data-root"><span>DATA ROOT</span><code>{settings.data_dir}</code></div>
    {!settings.editable && <p className="demo-note">Device paths are read-only in the demo. Use the Windows application to edit them.</p>}
    <form onSubmit={save}>
      <fieldset className="paths-grid" disabled={!settings.editable || working}>
        {paths.map(({ key, label, hint }) => <label className="field" key={key}><span>{label}</span><input value={values[key]} onChange={event => { setValues({ ...values, [key]: event.target.value }); setNotice(null) }} placeholder={key.endsWith('_path') ? 'Auto-detect on PATH' : undefined} required={key.endsWith('_dir')} spellCheck={false} maxLength={4096}/><small>{hint}{report && key === 'projects_dir' ? ` ${size(report.storage.projects.free_bytes)} free at the saved location.` : report && key === 'models_dir' ? ` ${size(report.storage.models.free_bytes)} free at the saved location.` : report && key === 'outputs_dir' ? ` ${size(report.storage.outputs.free_bytes)} free at the saved location.` : ''}</small></label>)}
      </fieldset>
      {error && <Warning>{error}</Warning>}
      {notice && <div className="notice notice-success" role="status"><Check size={18} aria-hidden="true"/>{notice}</div>}
      {settings.editable && <div className="settings-actions"><button type="button" className="button button-secondary" disabled={working} onClick={() => { setValues(settings.defaults); setNotice(null); setError(null) }}>Use defaults</button><button type="submit" className="button button-primary" disabled={working || !dirty}>{working ? <LoaderCircle size={17} className="spinner" aria-hidden="true"/> : <Save size={17} aria-hidden="true"/>}{working ? 'Saving…' : 'Save settings'}</button></div>}
    </form>
  </section>
}

export function SystemSettings() {
  const hardware = useResource<HardwareReport>('/api/hardware')
  const settings = useResource<SettingsView>('/api/settings')
  const refresh = () => hardware.reload('/api/hardware?refresh=true')
  return <>
    <PageHeading label="Device preferences" title="System & models" actions={<button type="button" className="button button-secondary" onClick={refresh} disabled={hardware.loading}><RefreshCw size={16} aria-hidden="true" className={hardware.loading ? 'spinner' : undefined}/> Refresh diagnostics</button>}>
      Check what this device can run and where your work lives.
    </PageHeading>
    {settings.data && !settings.data.editable && <p className="demo-note">These readings are for the Linux demo sandbox, not your Windows computer.</p>}
    {hardware.error && <Warning retry={refresh}>{hardware.error}</Warning>}
    {hardware.loading && !hardware.data && <Busy>Checking local hardware and tools…</Busy>}
    {hardware.data && <Devices report={hardware.data}/>}
    {settings.error && <Warning retry={() => settings.reload()}>{settings.error}</Warning>}
    {settings.loading && !settings.data && <Busy>Reading workspace settings…</Busy>}
    {settings.data && <WorkspacePaths initial={settings.data} report={hardware.data} saved={refresh}/>}
  </>
}
