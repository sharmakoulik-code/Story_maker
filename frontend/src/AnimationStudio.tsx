import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, Clapperboard, Diamond, Film, FolderPlus, ImagePlus, Layers3, LockKeyhole, Plus, Save, Trash2 } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { describeError, useResource } from './api'
import { descendants, MotionInspector, type InspectorTab } from './MotionInspector'
import { MotionExport } from './MotionExport'
import { MotionStage } from './MotionStage'
import { MotionTimeline, MotionTransport } from './MotionTimeline'
import { defaultCamera, defaultPose, defaultShot, duration, fps, idFor, importAsset, loadBlueFlower, maxFrames, motionPage, motionPath, motionRoot, newSequence, saveSequence, shotFrames, sourceFrame, type Asset, type Layer, type Sequence, type SequenceSummary, type SequenceView, type Shot } from './motionApi'
import cover from './assets/blue-flower.webp'
import { Badge, Busy, PageHeading, useWarnUnsaved, useWorkspaceMode, Warning } from './ui'

export function AnimationLibrary() {
  const library = useResource<SequenceSummary[]>(motionRoot)
  const navigate = useNavigate()
  const [title,setTitle] = useState('')
  const [work,setWork] = useState(false)
  const [error,setError] = useState('')
  const sample = library.data?.find(item => item.sample)
  async function open(isSample: boolean) {
    if (isSample && sample) { navigate(motionPage(sample.id)); return }
    setWork(true);setError('')
    try { navigate(motionPage((isSample ? await loadBlueFlower() : await newSequence(title.trim() || 'Untitled animation')).id)) }
    catch (e) { setError(describeError(e));setWork(false) }
  }
  return <>
    <PageHeading label="04 / Motion and export" title="Animation Studio">Build motion from layered artwork. Review each shot, then render a local portrait MP4.</PageHeading>
    {error && <Warning>{error}</Warning>}
    <section className="motion-library-hero panel">
      <div className="motion-library-intro"><Badge tone="mint">Original animated short</Badge><h2>Blue Flower</h2><p>A forest traveler notices a light on the path. See her blink and reach without moving the camera, then cut into the bloom.</p><div className="motion-hero-facts"><span>03 shots</span><span>9.8 seconds</span><span>9:16</span></div><button type="button" className="button button-primary" disabled={work} onClick={() => void open(true)}><Clapperboard size={17}/> Open Blue Flower <ArrowRight size={15}/></button></div>
      <img src={cover} alt="Mina reaches toward a glowing blue flower in the forest"/>
    </section>
    <section className="panel motion-library-drafts"><div className="section-heading"><div><h2>Local timelines</h2><p>Use prepared PNG, JPEG, or WebP layers. Transparent artwork works best for character parts.</p></div></div>
      <form className="motion-new" onSubmit={event => { event.preventDefault(); void open(false) }}><label className="field"><span>Animation title</span><input autoComplete="off" value={title} placeholder="A new illustrated sequence" maxLength={100} onChange={event => setTitle(event.target.value)}/></label><button type="submit" disabled={work} className="button button-secondary"><Plus size={17}/> New animation</button></form>
      {library.loading && !library.data && <Busy>Loading timelines…</Busy>}{library.error && <Warning retry={() => library.reload()}>{library.error}</Warning>}
      {library.data?.map(item => <Link className="motion-library-row" key={item.id} to={motionPage(item.id)}><Film size={17}/><strong>{item.title}</strong><span>{item.shots} {item.shots === 1 ? 'shot' : 'shots'} · {duration(item.frames)}{item.sample ? ' · sample' : ''}</span><ArrowRight size={16}/></Link>)}
    </section>
  </>
}

function TimelineEditor({ initial }: { initial: SequenceView }) {
  const [saved,setSaved] = useState(initial)
  const [draft,setDraft] = useState<Sequence | null>(null)
  const [imported,setImported] = useState<Asset[]>([])
  const [cursor,setCursor] = useState(0)
  const [playing,setPlaying] = useState(false)
  const [rate,setRate] = useState(1)
  const [tab,setTab] = useState<InspectorTab>('layer')
  const [selected,setSelected] = useState('eyes')
  const [work,setWork] = useState(false)
  const [error,setError] = useState('')
  const [notice,setNotice] = useState('')
  const [addAsset,setAddAsset] = useState('')
  const dialog = useRef<HTMLDialogElement>(null)
  const file = useRef<HTMLInputElement>(null)
  const lastFrame = useRef(0)
  const mode = useWorkspaceMode()
  const doc = draft ?? saved.document
  const assets = useMemo(() => [...saved.assets,...imported], [saved.assets,imported])
  const total = doc.shots.reduce((sum,shot) => sum + shotFrames(shot),0)
  const frame = Math.min(total-1,cursor)
  let start = 0, index = 0
  while (index < doc.shots.length-1 && frame >= start + shotFrames(doc.shots[index])) { start += shotFrames(doc.shots[index]); index += 1 }
  const shot = doc.shots[index], local = frame-start
  const currentLayer = shot.layers.find(layer => layer.id === selected) ?? shot.layers.find(layer => layer.keys.length) ?? shot.layers.at(-1)
  const source = Math.round(sourceFrame(shot,local))
  const dirty = Boolean(draft)
  useWarnUnsaved(dirty,'Leave without saving the animation timeline?')
  lastFrame.current = frame
  useEffect(() => {
    if (!playing) return
    const initialFrame = lastFrame.current, began = performance.now()
    let request = 0
    function tick(now: number) {
      const at = initialFrame + Math.max(0,Math.floor((now-began)*fps*rate/1000))
      if (at >= total) { setCursor(total-1);setPlaying(false);return }
      setCursor(at)
      request = requestAnimationFrame(tick)
    }
    request = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(request)
  },[playing,rate,total])
  function seek(at: number) { setPlaying(false);setCursor(Math.min(total-1,Math.max(0,at))) }
  function toggle() { if (!playing && frame === total-1) setCursor(0);setPlaying(!playing) }
  function commit(next: Sequence, focus?: string, inShot = 0) {
    const count = next.shots.reduce((n,cut) => n+shotFrames(cut),0)
    if (count > maxFrames) { setError('This timeline supports up to 60 seconds after speed changes.');return }
    setDraft(next);setNotice('');setError('')
    if (focus) {
      let time = 0
      for (const cut of next.shots) { if (cut.id === focus) break; time += shotFrames(cut) }
      setCursor(time+inShot)
    } else setCursor(Math.min(frame,count-1))
  }
  function changeShot(patch: Partial<Shot>) {
    const updated = { ...shot,...patch }
    const next = { ...doc,shots:doc.shots.map(item => item.id===shot.id ? updated : item) }
    if (patch.speed !== undefined || patch.frames !== undefined) {
      commit(next,shot.id,Math.min(shotFrames(updated)-1,Math.round(sourceFrame(shot,local)/updated.speed)))
    } else commit(next)
  }
  const changeLayer = (patch: Partial<Layer>) => changeShot({layers:shot.layers.map(l => l.id===currentLayer?.id ? {...l,...patch} : l)})
  function selectTrack(view: InspectorTab, key?: string) { setTab(view);if (key && view === 'layer') setSelected(key) }
  function addLayer(asset?: Asset) {
    if (shot.layers.length >= 40) { setError('This shot supports up to 40 layers.');return }
    const id = idFor('layer')
    const layer: Layer = { id,name:asset?.name.slice(0,100) ?? 'Transform group',asset:asset?.id ?? null,parent:null,
      pivot_x:asset ? asset.width/4 : 0,pivot_y:asset ? asset.height/4 : 0,pose:asset ? {...defaultPose,x:270,y:480} : {...defaultPose},keys:[] }
    changeShot({layers:[...shot.layers,layer]});selectTrack('layer',id)
  }
  async function upload(image: File) {
    setWork(true);setError('')
    try { const asset = await importAsset(saved.id,image);setImported(old => [...old,asset]);addLayer(asset) }
    catch (e) {setError(describeError(e))}
    finally {setWork(false);if (file.current) file.current.value=''}
  }
  function removeLayer() {
    if (!currentLayer) return
    const ids = descendants(shot,currentLayer.id)
    if (!window.confirm(`Remove ${ids.size > 1 ? 'this layer and its children' : 'this layer'} from the shot? Artwork stays in the library.`)) return
    const camera = shot.camera.target && ids.has(shot.camera.target) ? { mode:'locked' as const,target:null,pose:{...defaultCamera},keys:[] } : shot.camera
    changeShot({layers:shot.layers.filter(item => !ids.has(item.id)),camera})
  }
  function moveLayer(direction: number) {
    const layers = [...shot.layers], from = layers.findIndex(item => item.id===currentLayer?.id), to = from+direction
    if (from<0 || to<0 || to>=layers.length) return
    ;[layers[from],layers[to]] = [layers[to],layers[from]]
    changeShot({layers})
  }
  function moveShot(direction: number) {
    const shots = [...doc.shots], at = index+direction
    if (at<0 || at>=shots.length) return
    ;[shots[index],shots[at]] = [shots[at],shots[index]]
    commit({...doc,shots},shot.id)
  }
  async function save() {
    if (!draft) return
    setWork(true);setError('');setPlaying(false)
    try {const changed = await saveSequence(saved.id,saved.revision,draft);setSaved(changed);setImported([]);setDraft(null);setNotice('Timeline saved on this device.')}
    catch(e) {setError(describeError(e))}
    finally {setWork(false)}
  }
  const locked = saved.sample ? doc.shots.findIndex(item => item.id === 'reach' && item.camera.mode === 'locked') : -1
  function jumpToBlink() {
    if (locked<0) return
    const cut = doc.shots[locked]
    seek(doc.shots.slice(0,locked).reduce((n,item) => n+shotFrames(item),0)+Math.min(shotFrames(cut)-1,Math.round(28/cut.speed)))
    selectTrack('layer','eyes')
  }
  return <div className="motion-editor">
    <Link to="/animation" className="back-link"><ArrowLeft size={16}/> Animation Studio</Link>
    <PageHeading label="04 / Motion and export" title={doc.title} actions={<div className="plan-primary-actions"><button type="button" className="button button-secondary" disabled={!dirty || work} onClick={() => void save()}><Save size={16}/> Save timeline</button><button type="button" className="button button-primary" onClick={() => {setPlaying(false);dialog.current?.showModal()}}><Film size={17}/> Export MP4</button></div>}>Animate layers independently and compose the camera separately.</PageHeading>
    {mode === 'preview' && <p className="motion-demo">Temporary demo workspace · Sample content only. Exports and edits reset with the sandbox.</p>}
    {error && <Warning>{error}</Warning>}{notice && <p className="notice notice-success" role="status">{notice}</p>}
    <div className="motion-banner"><div className="motion-banner-name"><span className="panel-symbol"><Clapperboard size={21}/></span><div><small>Animation timeline</small><strong>{saved.sample ? 'Original illustrated short' : 'Local sequence'}</strong></div></div>
      <div className="motion-facts"><div><small>Run time</small><strong>{duration(total)}</strong></div><div><small>Shots</small><strong>{String(doc.shots.length).padStart(2,'0')}</strong></div><div><small>Export</small><strong>1080 × 1920</strong></div><div><small>Frame rate</small><strong>30 <em>FPS</em></strong></div></div>
    </div>
    {locked>=0 && <div className="motion-proof"><LockKeyhole size={16}/><span><strong>Locked-camera check:</strong> Play shot {String(locked+1).padStart(2,'0')} to watch Mina blink and reach while the forest stays still.</span><button type="button" className="text-button" onClick={jumpToBlink}>Jump to blink <ArrowRight size={14}/></button></div>}
    <div className="motion-desk">
      <div className="motion-side">
        <section className="panel motion-shots" aria-label="Shot list"><div className="motion-panel-heading"><h2>Shots</h2><button type="button" title="Add shot" aria-label="Add shot" className="motion-icon" disabled={playing || work || doc.shots.length>=12} onClick={() => {const next=defaultShot(`Shot ${doc.shots.length+1}`);commit({...doc,shots:[...doc.shots,next]},next.id)}}><Plus size={16}/></button></div>
          {doc.shots.map((item,i) => <button key={item.id} className="motion-shot-item" type="button" aria-pressed={item.id===shot.id} onClick={() => seek(doc.shots.slice(0,i).reduce((n,cut) => n+shotFrames(cut),0))}><b>{String(i+1).padStart(2,'0')}</b><span><strong>{item.name}</strong><small>{duration(shotFrames(item))} · {item.camera.mode === 'locked' ? 'Locked camera' : item.camera.mode === 'tracking' ? 'Track' : 'Camera keys'}</small></span></button>)}
          <div className="motion-order"><button type="button" title="Move shot earlier" aria-label="Move shot earlier" disabled={playing || work || index===0} onClick={() => moveShot(-1)}><ArrowUp size={14}/></button><button type="button" title="Move shot later" aria-label="Move shot later" disabled={playing || work || index===doc.shots.length-1} onClick={() => moveShot(1)}><ArrowDown size={14}/></button><button type="button" title="Remove shot" aria-label="Remove shot" disabled={playing || work || doc.shots.length<=1} onClick={() => {if(window.confirm('Remove this shot from the timeline?')) {const shots = doc.shots.filter(item => item.id!==shot.id);commit({...doc,shots},shots[Math.min(index,shots.length-1)].id)}}}><Trash2 size={14}/></button></div>
        </section>
        <section className="panel motion-layers" aria-label="Shot layers"><div className="motion-panel-heading"><h2>Layers <small>{shot.layers.length}</small></h2><button type="button" title="Add transform group" aria-label="Add transform group" className="motion-icon" disabled={work || playing || shot.layers.length>=40} onClick={() => addLayer()}><FolderPlus size={16}/></button></div>
          <div className="motion-layer-list" tabIndex={0}>{[...shot.layers].reverse().map(layer => <button key={layer.id} type="button" aria-pressed={tab==='layer' && currentLayer?.id===layer.id} title={layer.name} className="motion-layer-item" onClick={() => selectTrack('layer',layer.id)}><Layers3 size={14}/><span>{layer.name}</span>{layer.keys.length>0 && <Diamond size={10} fill="currentColor"/>}</button>)}{!shot.layers.length && <p className="motion-help">Nothing on this stage yet.</p>}</div>
          <input hidden type="file" ref={file} aria-label="Layer image file" accept="image/png,image/jpeg,image/webp,.png,.jpg,.jpeg,.webp" onChange={e => {const f=e.target.files?.[0];if(f) void upload(f)}}/>
          <button type="button" className="button button-secondary button-small motion-import" disabled={work || playing || shot.layers.length>=40} onClick={() => file.current?.click()}><ImagePlus size={15}/> Import artwork</button>
          <details className="motion-extra"><summary>Add from library</summary><div className="motion-use-asset"><select aria-label="Saved artwork" value={addAsset} onChange={event => setAddAsset(event.target.value)}><option value="">Select artwork…</option>{assets.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select><button type="button" className="motion-icon" title="Add saved artwork" aria-label="Add saved artwork" disabled={!addAsset || work || playing || shot.layers.length>=40} onClick={() => { const asset = assets.find(item => item.id === addAsset);if (asset) addLayer(asset) }}><Plus size={16}/></button></div></details>
        </section>
      </div>
      <MotionStage shot={shot} next={doc.shots[index+1]} frame={local} globalFrame={frame} assets={assets}>
        <MotionTransport cursor={frame} total={total} playing={playing} rate={rate} seek={seek} toggle={toggle} setRate={setRate}/>
      </MotionStage>
      <MotionInspector tab={tab} onTab={setTab} shot={shot} layer={currentLayer} frame={source} localFrame={local} assets={assets} disabled={playing || work} update={changeShot} updateLayer={changeLayer} removeLayer={removeLayer} moveLayer={moveLayer}/>
      <MotionTimeline doc={doc} shot={shot} selected={tab==='camera' ? '$camera' : currentLayer?.id} cursor={frame} start={start} total={total} seek={seek} selectTrack={selectTrack}/>
    </div>
    <MotionExport dialog={dialog} id={saved.id} revision={saved.revision} dirty={dirty} hasArt={doc.shots.every(item => item.layers.some(layer => layer.asset))}/>
  </div>
}
export function AnimationPage() {
  const { id='' } = useParams()
  const resource = useResource<SequenceView>(motionPath(id))
  if (resource.error) return <><PageHeading label="Motion and export" title="Couldn’t open this timeline"/><Warning retry={() => resource.reload()}>{resource.error}</Warning><Link to="/animation" className="action-link">Back to Animation Studio <ArrowRight size={16}/></Link></>
  return resource.data ? <TimelineEditor key={id} initial={resource.data}/> : <Busy>Opening the animation timeline…</Busy>
}
