import { Archive, ArchiveRestore, ArrowLeft, ArrowRight, Check, Clapperboard, FileText, Folder, Image, LoaderCircle, RectangleVertical, Save, Sparkles, Upload } from 'lucide-react'
import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, dateLabel, describeError, languageNames, resolutionNames, standardProfile, styleNames, useResource, type Draft, type Profile, type Project, type Style } from './api'
import { covers } from './Projects'
import { ProjectSteps } from './PlanChrome'
import { generatePlan, planPage } from './planApi'
import { Badge, Busy, PageHeading, Warning, useWarnUnsaved, useWorkspaceMode } from './ui'

const durationOptions = [[30, '30 seconds'], [60, '60 seconds'], [90, '90 seconds'], [120, '2 minutes'], [180, '3 minutes']] as const
const maxStory = 100_000

async function readStory(file: File) {
  if (!file.name.toLowerCase().endsWith('.txt')) throw new Error('Choose a .txt file.')
  if (file.size > 404_000) throw new Error('This file is too large. Keep the draft to 100,000 characters.')
  const bytes = new Uint8Array(await file.arrayBuffer())
  const encoding = bytes[0] === 0xff && bytes[1] === 0xfe ? 'utf-16le'
    : bytes[0] === 0xfe && bytes[1] === 0xff ? 'utf-16be' : 'utf-8'
  let story: string
  try {
    story = new TextDecoder(encoding, { fatal: true }).decode(bytes)
    if (story.includes('\0')) throw new Error('Invalid plain text')
  } catch {
    throw new Error('This file is not valid plain text. Save it as UTF-8 or UTF-16 with a byte order mark and try again.')
  }
  if (story.length > maxStory) throw new Error('Keep the draft to 100,000 characters.')
  return story
}

function DraftEditor({ initial, isNew = false, archived = false, locked = false, onSave, onGenerate, onDirty }: {
  initial: Draft; isNew?: boolean; archived?: boolean; locked?: boolean;
  onSave: (draft: Draft) => Promise<void>; onGenerate?: (draft: Draft) => Promise<void>; onDirty?: (dirty: boolean) => void;
}) {
  const [draft, setDraft] = useState(initial)
  const [custom, setCustom] = useState(!durationOptions.some(([seconds]) => seconds === initial.profile.duration_seconds))
  const [saving, setSaving] = useState<'save' | 'plan' | null>(null)
  const [importing, setImporting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [imported, setImported] = useState<string | null>(null)
  const upload = useRef<HTMLInputElement>(null)
  const disabled = archived || Boolean(saving) || locked
  const words = draft.story.trim() ? draft.story.trim().split(/\s+/u).length : 0
  const changed = draft.title !== initial.title || draft.story !== initial.story || JSON.stringify(draft.profile) !== JSON.stringify(initial.profile)
  useEffect(() => { onDirty?.(changed) }, [changed, onDirty])
  useWarnUnsaved(changed && !archived && !saving && !locked, 'Leave without saving this draft?')
  function profile<K extends keyof Profile>(key: K, value: Profile[K]) {
    setDraft(previous => ({ ...previous, profile: { ...previous.profile, [key]: value } }))
  }
  async function importFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file || disabled || importing) return
    if (draft.story.trim() && !window.confirm('Replace the current draft text with this file?')) return
    setError(null)
    setImported(null)
    setImporting(true)
    try {
      const story = await readStory(file)
      setDraft(previous => ({ ...previous, title: previous.title || file.name.replace(/\.txt$/i, '').trim().slice(0, 120), story }))
      setImported(`Imported ${file.name}`)
    } catch (error) { setError(describeError(error)) } finally { setImporting(false) }
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (disabled || importing) return
    const title = draft.title.trim()
    setError(null)
    if (!title) { setError('Enter a project title.'); return }
    const choice = ((event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null)?.value
    if (choice === 'plan' && !draft.story.trim()) { setError('Enter story text to generate a plan.'); return }
    const shouldPlan = choice === 'plan' && onGenerate
    setSaving(shouldPlan ? 'plan' : 'save')
    try { await (shouldPlan || onSave)({ ...draft, title }) }
    catch (error) { setError(describeError(error)) }
    finally { setSaving(null) }
  }
  const selected = draft.profile
  return <form className="draft-form" onSubmit={submit}>
    <div className="draft-grid">
      <section className="panel story-panel" aria-labelledby="script-heading">
        <div className="panel-heading"><span className="panel-symbol"><FileText size={20} aria-hidden="true"/></span><div><h2 id="script-heading">Story draft</h2><p>Set down the story you want to tell.</p></div></div>
        <fieldset disabled={disabled} className="form-fields">
          <label className="field"><span>Project title</span><input name="title" placeholder="e.g. Lanterns After Dusk" value={draft.title} onChange={event => setDraft({ ...draft, title: event.target.value })} maxLength={120} required autoComplete="off" spellCheck={false} /></label>
          <div className="field story-field">
            <div className="field-top"><label htmlFor="draft-story">Story text <span className="optional-label">Optional</span></label>
              {!archived && <><input type="file" accept=".txt,text/plain" aria-label="Choose a TXT file" ref={upload} onChange={importFile} hidden/><button type="button" className="button button-small button-secondary" onClick={() => upload.current?.click()} disabled={importing}><Upload size={14} aria-hidden="true"/>{importing ? 'Reading…' : 'Import TXT'}</button></>}
            </div>
            <textarea name="story" id="draft-story" className="story-input" value={draft.story} onChange={event => { setDraft({ ...draft, story: event.target.value }); setImported(null) }} placeholder="Begin with a place, a character, or a moment that changes everything…" maxLength={maxStory} rows={13} spellCheck={false} autoComplete="off" />
            <div className="story-count"><span role="status">{imported ?? `${words.toLocaleString()} ${words === 1 ? 'word' : 'words'}`}</span><span>{draft.story.length.toLocaleString()} / {maxStory.toLocaleString()} characters</span></div>
          </div>
        </fieldset>
      </section>
      <aside className="draft-side">
        <section className="panel preferences-panel" aria-labelledby="prefs-heading">
          <div className="panel-heading"><span className="panel-symbol panel-symbol-lilac"><Clapperboard size={20} aria-hidden="true"/></span><div><h2 id="prefs-heading">Production preferences</h2><p>Saved with your draft.</p></div></div>
          <fieldset disabled={disabled} className="form-fields">
            <div className="two-fields">
              <label className="field"><span>Target duration</span><select value={custom ? 'custom' : String(selected.duration_seconds)} onChange={event => { const next = event.target.value; setCustom(next === 'custom'); if (next !== 'custom') profile('duration_seconds', Number(next)) }}>{durationOptions.map(([seconds, label]) => <option key={seconds} value={seconds}>{label}</option>)}<option value="custom">Custom</option></select></label>
              <label className="field"><span>Narration language</span><select value={selected.language} onChange={event => profile('language', event.target.value as Profile['language'])}>{Object.entries(languageNames).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
            </div>
            {custom && <label className="field"><span>Custom duration in seconds</span><input type="number" min={10} max={900} required value={selected.duration_seconds || ''} onChange={event => profile('duration_seconds', Number(event.target.value))}/><small>Between 10 and 900 seconds.</small></label>}
            <label className="field"><span>Visual style</span><select value={selected.style} onChange={event => profile('style', event.target.value as Style)}>{Object.entries(styleNames).map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
            <div className={`style-cover art-${selected.style}`}><img src={covers[selected.style]} alt="" /><span><Image size={13} aria-hidden="true"/> Style artwork</span></div>
            <div className="two-fields">
              <label className="field"><span>Resolution</span><select value={selected.resolution} onChange={event => profile('resolution', event.target.value as Profile['resolution'])}>{Object.entries(resolutionNames).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
              <label className="field"><span>Frame rate</span><select value={selected.fps} onChange={event => profile('fps', Number(event.target.value) as Profile['fps'])}><option value={24}>24 FPS</option><option value={18}>18 FPS</option><option value={15}>15 FPS</option></select></label>
            </div>
            <div className="field"><span id="animation-label">Animation intensity</span><div className="choice-row" role="group" aria-labelledby="animation-label">{(['subtle', 'balanced', 'expressive'] as const).map(value => <button type="button" key={value} aria-pressed={value === selected.animation} onClick={() => profile('animation', value)}>{value}</button>)}</div></div>
          </fieldset>
        </section>
        <div className="canvas-note"><RectangleVertical size={21} aria-hidden="true"/><div><strong>Vertical canvas · 9:16</strong><p>Generate a timed story plan when your draft is ready. Planning does not create images or audio.</p></div></div>
      </aside>
    </div>
    {error && <Warning>{error}</Warning>}
    <div className="form-footer">
      <span className="form-hint">{archived ? 'Restore the project to edit it.' : changed ? 'Unsaved changes' : isNew ? 'Title is required. You can add the story later.' : 'Saved to the project library'}</span>
      <div className="form-actions">
        <Link className="button button-secondary" to="/projects">{isNew ? 'Cancel' : 'Back to projects'}</Link>
        {!archived && <button className={`button ${onGenerate ? 'button-secondary' : 'button-primary'}`} type="submit" value="save" disabled={disabled || importing || (!isNew && !changed)}>
          {saving === 'save' ? <LoaderCircle size={17} className="spinner" aria-hidden="true"/> : !isNew && <Save size={17} aria-hidden="true"/>}
          {saving === 'save' ? 'Saving…' : isNew ? 'Create project' : 'Save draft'}{isNew && !saving && <ArrowRight size={17} aria-hidden="true"/>}</button>}
        {!archived && onGenerate && <button className="button button-primary" type="submit" value="plan" disabled={disabled || importing || !draft.story.trim()}>
          {saving === 'plan' ? <LoaderCircle size={17} className="spinner" aria-hidden="true"/> : <Sparkles size={17} aria-hidden="true"/>}{saving === 'plan' ? 'Planning…' : 'Generate story plan'}</button>}
      </div>
    </div>
  </form>
}

export function NewStory() {
  const navigate = useNavigate()
  const mode = useWorkspaceMode()
  return <>
    <PageHeading label="01 / Story development" title="New story">Start a new draft and set the direction for your video.</PageHeading>
    {mode === 'preview' && <p className="demo-note">You’re in the temporary demo. Use a sample story, not personal content.</p>}
    <DraftEditor initial={{ title: '', story: '', profile: standardProfile }} isNew onSave={async draft => {
      const project = await api<Project>('/api/projects', { method: 'POST', body: JSON.stringify(draft) })
      navigate(`/projects/${project.id}`, { replace: true })
    }} onGenerate={async draft => {
      const project = await api<Project>('/api/projects', { method: 'POST', body: JSON.stringify(draft) })
      let planError: string | undefined
      try { await generatePlan(project.id) } catch (error) { planError = describeError(error) }
      navigate(planPage(project.id), { replace: true, state: { planError } })
    }}/>
  </>
}

function OpenStory({ initial }: { initial: Project }) {
  const navigate = useNavigate()
  const [project, setProject] = useState(initial)
  const [notice, setNotice] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [working, setWorking] = useState(false)
  const [dirty, setDirty] = useState(false)
  const mode = useWorkspaceMode()
  const endpoint = `/api/projects/${project.id}`
  const archived = Boolean(project.archived_at)
  async function archive() {
    if (dirty && !window.confirm('Archive this project and discard unsaved edits?')) return
    setWorking(true)
    setNotice(null)
    setActionError(null)
    try {
      const changed = await api<Project>(`${endpoint}/archive`, { method: 'PUT', body: JSON.stringify({ archived: !archived }) })
      setProject(changed)
      setNotice(archived ? 'Project restored.' : 'Project archived. Its story and files are unchanged.')
    } catch (error) { setActionError(describeError(error)) } finally { setWorking(false) }
  }
  return <>
    <div className="project-back"><Link to="/projects"><ArrowLeft size={16} aria-hidden="true"/> My projects</Link></div>
    <PageHeading label="01 / Story development" title={project.title} actions={<button className="button button-secondary" type="button" onClick={archive} disabled={working}>{archived ? <ArchiveRestore size={17} aria-hidden="true"/> : <Archive size={17} aria-hidden="true"/>}{archived ? 'Restore project' : 'Archive project'}</button>}>
      <div className="project-header-meta"><Badge tone={archived ? 'amber' : 'mint'}><span className="status-dot" />{archived ? 'Archived' : 'Draft'}</Badge><span>Updated {dateLabel(project.updated_at)}</span></div>
    </PageHeading>
    <ProjectSteps project={project}/>
    {mode === 'preview' && <p className="demo-note">Use sample content only. The temporary demo library resets when the preview restarts.</p>}
    {notice && <div className="notice notice-success" role="status"><Check size={18} aria-hidden="true"/>{notice}</div>}
    {actionError && <Warning>{actionError}</Warning>}
    <DraftEditor key={project.updated_at} initial={{ title: project.title, story: project.story, profile: project.profile }} archived={archived} locked={working} onDirty={setDirty} onSave={async draft => {
      const saved = await api<Project>(endpoint, { method: 'PUT', body: JSON.stringify(draft) })
      setProject(saved)
      setNotice(saved.plan_status === 'stale' ? 'Draft saved. The existing story plan is now out of date.' : 'Draft saved.')
    }} onGenerate={project.plan_status === 'not_started' ? async draft => {
      const saved = await api<Project>(endpoint, { method: 'PUT', body: JSON.stringify(draft) })
      let planError: string | undefined
      try { await generatePlan(saved.id) } catch (error) { planError = describeError(error) }
      navigate(planPage(saved.id), { state: { planError } })
    } : undefined}/>
    <details className="project-location"><summary><Folder size={16} aria-hidden="true"/> {project.folder_exists ? 'Project folder' : 'Project folder is missing'}</summary><code>{project.folder}</code><p>The draft itself is stored in SQLite. This folder is reserved for your project media.</p></details>
  </>
}

export function StoryProject() {
  const { id } = useParams()
  const project = useResource<Project>(`/api/projects/${encodeURIComponent(id ?? '')}`)
  if (project.error) return <><PageHeading label="Project library" title="Couldn’t open this project"/><Warning retry={() => project.reload()}>{project.error}</Warning><Link className="button button-secondary" to="/projects"><ArrowLeft size={16} aria-hidden="true"/> My projects</Link></>
  if (!project.data) return <Busy>Opening the story draft…</Busy>
  return <OpenStory key={project.data.id} initial={project.data}/>
}
