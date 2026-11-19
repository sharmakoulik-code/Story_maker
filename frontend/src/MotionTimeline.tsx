import { Diamond, Layers3, Pause, Play, SkipBack, StepBack, StepForward, Video } from 'lucide-react'
import { duration, shotFrames, timecode, type Sequence, type Shot } from './motionApi'
import type { InspectorTab } from './MotionInspector'

export function MotionTransport({ cursor, total, playing, rate, seek, toggle, setRate }: {
  cursor: number; total: number; playing: boolean; rate: number;
  seek: (frame: number) => void; toggle: () => void; setRate: (rate: number) => void
}) {
  return <div className="motion-transport"><div className="motion-controls">
      <button type="button" className="motion-icon" aria-label="Go to start" title="Go to start" onClick={() => seek(0)}><SkipBack size={17}/></button>
      <button type="button" className="motion-icon" aria-label="Previous frame" title="Previous frame" onClick={() => seek(cursor-1)}><StepBack size={17}/></button>
      <button type="button" className="motion-play" aria-label={playing ? 'Pause animation' : 'Play animation'} title={playing ? 'Pause' : 'Play'} onClick={toggle}>{playing ? <Pause size={18}/> : <Play size={18}/>}</button>
      <button type="button" className="motion-icon" aria-label="Next frame" title="Next frame" onClick={() => seek(cursor+1)}><StepForward size={17}/></button>
      <div className="motion-timecode"><output aria-label="Current timecode">{timecode(cursor)}</output><small data-testid="motion-frame">Frame {cursor} / {total-1}</small></div>
    </div><label className="motion-rate">Preview speed <select aria-label="Preview speed" value={rate} onChange={event => setRate(Number(event.target.value))}>{[.5,1,1.5,2].map(rate => <option key={rate} value={rate}>{rate}×</option>)}</select></label></div>
}

export function MotionTimeline({ doc, shot, selected, cursor, start, total, seek, selectTrack }: {
  doc: Sequence; shot: Shot; selected?: string; cursor: number; start: number; total: number;
  seek: (frame: number) => void; selectTrack: (tab: InspectorTab, key?: string) => void
}) {
  const count = shotFrames(shot), local = cursor - start
  const tracks = [{ id:'$camera', name:'Camera', keys:shot.camera.keys, locked:shot.camera.mode === 'locked' }, ...shot.layers.filter(layer => layer.keys.length), ...shot.layers.filter(layer => !layer.keys.length)]
  let offset = 0
  return <section className="motion-timeline panel" aria-label="Animation timeline">
    <div className="motion-ruler"><span>00:00</span><span>{duration(total/4)}</span><span>{duration(total/2)}</span><span>{duration(total*3/4)}</span><span>{duration(total)}</span></div>
    <div className="motion-strip">{doc.shots.map((cut,i) => { const frames = shotFrames(cut), at = offset; offset += frames; return <button key={cut.id} type="button" style={{flexGrow:frames}} className={`motion-clip clip-${i%3}`} aria-label={`Jump to ${cut.name}`} aria-current={cut.id === shot.id ? 'true' : undefined} onClick={() => seek(at)}><span>{String(i+1).padStart(2,'0')}</span> {cut.name}</button> })}<span className="motion-position" style={{left:`${100*cursor/Math.max(1,total-1)}%`}}/></div>
    <input className="motion-scrub" aria-label="Timeline scrubber" type="range" min={0} max={total-1} step={1} value={cursor} onChange={event => seek(Number(event.target.value))}/>
    <div className="motion-track-head"><span><Diamond size={13}/> Shot keyframes</span><span>{shot.name} · {duration(count)}</span></div>
    <div className="motion-tracks" tabIndex={0} aria-label="Keyframe tracks">
      {tracks.map(track => {
        const isCam = track.id === '$camera', active = selected === track.id, locked = 'locked' in track && track.locked
        return <div key={track.id} className={`motion-track ${active ? 'track-selected' : ''}`}><button type="button" title={track.name} onClick={() => selectTrack(isCam ? 'camera' : 'layer',track.id)}>{isCam ? <Video size={13}/> : <Layers3 size={13}/>}<span>{track.name}</span></button><div className="motion-keybar">
          {locked ? <span className="motion-locked-track">Locked</span> : track.keys.map(key => {
            const output = Math.min(count-1,Math.round(key.frame/shot.speed))
            return <button className="motion-key-marker" type="button" key={key.frame} title={`Source frame ${key.frame} · ${key.ease}`} aria-label={`${track.name} keyframe ${key.frame}`} style={{left:`${100*output/Math.max(1,count-1)}%`}} onClick={() => {seek(start+output);selectTrack(isCam ? 'camera' : 'layer',track.id)}}><Diamond size={11} fill="currentColor"/></button>
          })}<span className="motion-position" style={{left:`${100*local/Math.max(1,count-1)}%`}}/>
        </div></div>
      })}
    </div>
  </section>
}
