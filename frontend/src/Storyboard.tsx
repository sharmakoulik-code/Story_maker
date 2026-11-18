import { ArrowLeft, Camera, Check, CheckCheck, Clock3, Film, ImageOff, Images, ListVideo, Plus, Save, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, describeError, useResource } from './api'
import { ProjectSteps } from './PlanChrome'
import { limits, newScene, planEndpoint, planPage, stamp, type Scene } from './planApi'
import { ScenePlanEditor } from './ScenePlanEditor'
import { ImageCountBadge, OpenStill, StillCredit, StillImage, StillImport, StillVersions } from './StillImages'
import { Badge, Busy, PageHeading, Warning, useWarnUnsaved, useWorkspaceMode } from './ui'
import { boardPath, imageUrl, jsonMutation, shotLabels, shotPath, type BoardShot, type ShotStatus, type StoryboardView } from './visualApi'

const shotTone: Record<ShotStatus, 'quiet' | 'mint' | 'lilac' | 'amber'> = { empty: 'quiet', review: 'lilac', approved: 'mint', changed: 'amber', missing: 'amber' }
const selectable = (shot?: BoardShot) => shot?.status === 'review' || shot?.status === 'changed'
const padded = (index: number) => String(index).padStart(2, '0')

function FrameStatus({ shot }: { shot?: BoardShot }) {
  const status = shot?.status ?? 'empty'
  return <Badge tone={shotTone[status]}><span className="status-dot"/>{shotLabels[status]}</Badge>
}

function CastReference({ image, name }: { image: string; name: string }) {
  const [failed, setFailed] = useState(false)
  if (failed) return <span className="pinned-missing" title="Pinned reference file unavailable"><ImageOff size={14} aria-label="Pinned reference file unavailable"/></span>
  return <a href={imageUrl(image)} target="_blank" rel="noreferrer" aria-label={`Open reference for ${name}`}><img src={imageUrl(image, true)} alt="" loading="lazy" onError={() => setFailed(true)}/></a>
}

function BoardWorkspace({ initial, reload }: { initial: StoryboardView; reload: () => void }) {
  const [data, setData] = useState(initial)
  const [edits, setEdits] = useState<Scene[] | null>(null)
  const [selection, select] = useState('')
  const [batch, setBatch] = useState<string[]>([])
  const [tab, setTab] = useState<'frame' | 'details'>('frame')
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const { plan: { plan, project, has_story } } = data
  const scenes = edits ?? plan?.document.scenes ?? []
  const scene = scenes.find(item => item.id === selection) ?? scenes[0]
  const number = scene ? scenes.indexOf(scene) + 1 : 0
  const byScene = new Map(data.shots.map(item => [item.scene_id, item]))
  const shot = scene ? byScene.get(scene.id) : undefined
  const frame = shot?.active
  const locked = Boolean(project.archived_at || plan?.status === 'stale')
  const canEdit = Boolean(plan && !busy && !locked)
  const canReview = canEdit && !edits && plan?.status === 'approved'
  const canImport = canEdit && !edits
  const readyIds = scenes.filter(item => selectable(byScene.get(item.id))).map(item => item.id)
  const selectedForReview = readyIds.filter(id => batch.includes(id))
  const runningTime = scenes.reduce((total, item) => total + item.duration_seconds, 0)
  const approvedCount = scenes.filter(item => byScene.get(item.id)?.status === 'approved').length
  const frameCount = scenes.filter(item => byScene.get(item.id)?.active?.available).length
  const mode = useWorkspaceMode()
  useWarnUnsaved(Boolean(edits) && !busy, 'Leave without saving the storyboard scene edits?')

  function clearDraft() {
    if (!edits || window.confirm('Discard unsaved scene edits and reload the saved storyboard?')) reload()
  }
  async function run(command: () => Promise<StoryboardView>, notice: string, propagate = false) {
    setBusy(true); setError(''); setMessage('')
    try { setData(await command()); setEdits(null); setBatch([]); setMessage(notice) }
    catch (problem) { if (propagate) throw problem; setError(describeError(problem)) }
    finally { setBusy(false) }
  }
  function save() {
    if (!plan || !edits || !canEdit) return
    void run(async () => {
      await jsonMutation(planEndpoint(project.id), 'PUT', { revision: plan.revision, document: { ...plan.document, scenes: edits } })
      return api<StoryboardView>(boardPath(project.id))
    }, 'Scene edits saved. Review the Story plan before approving new frames.')
  }
  function review(ids: string[], approved: boolean) {
    if (!plan || !canEdit || edits || (approved && !canReview) || !ids.length) return
    const targets = ids.map(id => ({ scene_id: id, revision: byScene.get(id)?.revision ?? 0 }))
    void run(() => jsonMutation(`${boardPath(project.id)}/review`, 'POST', { plan_revision: plan.revision, approved, targets }),
      approved ? (ids.length === 1 ? 'Frame approved.' : `${ids.length} frames approved.`) : 'Frame reopened for review.')
  }
  function add() {
    if (!canEdit || scenes.length >= limits.scenes) return
    const inserted = newScene(scenes.length + 1)
    setEdits([...scenes, inserted]); select(inserted.id); setTab('details')
  }
  function update(patch: Partial<Scene>) {
    if (canEdit && scene) setEdits(scenes.map(item => item.id === scene.id ? { ...item, ...patch } : item))
  }
  function move(offset: number) {
    const target = number - 1 + offset
    if (!canEdit || !scene || target < 0 || target >= scenes.length) return
    const ordered = scenes.filter(item => item.id !== scene.id)
    ordered.splice(target, 0, scene)
    setEdits(ordered)
  }
  function remove() {
    if (!canEdit || !scene || scenes.length === 1 || !window.confirm(`Remove “${scene.title}” from this sequence? Its saved images will be kept off the board.`)) return
    const next = scenes.filter(item => item.id !== scene.id)
    select(next[Math.min(number - 1, next.length - 1)].id)
    setEdits(next)
  }
  function selectFrame(imageId: string) {
    if (!scene || !shot || !plan || !canImport) return
    void run(() => jsonMutation(`${shotPath(project.id, scene.id)}/frame`, 'PUT', { plan_revision: plan.revision, shot_revision: shot.revision, image_id: imageId }),
      'Image version selected. Review this frame again before approving it.')
  }

  return <>
    <div className="project-back"><Link to="/projects"><ArrowLeft size={16} aria-hidden="true"/> My projects</Link></div>
    <PageHeading label="03 / Visual development" title="Storyboard" actions={plan && <div className="plan-primary-actions">
      {edits && <button type="button" className="button button-primary" disabled={!canEdit} onClick={save}><Save size={17} aria-hidden="true"/> Save scene edits</button>}
      {!locked && <button type="button" className="button button-secondary" disabled={!canReview || !selectedForReview.length} onClick={() => review(selectedForReview, true)}><CheckCheck size={17} aria-hidden="true"/> Approve selected{selectedForReview.length ? ` (${selectedForReview.length})` : ''}</button>}
    </div>}>{project.title} · Import a still for each scene, then review what goes into the sequence.</PageHeading>
    <ProjectSteps project={project}/>
    {mode === 'preview' && <p className="demo-note">Temporary demo · Use sample images only. The preview library resets when the server restarts.</p>}
    {locked && <div className="plan-notice">{project.archived_at ? 'This project is archived. Restore it from Story draft to edit the board.' : 'The story or preferences changed. Open Story plan to update the plan before editing frames.'}</div>}
    {plan && !locked && plan.status !== 'approved' && <div className="board-hint"><ShieldCheck size={17} aria-hidden="true"/><span>You can import stills now. <Link to={planPage(project.id)}>Approve the Story plan</Link> before approving frames.</span></div>}
    {error && <Warning>{error}<div><button type="button" className="text-button" onClick={clearDraft}>Reload saved board</button></div></Warning>}
    {message && <div className="notice notice-success" role="status"><Check size={18} aria-hidden="true"/>{message}</div>}
    {busy && <Busy>Saving to the local workspace…</Busy>}
    {edits && <div className="plan-notice">Unsaved scene edits. Save them before importing, switching or approving frame versions.</div>}
    {!plan && <section className="panel board-start"><span className="panel-symbol panel-symbol-lilac"><Film size={23} aria-hidden="true"/></span><h2>{has_story ? 'Make a plan before framing the story' : 'Start with a story'}</h2><p>Each saved scene becomes a storyboard card. You’ll see its versions and approval status here.</p><Link className="button button-primary" to={has_story ? planPage(project.id) : `/projects/${project.id}`}>{has_story ? 'Open story plan' : 'Write the draft'}</Link></section>}
    {plan && scene && <>
      <section className="board-banner" aria-label="Storyboard summary">
        <div className="board-banner-title"><span className="board-banner-icon"><Film size={21} aria-hidden="true"/></span><div><p className="eyebrow">Visual sequence</p><h2>Review the frames</h2></div></div>
        <div className="board-stats"><div><span>Scenes</span><strong>{padded(scenes.length)}</strong></div><div><span>Frames ready</span><strong>{frameCount}<small> / {scenes.length}</small></strong></div><div><span>Approved stills</span><strong>{approvedCount}<small> / {scenes.length}</small></strong></div><div><span>Planned runtime</span><strong>{stamp(runningTime)}</strong></div></div>
      </section>
      <div className="storyboard-layout">
        <section className="panel shot-deck" aria-labelledby="deck-heading">
          <div className="deck-heading"><div className="panel-heading"><span className="panel-symbol panel-symbol-lilac"><ListVideo size={19} aria-hidden="true" /></span><div><h2 id="deck-heading">Scene sequence</h2><p>Pick a card to preview and review its still.</p></div></div>
            {canEdit && <button type="button" className="button button-secondary button-small" onClick={add} disabled={scenes.length >= limits.scenes}><Plus size={15} aria-hidden="true"/> Add scene</button>}
          </div>
          {canReview && readyIds.length > 0 && <div className="batch-caption"><button type="button" className="text-button" onClick={() => setBatch(selectedForReview.length === readyIds.length ? [] : readyIds)}>{selectedForReview.length === readyIds.length ? 'Clear selection' : 'Select pending frames'}</button><small>{selectedForReview.length} selected</small></div>}
          <ol className="shot-grid">{scenes.map((item, index) => {
            const stored = byScene.get(item.id)
            const checked = batch.includes(item.id)
            return <li key={item.id} className={`shot-card${item.id === scene.id ? ' shot-card-selected' : ''}`}>
              <button type="button" className="shot-card-pick" aria-pressed={item.id === scene.id} aria-label={`Select scene ${index + 1}: ${item.title}`} onClick={() => select(item.id)}>
                <span className="shot-card-image"><StillImage version={stored?.active} alt="" fallback="No frame yet"/><span className="shot-number">{padded(index + 1)}</span><span className="shot-length"><Clock3 size={11} aria-hidden="true"/>{item.duration_seconds}s</span></span>
                <span className="shot-card-title">{item.title || 'Unnamed scene'}</span>
              </button>
              <div className="shot-card-status"><FrameStatus shot={stored}/>{checked && canReview && <Check size={13} aria-hidden="true"/>}</div>
              {canReview && selectable(stored) && <label className="shot-checkbox"><input type="checkbox" aria-label={`Select scene ${index + 1} for approval`} checked={checked} onChange={event => setBatch(previous => event.target.checked ? [...previous, item.id] : previous.filter(id => id !== item.id))}/> Select for approval</label>}
            </li>
          })}</ol>
          <div className="deck-footer"><Images size={15} aria-hidden="true"/> {mode === 'preview' ? 'This demo keeps stills in a temporary library.' : 'Imports and approvals stay on this device.'} A replacement never overwrites its earlier version.</div>
        </section>
        <div className="shot-desk">
          <div className="filter-group inspector-tabs" role="group" aria-label="Shot inspector">
            <button type="button" className={tab === 'frame' ? 'filter-active' : ''} aria-pressed={tab === 'frame'} onClick={() => setTab('frame')}><Camera size={14} aria-hidden="true"/> Frame &amp; versions</button>
            <button type="button" className={tab === 'details' ? 'filter-active' : ''} aria-pressed={tab === 'details'} onClick={() => setTab('details')}><ListVideo size={14} aria-hidden="true"/> Scene details</button>
          </div>
          {tab === 'details' ? <ScenePlanEditor key={scene.id} scene={scene} bible={plan.document.bible} number={number} count={scenes.length} metric={plan.timing.scenes.find(item => item.scene_id === scene.id)} source={plan.source.excerpts[scene.id]} editable={canEdit} change={update} move={move} remove={remove}/> :
            <section className="panel frame-inspector" aria-labelledby="frame-title">
              <div className="inspector-heading"><div><p className="eyebrow">Scene {padded(number)} · still preview</p><h2 id="frame-title">{scene.title}</h2></div><FrameStatus shot={shot}/></div>
              <div className="frame-view"><div className="frame-display"><StillImage full version={frame} alt={`Frame for ${scene.title}`} fallback="No still imported"/></div><div className="frame-info">
                {frame ? <><Badge tone="lilac">Imported · v{frame.number}</Badge><StillCredit version={frame}/>{frame.available && Math.abs(frame.width / frame.height - 9 / 16) > .02 && <small>Not 9:16 · shown uncropped</small>}
                  <OpenStill version={frame}/></> : <p>Import an illustration or a local test image. This board doesn’t generate new art.</p>}
                {shot?.status === 'changed' && <p>The saved visual direction changed. Compare it with this image before reapproving.</p>}
                {shot?.status === 'approved' ? <button type="button" className="button button-secondary button-small" disabled={!canImport} onClick={() => review([scene.id], false)}>Reopen frame</button> : frame?.available && <button type="button" className="button button-primary button-small" disabled={!canReview} onClick={() => review([scene.id], true)}><Check size={16} aria-hidden="true"/> Approve frame</button>}
              </div></div>
              {!locked && <StillImport key={`import-${scene.id}`} label={frame ? 'Replace frame' : 'Import frame'} disabled={!canImport} submit={body => {
                body.set('plan_revision', String(plan.revision)); body.set('shot_revision', String(shot?.revision ?? 0))
                return run(() => api(`${shotPath(project.id, scene.id)}/frames`, { method: 'POST', body }), 'Still imported. Earlier versions and other scenes are unchanged.', true)
              }}/>}
              {shot && shot.version_count > 0 && <StillVersions key={`versions-${scene.id}`} path={`${shotPath(project.id, scene.id)}/frames`} activeId={frame?.id ?? null} count={shot.version_count} epoch={shot.revision} disabled={!canImport} choose={locked ? undefined : selectFrame}/>}
              <div className="frame-cast"><h3>Cast references</h3>{scene.cast.length ? <ul>{scene.cast.map(entry => {
                const person = plan.document.bible.characters.find(character => character.id === entry.character_id)
                if (!person) return null
                const pinned = person.library_pin?.image_id
                return <li key={person.id}>{pinned && <CastReference key={pinned} image={pinned} name={person.name}/>}<span><strong>{person.name}</strong><small>{[entry.emotion, pinned ? 'Pinned reference' : 'Text design'].filter(Boolean).join(' · ')}</small></span></li>
              })}</ul> : <p className="inline-empty">No cast linked to this scene.</p>}</div>
            </section>}
        </div>
      </div>
      {data.off_board_count > 0 && <details className="scene-details off-board">
        <summary>Off-board images <span className="version-count">{data.off_board_count}</span></summary>
        <div className="details-body"><p className="inline-empty">Frames from removed or replaced scenes. They’re not in the active sequence. To bring back a compatible sequence, use Saved versions in the <Link to={planPage(project.id)}>Story plan</Link>.</p>
          {data.off_board_count > data.off_board.length && <p className="inline-empty">Showing {data.off_board.length} most recent off-board shots.</p>}
          <div className="off-board-grid">{data.off_board.map(item => <article className="bible-entry" key={item.scene_id}><div className="off-board-title"><strong>{item.title}</strong><ImageCountBadge count={item.version_count}/></div><StillVersions label="Browse images" path={`${shotPath(project.id, item.scene_id)}/frames`} count={item.version_count} activeId={null}/></article>)}</div>
        </div>
      </details>}
    </>}
  </>
}

export function StoryboardPage() {
  const { id = '' } = useParams()
  const resource = useResource<StoryboardView>(boardPath(id))
  if (resource.loading) return <Busy>Opening the storyboard…</Busy>
  if (resource.error) return <><PageHeading label="Visual development" title="Couldn’t open this storyboard"/><Warning retry={() => resource.reload()}>{resource.error}</Warning></>
  return resource.data ? <BoardWorkspace key={id} initial={resource.data} reload={() => resource.reload()} /> : null
}
