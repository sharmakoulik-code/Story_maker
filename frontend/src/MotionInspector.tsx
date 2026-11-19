import { ArrowDown, ArrowUp, Diamond, Focus, LockKeyhole, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Badge } from './ui'
import { defaultCamera, duration, fps, shotFrames, type Asset, type Camera, type CameraPose, type Ease, type Key, type Layer, type Pose, type Shot } from './motionApi'
import { evaluateFrame, sample } from './motionMath'

export type InspectorTab = 'layer' | 'camera' | 'shot'
const clamp = (n: number, lo: number, hi: number) => Math.min(hi, Math.max(lo,n))
const display = (n: number) => String(Number(n.toFixed(3)))

function NumberField({ label, value, onValue, min, max, step = 1 }: { label: string; value: number; onValue: (n: number) => void; min: number; max: number; step?: number }) {
  const [edit,setEdit] = useState<string | null>(null)
  return <label className="field motion-field"><span>{label}</span><input type="number" min={min} max={max} step={step} value={edit ?? display(value)} onFocus={() => setEdit(display(value))}
    onChange={event => setEdit(event.target.value)} onBlur={() => { if (edit?.trim() && Number.isFinite(Number(edit)) && Number(edit) !== Number(display(value))) onValue(clamp(Number(edit),min,max)); setEdit(null) }}
    onKeyDown={event => { if (event.key === 'Enter') event.currentTarget.blur() }}/></label>
}

function authored<T extends Pose | CameraPose>(base: T, keys: Key<T>[], frame: number, patch: Partial<T>, force = false, easing?: Ease): { pose: T; keys: Key<T>[] } {
  const state = { ...sample(base,keys,frame), ...patch }
  if (!force && frame === 0 && keys.length === 0) return { pose: state, keys }
  const key = { ...state, frame, ease: easing ?? keys.find(key => key.frame === frame)?.ease ?? 'smooth' }
  return { pose: base, keys: [...keys.filter(key => key.frame !== frame), key].sort((a,b) => a.frame-b.frame) }
}

function KeyTools({ keys, frame, onKey, remove }: { keys: { frame: number; ease: Ease }[]; frame: number; onKey: (ease?: Ease) => void; remove: () => void }) {
  const existing = keys.find(key => key.frame === frame)
  return <div className="motion-key-tools">
    <div className="motion-key-row"><span><Diamond size={13}/> Source frame {frame}</span><Badge tone={existing ? 'mint' : 'quiet'}>{existing ? 'Keyed' : `${keys.length} keys`}</Badge></div>
    <div className="motion-key-actions"><button className="button button-secondary button-small" type="button" disabled={!existing && keys.length >= 96} onClick={() => onKey()}><Diamond size={13}/> Set keyframe</button><button type="button" title="Remove keyframe" aria-label="Remove keyframe" className="button button-secondary button-small" disabled={!existing} onClick={remove}><Trash2 size={14}/></button></div>
    <label className="field motion-field"><span>Ease into keyframe</span><select value={existing?.ease ?? 'smooth'} disabled={!existing} onChange={event => onKey(event.target.value as Ease)}><option value="smooth">Smooth</option><option value="linear">Linear</option><option value="hold">Hold (step)</option></select></label>
  </div>
}

export function descendants(shot: Shot, root: string) {
  const ids = new Set([root])
  while (true) {
    const count = ids.size
    for (const layer of shot.layers) if (layer.parent && ids.has(layer.parent)) ids.add(layer.id)
    if (ids.size === count) return ids
  }
}

export function MotionInspector({ tab, onTab, shot, layer, frame, localFrame, assets, disabled, update, updateLayer, removeLayer, moveLayer }:
  { tab: InspectorTab; onTab: (tab: InspectorTab) => void; shot: Shot; layer?: Layer; frame: number; localFrame: number; assets: Asset[];
    disabled: boolean; update: (patch: Partial<Shot>) => void; updateLayer: (patch: Partial<Layer>) => void; removeLayer: () => void; moveLayer: (direction: number) => void }) {
  const camera = shot.camera, isLocked = camera.mode === 'locked'
  function layerPose(patch: Partial<Pose>, force = false, easing?: Ease) {
    if (!layer || (layer.keys.length >= 96 && !layer.keys.some(k => k.frame === frame))) return
    updateLayer(authored(layer.pose,layer.keys,frame,patch,force,easing))
  }
  function cameraPose(patch: Partial<CameraPose>, force = false, easing?: Ease) {
    if (isLocked) update({ camera:{ ...camera, pose:{ ...camera.pose,...patch } } })
    else if (camera.keys.length < 96 || camera.keys.some(k => k.frame === frame)) update({ camera:{ ...camera,...authored(camera.pose,camera.keys,frame,patch,force,easing) } })
  }
  function switchCamera(mode: Camera['mode']) {
    if (mode === camera.mode) return
    const isTracking = camera.mode === 'tracking' || mode === 'tracking'
    if (isTracking && camera.keys.length > 0 && !window.confirm('Tracking uses offsets instead of stage coordinates. Replace these camera keys?')) return
    const [z,,,,e,f] = evaluateFrame(shot,localFrame).projection
    const pose = { x:(270-e)/z,y:(480-f)/z,zoom:z }
    const target = mode === 'tracking' ? shot.layers.find(l => !l.asset)?.id ?? layer?.id ?? shot.layers[0]?.id ?? null : null
    update({ camera:{ mode, target, pose:mode === 'tracking' ? { x:0,y:0,zoom:pose.zoom } : pose, keys:isTracking ? [] : camera.keys } })
  }
  function changeLength(seconds: number) {
    const frames = clamp(Math.round(seconds*fps),15,900)
    const affected = [camera.keys,...shot.layers.map(l => l.keys)].some(keys => keys.some(k => k.frame >= frames))
    if (affected && !window.confirm('Shortening this shot will remove keys beyond its new end. Continue?')) return
    update({ frames, camera:{ ...camera, keys:camera.keys.filter(k => k.frame < frames) }, layers:shot.layers.map(item => ({ ...item,keys:item.keys.filter(k => k.frame < frames) })) })
  }
  const pose = layer ? sample(layer.pose,layer.keys,frame) : null
  const cp = isLocked ? camera.pose : sample(camera.pose,camera.keys,frame)
  const forbidden = layer && descendants(shot,layer.id)
  const index = layer ? shot.layers.findIndex(l => l.id === layer.id) : -1
  return <aside className="panel motion-inspector" aria-label="Animation inspector">
    <div className="motion-tabs" aria-label="Inspector view">{(['layer','camera','shot'] as const).map(item => <button key={item} type="button" aria-pressed={tab === item} onClick={() => onTab(item)}>{item[0].toUpperCase()+item.slice(1)}</button>)}</div>
    <fieldset disabled={disabled} className="motion-inspector-body">
      {tab === 'layer' && (layer && pose ? <>
        <div className="motion-inspector-heading"><div><small>{layer.asset ? 'Artwork layer' : 'Transform group'}</small><h2>{layer.name}</h2></div><Badge>{index + 1}/{shot.layers.length}</Badge></div>
        <div className="motion-values" key={layer.id}>
          <NumberField label="Position X" value={pose.x} min={-4096} max={4096} onValue={x => layerPose({x})}/><NumberField label="Position Y" value={pose.y} min={-4096} max={4096} onValue={y => layerPose({y})}/>
          <NumberField label="Scale X" value={pose.scale_x} min={.05} max={4} step={.05} onValue={scale_x => layerPose({scale_x})}/><NumberField label="Scale Y" value={pose.scale_y} min={.05} max={4} step={.05} onValue={scale_y => layerPose({scale_y})}/>
          <NumberField label="Rotation °" value={pose.rotation} min={-720} max={720} onValue={rotation => layerPose({rotation})}/><NumberField label="Opacity %" value={100*pose.opacity} min={0} max={100} onValue={value => layerPose({opacity:value/100})}/>
        </div>
        <label className="check-field motion-visible"><input type="checkbox" checked={pose.visible} onChange={event => layerPose({visible:event.target.checked})}/> Visible at this frame</label>
        <KeyTools keys={layer.keys} frame={frame} onKey={ease => layerPose({},true,ease)} remove={() => updateLayer({ keys:layer.keys.filter(key => key.frame !== frame) })}/>
        <details className="motion-extra"><summary>Layer setup & ordering</summary>
          <label className="field motion-field"><span>Layer name</span><input value={layer.name} maxLength={100} onChange={event => updateLayer({ name:event.target.value })}/></label>
          <label className="field motion-field"><span>Artwork source</span><select value={layer.asset ?? ''} onChange={event => updateLayer({ asset:event.target.value || null })}><option value="">No image (group)</option>{assets.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label className="field motion-field"><span>Parent group or layer</span><select value={layer.parent ?? ''} onChange={event => updateLayer({ parent:event.target.value || null })}><option value="">Stage</option>{shot.layers.filter(l => !forbidden?.has(l.id)).map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <div className="motion-values"><NumberField label="Pivot X" value={layer.pivot_x} min={-4096} max={4096} onValue={pivot_x => updateLayer({pivot_x})}/><NumberField label="Pivot Y" value={layer.pivot_y} min={-4096} max={4096} onValue={pivot_y => updateLayer({pivot_y})}/></div>
          <div className="motion-key-actions"><button type="button" className="button button-secondary button-small" disabled={index === shot.layers.length-1} onClick={() => moveLayer(1)}><ArrowUp size={14}/> Forward</button><button type="button" className="button button-secondary button-small" disabled={index < 1} onClick={() => moveLayer(-1)}><ArrowDown size={14}/> Back</button><button type="button" aria-label="Remove layer" title="Remove layer" className="button button-secondary button-small" onClick={removeLayer}><Trash2 size={14}/></button></div>
        </details>
      </> : <p className="motion-help">Import a layer or add a group to start animating.</p>)}
      {tab === 'camera' && <>
        <div className="motion-inspector-heading"><div><small>Cinematography</small><h2>Camera direction</h2></div><Focus size={19}/></div>
        <label className="field motion-field"><span>Camera mode</span><select value={camera.mode} onChange={event => switchCamera(event.target.value as Camera['mode'])}><option value="locked">Locked / static</option><option value="keyframed">Pan & zoom keyframes</option><option value="tracking" disabled={!shot.layers.length}>Track a layer</option></select></label>
        {camera.mode === 'tracking' && <label className="field motion-field"><span>Tracking target</span><select value={camera.target ?? ''} onChange={event => update({camera:{...camera,target:event.target.value || null}})}>{shot.layers.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
        <div className="motion-values"><NumberField label={camera.mode === 'tracking' ? 'Offset X' : 'Center X'} value={cp.x} min={-4096} max={4096} onValue={x => cameraPose({x})}/><NumberField label={camera.mode === 'tracking' ? 'Offset Y' : 'Center Y'} value={cp.y} min={-4096} max={4096} onValue={y => cameraPose({y})}/><NumberField label="Zoom" value={cp.zoom} min={.5} max={4} step={.05} onValue={zoom => cameraPose({zoom})}/></div>
        <div className="motion-key-actions"><button className="button button-secondary button-small" type="button" onClick={() => cameraPose(camera.mode === 'tracking' ? {x:0,y:0,zoom:1} : defaultCamera)}>Wide framing</button><button className="button button-secondary button-small" type="button" onClick={() => cameraPose({zoom:1.4})}>Close framing</button></div>
        {isLocked ? <p className="motion-help motion-locked-hint"><LockKeyhole size={16}/> This view holds exactly still throughout the shot. Layer animation keeps playing.</p> : <KeyTools keys={camera.keys} frame={frame} onKey={ease => cameraPose({},true,ease)} remove={() => update({camera:{...camera,keys:camera.keys.filter(key => key.frame !== frame)}})}/>}
      </>}
      {tab === 'shot' && <>
        <div className="motion-inspector-heading"><div><small>Timing & edit</small><h2>Shot settings</h2></div><Badge>{duration(shotFrames(shot))}</Badge></div>
        <label className="field motion-field"><span>Shot name</span><input value={shot.name} maxLength={100} onChange={event => update({name:event.target.value})}/></label>
        <NumberField label="Source duration (seconds)" min={.5} max={30} step={1/30} value={shot.frames/fps} onValue={changeLength}/>
        <label className="field motion-field"><span>Motion speed</span><select value={shot.speed} onChange={event => update({speed:Number(event.target.value)})}>{[.5,.75,1,1.25,1.5,2].map(speed => <option key={speed} value={speed}>{speed}×</option>)}</select></label>
        <p className="motion-help">{shot.frames} source frames → {shotFrames(shot)} output frames at 30 FPS. Speed retimes layers and camera together.</p>
        <p className="motion-help">When paused, changing a pose after source frame 0 sets a keyframe. Set frame 0 for the starting pose.</p>
      </>}
    </fieldset>
  </aside>
}
