import { ArrowLeft, ArrowUpRight, BookOpen, Check, CheckCheck, Clock3, Film, ListVideo, LoaderCircle, RotateCcw, Save, Sparkles, Timer } from 'lucide-react'
import { useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { api, describeError, formatDuration, languageNames, styleNames, useResource } from './api'
import { ArcEditor, BibleEditor } from './BibleEditor'
import { boardPage } from './visualApi'
import { ProjectSteps } from './PlanChrome'
import { PlanHistory } from './PlanHistory'
import { covers } from './Projects'
import { SceneList, ScenePlanEditor } from './ScenePlanEditor'
import { generatePlan, limits, newScene, planEndpoint, planLabels, stamp, type PlanDocument, type PlanView, type SavedPlan, type Scene } from './planApi'
import { Badge, Busy, PageHeading, Warning, useWarnUnsaved, useWorkspaceMode } from './ui'

const tabs = [
  { key: 'scenes', label: 'Scene plan', icon: ListVideo },
  { key: 'bible', label: 'Story Bible', icon: BookOpen },
  { key: 'analysis', label: 'Story analysis', icon: Film },
] as const

type Job = 'generate' | 'save' | 'approve' | 'fit' | 'adopt' | 'restore'

function TimingBoard({ plan, document, dirty, selected, select }: { plan: SavedPlan; document: PlanDocument; dirty: boolean; selected: string; select: (id: string) => void }) {
  const { timing, source } = plan
  const total = document.scenes.reduce((value, item) => value + item.duration_seconds, 0)
  const clipped = source.source_beats - source.spoken_beats
  return <section className="timing-board" aria-labelledby="timing-heading">
    <div className="timing-top"><div><p className="eyebrow">Pacing desk</p><h2 id="timing-heading">Review timing</h2></div><Badge tone={dirty ? 'lilac' : timing.can_approve ? 'mint' : 'amber'}><Clock3 size={14} aria-hidden="true"/>{dirty ? 'Save to check timing' : timing.can_approve ? 'Fits the target' : 'Needs review'}</Badge></div>
    <div className="timing-stats"><div><span>Sequence length</span><strong>{stamp(total)} <small>/ {stamp(timing.target_seconds)}</small></strong></div><div><span>Scenes</span><strong>{String(document.scenes.length).padStart(2, '0')}</strong></div><div><span>Saved spoken words</span><strong>{timing.spoken_words}</strong></div></div>
    <div className="timing-strip" role="group" aria-label="Scene durations">{document.scenes.map((scene, index) => <button type="button" key={scene.id} aria-pressed={scene.id === selected} aria-label={`View scene ${index + 1}, ${scene.duration_seconds} seconds`} title={`${scene.title} · ${scene.duration_seconds}s`} onClick={() => select(scene.id)} style={{ flexGrow: Math.max(1, scene.duration_seconds) }}>
      <span>{String(index + 1).padStart(2, '0')}</span><small>{scene.duration_seconds}s</small>
    </button>)}</div>
    <p className="timing-foot"><span>{languageNames[plan.profile.language]} · {timing.words_per_minute} words/min with pauses</span><span>Estimates, not measured audio</span></p>
    {!dirty && timing.issues.length > 0 && <ul className="timing-notices issues" aria-label="Timing issues">{timing.issues.map(note => <li key={note}>{note}</li>)}</ul>}
    {clipped > 0 && <p className="timing-notices">Initial compression: {clipped} of {source.source_beats} source beats weren’t added to the spoken script. The original story is unchanged. Review the scene excerpts for anything you want to restore.</p>}
    {!dirty && timing.cautions.length > 0 && <details className="scene-details timing-details"><summary>Planning notes ({timing.cautions.length})</summary><ul className="timing-notices">{timing.cautions.map(note => <li key={note}>{note}</li>)}</ul></details>}
  </section>
}

function Workspace({ initial, initialError, reload }: { initial: PlanView; initialError?: string; reload: () => void }) {
  const [view, setView] = useState(initial)
  const [document, setDocument] = useState<PlanDocument | null>(initial.plan?.document ?? null)
  const [tab, setTab] = useState<typeof tabs[number]['key']>('scenes')
  const [selection, select] = useState('')
  const [work, setWork] = useState<Job | null>(null)
  const [error, setError] = useState(initial.plan ? null : initialError ?? null)
  const [notice, setNotice] = useState<string | null>(null)
  const mode = useWorkspaceMode()
  const { project, plan } = view
  const archived = Boolean(project.archived_at)
  const stale = plan?.status === 'stale'
  const dirty = Boolean(plan && document && plan.document !== document)
  const editable = !archived && !stale && !work
  const selected = document?.scenes.find(item => item.id === selection) ?? document?.scenes[0]
  const sceneNumber = document && selected ? document.scenes.indexOf(selected) + 1 : 0
  useWarnUnsaved(dirty && !work && !stale && !archived, 'Leave without saving your story plan changes?')

  async function run(job: Job, command: () => Promise<PlanView>, message: string) {
    if (work) return
    setWork(job); setError(null); setNotice(null)
    try {
      const updated = await command()
      setView(updated); setDocument(updated.plan?.document ?? null); setNotice(message)
      if (job === 'generate' || job === 'restore') { select(''); setTab('scenes'); window.scrollTo(0, 0) }
    } catch (error) { setError(describeError(error)) }
    finally { setWork(null) }
  }
  function generate() {
    if (archived || !view.has_story || work) return
    if (plan && !window.confirm(`Generate a fresh plan from the saved story? The previous saved revision will be kept under Saved versions.${dirty ? ' Unsaved edits will be discarded.' : ''}`)) return
    void run('generate', () => generatePlan(project.id, plan?.revision ?? null), 'Plan generated locally. Review the script and suggested references.')
  }
  function save(fit = false) {
    if (!editable || !plan || !document) return
    void run(fit ? 'fit' : 'save', () => api<PlanView>(planEndpoint(project.id), { method: 'PUT', body: JSON.stringify({ revision: plan.revision, document, fit_duration: fit }) }),
      fit ? 'Scene lengths were fitted to the target. No spoken lines were removed.' : 'Plan saved. Timing has been checked.')
  }
  function approval(approved: boolean) {
    if (!editable || !plan || dirty || (approved && !plan.timing.can_approve)) return
    void run('approve', () => api<PlanView>(`${planEndpoint(project.id)}/approval`, { method: 'PUT', body: JSON.stringify({ revision: plan.revision, approved }) }),
      approved ? 'Story plan approved. No media jobs were started.' : 'Plan reopened for review.')
  }
  function adoptTarget() {
    if (!plan || !view.can_adopt_target) return
    void run('adopt', () => api<PlanView>(`${planEndpoint(project.id)}/target`, { method: 'PUT', body: JSON.stringify({ revision: plan.revision }) }),
      'New target applied without changing the script. Use Fit to target or adjust scene lengths before approving again.')
  }
  function restoreVersion(version: number) {
    if (!plan || archived || work) return
    if (!window.confirm(`Restore revision ${version} as a draft? The current saved plan will be kept under Saved versions.${dirty ? ' Unsaved edits will be discarded.' : ''}`)) return
    void run('restore', () => api<PlanView>(`${planEndpoint(project.id)}/restore`, { method: 'PUT', body: JSON.stringify({ revision: plan.revision, version }) }),
      `Revision ${version} restored as a draft. Review it before approving again.`)
  }
  function updateScene(patch: Partial<Scene>) {
    if (!editable || !selected) return
    setDocument(current => current && ({ ...current, scenes: current.scenes.map(item => item.id === selected.id ? { ...item, ...patch } : item) }))
  }
  function addScene() {
    if (!editable || !document || document.scenes.length >= limits.scenes) return
    const scene = newScene(document.scenes.length + 1)
    setDocument({ ...document, scenes: [...document.scenes, scene] }); select(scene.id)
  }
  function moveScene(direction: number) {
    if (!editable || !document || !sceneNumber) return
    const next = sceneNumber - 1 + direction
    if (next < 0 || next >= document.scenes.length) return
    const scenes = [...document.scenes]
    const [scene] = scenes.splice(sceneNumber - 1, 1)
    scenes.splice(next, 0, scene)
    setDocument({ ...document, scenes })
  }
  function removeScene() {
    if (!editable || !document || !selected || document.scenes.length < 2 || !window.confirm(`Remove scene “${selected.title}” from this plan?`)) return
    const scenes = document.scenes.filter(item => item.id !== selected.id)
    select(scenes[Math.min(sceneNumber - 1, scenes.length - 1)].id)
    setDocument({ ...document, scenes })
  }
  function removeReference(kind: 'characters' | 'locations' | 'props', id: string, name: string) {
    if (!editable || !document || !window.confirm(`Remove “${name}” and unlink it from this plan’s scenes?`)) return
    const bible = { ...document.bible, [kind]: document.bible[kind].filter(entry => entry.id !== id) }
    const scenes = document.scenes.map(scene => kind === 'characters' ? { ...scene, cast: scene.cast.filter(item => item.character_id !== id), dialogue: scene.dialogue.map(line => line.character_id === id ? { ...line, character_id: null, speaker: name } : line) }
      : kind === 'locations' ? { ...scene, location_id: scene.location_id === id ? null : scene.location_id } : { ...scene, prop_ids: scene.prop_ids.filter(key => key !== id) })
    setDocument({ ...document, bible, scenes })
  }

  return <>
    <div className="project-back"><Link to="/projects"><ArrowLeft size={16} aria-hidden="true"/> My projects</Link></div>
    <PageHeading label="02 / Story development" title="Story plan" actions={plan && !archived && !stale ? <div className="plan-primary-actions">
      <button type="button" className="button button-secondary" disabled={!editable || !dirty} onClick={() => save()}>{work === 'save' ? <LoaderCircle className="spinner" size={16} aria-hidden="true" /> : <Save size={16} aria-hidden="true"/>} Save plan</button>
      <button type="button" className="button button-primary" disabled={!editable || dirty || (plan.status !== 'approved' && !plan.timing.can_approve)} onClick={() => approval(plan.status !== 'approved')} title={dirty ? 'Save changes first' : !plan.timing.can_approve ? 'Resolve timing issues first' : undefined}>
        {work === 'approve' ? <LoaderCircle size={16} className="spinner" aria-hidden="true"/> : <CheckCheck size={17} aria-hidden="true"/>}{plan.status === 'approved' ? 'Reopen for review' : 'Approve plan'}</button>
    </div> : undefined}>{project.title} · Review the plan before starting any media work.</PageHeading>
    <ProjectSteps project={project}/>
    {mode === 'preview' && <p className="demo-note">This is a temporary demo. Use sample content only.</p>}
    {error && <Warning>{error}<div className="mt-1"><button className="text-button" type="button" onClick={() => { if (!dirty || window.confirm('Discard unsaved changes and reload the saved plan?')) reload() }}>Reload saved plan</button></div></Warning>}
    {notice && <div role="status" className="notice notice-success"><Check size={18} aria-hidden="true"/>{notice}</div>}
    {plan?.status === 'approved' && !archived && !dirty && <div className="board-hint"><Film size={16} aria-hidden="true"/><span>Plan approved. <Link to={boardPage(project.id)}>Open the storyboard</Link> to import and review your frames.</span></div>}
    {archived && <p className="plan-notice">Archived project. Restore it from the <Link to={`/projects/${project.id}`}>story draft</Link> before editing the plan.</p>}
    {stale && <div className="plan-notice plan-stale"><div><strong>Saved draft changed</strong><p>This plan is kept for reference, but isn’t approved for the current story or preferences. Review it before replacing it.</p></div>{!archived && <div className="plan-primary-actions">
      {view.can_adopt_target && <button type="button" className="button button-primary" disabled={Boolean(work)} onClick={adoptTarget}>{work === 'adopt' ? 'Applying…' : `Keep script & use ${formatDuration(project.profile.duration_seconds)} target`}</button>}
      <button type="button" className="button button-secondary" disabled={!view.has_story || Boolean(work)} onClick={generate}>{work === 'generate' ? 'Planning…' : 'Regenerate from saved draft'}</button>
    </div>}</div>}
    {!plan && <section className="plan-start panel">
      <div className="plan-start-copy"><Badge tone="mint"><Sparkles size={14} aria-hidden="true" /> Local planner</Badge><h2>Break your story into scenes.</h2><p>Get a starter Story Bible, a plot outline and a timed script for your {formatDuration(project.profile.duration_seconds)} target. Review and edit the suggestions before approval.</p>
        <div className="plan-primary-actions"><button className="button button-primary" type="button" onClick={generate} disabled={archived || !view.has_story || Boolean(work)}>{work === 'generate' ? <LoaderCircle className="spinner" size={17} aria-hidden="true"/> : <Sparkles size={17} aria-hidden="true"/>}{work === 'generate' ? 'Planning…' : 'Generate story plan'}</button><Link to={`/projects/${project.id}`} className="button button-secondary">{view.has_story ? 'Review draft' : 'Add story text'} <ArrowUpRight size={15} aria-hidden="true"/></Link></div>
        <small>{languageNames[project.profile.language]} · {styleNames[project.profile.style]} · No AI model or image processing required</small></div>
      <div className={`plan-start-art art-${project.profile.style}`}><img src={covers[project.profile.style]} alt="" /></div>
    </section>}
    {plan && document && selected && <>
      <TimingBoard plan={plan} document={document} dirty={dirty} selected={selected.id} select={id => { select(id); setTab('scenes') }}/>
      <div className="plan-toolbar"><div className="filter-group" role="group" aria-label="Plan editors">{tabs.map(({ key, label, icon: Icon }) => <button type="button" key={key} aria-pressed={tab === key} className={tab === key ? 'filter-active' : ''} onClick={() => setTab(key)}><Icon size={15} aria-hidden="true"/>{label}</button>)}</div>
        {editable && <button type="button" className="button button-secondary button-small" onClick={() => save(true)} title="Rebalance the scene lengths without changing your script"><Timer size={15} aria-hidden="true"/> Fit to target</button>}{work === 'fit' && <Busy>Checking timing…</Busy>}
      </div>
      {tab === 'scenes' && <div className="scene-plan-grid"><SceneList scenes={document.scenes} plan={plan} selected={selected.id} select={select} add={addScene} editable={editable}/><ScenePlanEditor key={selected.id} scene={selected} bible={document.bible} number={sceneNumber} count={document.scenes.length} metric={plan.timing.scenes.find(item => item.scene_id === selected.id)} source={plan.source.excerpts[selected.id]} editable={editable} change={updateScene} move={moveScene} remove={removeScene}/></div>}
      {tab === 'bible' && <BibleEditor bible={document.bible} editable={editable} change={bible => setDocument({ ...document, bible })} remove={removeReference}/>}
      {tab === 'analysis' && <ArcEditor arc={document.analysis} editable={editable} change={analysis => setDocument({ ...document, analysis })}/>}
      <div className="plan-footer"><div><Badge tone={plan.status === 'approved' ? 'mint' : stale ? 'amber' : 'lilac'}>{planLabels[plan.status]}</Badge><p>{dirty ? 'Unsaved edits. Save to refresh timing and automatic prompts.' : 'Rule-based suggestions. No images, voices or video are generated in this stage.'}</p></div>
        <div className="plan-primary-actions">{!archived && !stale && <button className="button button-secondary button-small" disabled={Boolean(work) || !view.has_story} type="button" onClick={generate}><RotateCcw size={14} aria-hidden="true"/>{work === 'generate' ? 'Planning…' : 'Regenerate plan'}</button>}{editable && dirty && <button type="button" className="button button-primary button-small" onClick={() => save()}><Save size={15} aria-hidden="true"/> Save plan</button>}</div>
      </div>
      <PlanHistory projectId={project.id} activeRevision={plan.revision} working={Boolean(work)} restore={restoreVersion}/>
    </>}
  </>
}

export function StoryPlanPage() {
  const { id = '' } = useParams()
  const { state } = useLocation()
  const resource = useResource<PlanView>(planEndpoint(id))
  const [epoch, setEpoch] = useState(0)
  if (resource.loading) return <Busy>Opening the production plan…</Busy>
  if (resource.error) return <><PageHeading label="Story development" title="Couldn’t open the story plan"/><Warning retry={() => resource.reload()}>{resource.error}</Warning></>
  if (!resource.data) return null
  return <Workspace key={`${id}-${epoch}`} initial={resource.data} initialError={epoch === 0 && typeof state?.planError === 'string' ? state.planError : undefined} reload={() => { setEpoch(value => value + 1); resource.reload() }} />
}
