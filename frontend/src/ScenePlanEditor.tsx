import { ArrowDown, ArrowUp, Camera, Clock3, Image as ImageIcon, ListVideo, Plus, Trash2 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { LineField, NoteField } from './PlanChrome'
import { limits, stamp, transitions, type SavedPlan, type Scene, type SceneTiming, type StoryBible } from './planApi'
import { Badge } from './ui'

export function SceneList({ scenes, plan, selected, select, add, editable }: {
  scenes: Scene[]; plan: SavedPlan; selected: string; select: (id: string) => void; add: () => void; editable: boolean;
}) {
  return <aside className="panel scene-list-panel" aria-labelledby="sequence-heading">
    <div className="bible-heading"><div><h3 id="sequence-heading"><ListVideo size={17} aria-hidden="true"/> Sequence <span>{scenes.length}</span></h3><p>Scenes in playback order.</p></div>{editable && <button type="button" className="button button-secondary button-small icon-only" aria-label="Add scene" title="Add scene" disabled={scenes.length >= limits.scenes} onClick={add}><Plus size={17} aria-hidden="true" /></button>}</div>
    <ol className="scene-list">{scenes.map((scene, index) => {
      const metric = plan.timing.scenes.find(item => item.scene_id === scene.id)
      return <li key={scene.id}><button type="button" aria-pressed={scene.id === selected} onClick={() => select(scene.id)} className="scene-pick">
        <span className="scene-number">{String(index + 1).padStart(2, '0')}</span><span className="scene-pick-label"><strong>{scene.title || 'Unnamed scene'}</strong><small>{scene.duration_seconds}s · {transitions[scene.transition]}</small></span>{metric && !metric.fits && <span className="timing-dot" title="Saved timing needs review"/>}
      </button></li>
    })}</ol>
  </aside>
}

function DialogueEditor({ scene, bible, change }: { scene: Scene; bible: StoryBible; change: (next: Partial<Scene>) => void }) {
  const lines = scene.dialogue
  return <div className="plan-fields dialogue-editor"><div className="bible-heading"><div><h3>Dialogue <span>{lines.length}</span></h3><p>Speaker labels aren’t counted as spoken text.</p></div><button type="button" className="button button-secondary button-small" onClick={() => change({ dialogue: [...lines, { character_id: null, speaker: '', text: '' }] })} disabled={lines.length >= limits.dialogue}><Plus size={15} aria-hidden="true"/> Add line</button></div>
    {lines.length ? lines.map((line, index) => {
      const set = (patch: Partial<typeof line>) => change({ dialogue: lines.map((old, i) => i === index ? { ...old, ...patch } : old) })
      return <div key={index} className="dialogue-line"><div className="dialogue-head"><label className="field"><span>Speaker for line {index + 1}</span><select value={line.character_id ?? ''} onChange={event => set({ character_id: event.target.value || null })}>
        <option value="">Unassigned / custom speaker</option>{bible.characters.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><button type="button" className="button button-small button-secondary icon-only" aria-label={`Remove dialogue line ${index + 1}`} onClick={() => change({ dialogue: lines.filter((_, i) => i !== index) })}><Trash2 size={15} aria-hidden="true"/></button></div>
        {!line.character_id && <LineField label={`Custom speaker for line ${index + 1}`} value={line.speaker} onChange={speaker => set({ speaker })} />}
        <NoteField label={`Dialogue line ${index + 1}`} value={line.text} rows={2} onChange={text => set({ text })}/>
      </div>
    }) : <p className="inline-empty">No quoted or speaker-labelled lines were included in this scene.</p>}
  </div>
}

export function ScenePlanEditor({ scene, bible, number, count, metric, source, editable, change, move, remove }: {
  scene: Scene; bible: StoryBible; number: number; count: number; metric: SceneTiming | undefined; source?: string; editable: boolean;
  change: (next: Partial<Scene>) => void; move: (direction: number) => void; remove: () => void;
}) {
  const [custom, setCustom] = useState(false)
  useEffect(() => setCustom(false), [metric])
  const manual = custom || Boolean(scene.image_prompt_override)
  return <section className="panel scene-plan-editor" aria-labelledby="scene-editor-heading">
    <div className="scene-editor-heading"><div className="panel-heading"><span className="panel-symbol"><Camera size={19} aria-hidden="true"/></span><div><p className="eyebrow">Scene {String(number).padStart(2, '0')}</p><h2 id="scene-editor-heading">{scene.title || 'Unnamed scene'}</h2></div></div>
      {editable && <div className="scene-edit-tools"><button type="button" className="button button-secondary button-small icon-only" aria-label="Move scene earlier" title="Move scene earlier" onClick={() => move(-1)} disabled={number === 1}><ArrowUp size={16} aria-hidden="true"/></button><button type="button" className="button button-secondary button-small icon-only" aria-label="Move scene later" title="Move scene later" onClick={() => move(1)} disabled={number === count}><ArrowDown size={16} aria-hidden="true"/></button><button type="button" className="button button-secondary button-small icon-only" aria-label="Remove scene" title="Remove scene" onClick={remove} disabled={count === 1}><Trash2 size={16} aria-hidden="true"/></button></div>}
    </div>
    {metric && <div className="scene-measurements"><Badge tone={metric.fits ? 'mint' : 'amber'}><Clock3 size={13} aria-hidden="true"/>{metric.spoken_words ? `${metric.speech_seconds.toFixed(1)}s estimated speech` : 'No spoken lines'}</Badge><small>{stamp(metric.start_seconds)}–{stamp(metric.end_seconds)} on saved plan · {metric.fits ? 'Fits this allocation' : `Needs ${metric.minimum_seconds}s`}</small></div>}
    <fieldset disabled={!editable} className="plan-fields">
      <LineField label="Scene title" value={scene.title} onChange={title => change({ title })} required />
      <div className="two-fields">
        <label className="field"><span>Scene duration (seconds)</span><input type="number" value={scene.duration_seconds || ''} min={1} max={900} step={1} required onChange={event => change({ duration_seconds: Number(event.target.value) })}/></label>
        <label className="field"><span>Outgoing transition</span><select value={scene.transition} onChange={event => change({ transition: event.target.value as Scene['transition'] })}>{Object.entries(transitions).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
      </div>
      <NoteField label="Scene narration" value={scene.narration} maxLength={8000} rows={4} onChange={narration => change({ narration })} placeholder="Write what should be spoken, or leave this scene silent."/>
      <details className="scene-details"><summary>Dialogue {scene.dialogue.length ? `· ${scene.dialogue.length} ${scene.dialogue.length === 1 ? 'line' : 'lines'}` : ''}</summary><div className="details-body"><DialogueEditor scene={scene} bible={bible} change={change}/></div></details>
      <details className="scene-details" open><summary>Visual direction & continuity</summary><div className="plan-fields details-body">
        <NoteField label="Visual description" value={scene.visual_description} onChange={visual_description => change({ visual_description })} rows={2}/>
        <div className="two-fields plot-fields"><label className="field"><span>Location reference</span><select value={scene.location_id ?? ''} onChange={event => change({ location_id: event.target.value || null })}><option value="">No location reference</option>{bible.locations.map(place => <option key={place.id} value={place.id}>{place.name}</option>)}</select></label><NoteField label="Environment notes" value={scene.environment} onChange={environment => change({ environment })} rows={2}/></div>
        <div className="plan-fields continuity-checks" role="group" aria-label="Characters in this scene">
          <span className="field-label">Characters & emotions</span>
          {bible.characters.length ? bible.characters.map(person => {
            const appearance = scene.cast.find(item => item.character_id === person.id)
            return <div className="cast-row" key={person.id}><label className="check-field"><input type="checkbox" checked={Boolean(appearance)} onChange={event => change({ cast: event.target.checked ? [...scene.cast, { character_id: person.id, emotion: '' }] : scene.cast.filter(item => item.character_id !== person.id) })}/> {person.name}</label>
              {appearance && <LineField label={`Emotion for ${person.name}`} value={appearance.emotion} onChange={emotion => change({ cast: scene.cast.map(item => item.character_id === person.id ? { ...item, emotion } : item) })} />}
            </div>
          }) : <p className="inline-empty">Add characters in the Story Bible to link them here.</p>}
        </div>
        {bible.props.length > 0 && <div className="plan-fields continuity-checks" role="group" aria-label="Props in this scene"><span className="field-label">Important props</span><div className="prop-checks">{bible.props.map(item => <label className="check-field" key={item.id}><input type="checkbox" checked={scene.prop_ids.includes(item.id)} onChange={event => change({ prop_ids: event.target.checked ? [...scene.prop_ids, item.id] : scene.prop_ids.filter(id => id !== item.id) })}/> {item.name}</label>)}</div></div>}
        <NoteField label="Camera direction" value={scene.camera} onChange={camera => change({ camera })} rows={2}/>
      </div></details>
      <details className="scene-details"><summary>Image prompt, motion & sound</summary><div className="plan-fields details-body">
        <NoteField label="Animation notes" value={scene.animation} onChange={animation => change({ animation })} rows={2}/><NoteField label="Sound effect suggestions" value={scene.sound_effects} onChange={sound_effects => change({ sound_effects })} rows={2}/>
        <div className="field"><div className="field-top"><label htmlFor="automatic-prompt"><ImageIcon size={15} aria-hidden="true"/> Image prompt</label>{manual ? <button type="button" className="text-button" onClick={() => { setCustom(false); change({ image_prompt_override: '' }) }}>Use automatic prompt</button> : <button type="button" className="text-button" onClick={() => { setCustom(true); change({ image_prompt_override: metric?.image_prompt || '' }) }}>Customize prompt</button>}</div>
          <textarea spellCheck={false} id="automatic-prompt" rows={5} maxLength={8000} value={manual ? scene.image_prompt_override : metric?.image_prompt ?? ''} readOnly={!manual} onChange={event => change({ image_prompt_override: event.target.value })} placeholder="Automatic prompt will appear after saving this scene."/>
          <small>{manual ? 'Custom prompt. Changes to the Bible won’t replace your text. A blank override saves as automatic.' : 'Automatic prompts update on save using shared character profiles, setting, staging and the 9:16 canvas. Nothing is sent to a model.'}</small>
        </div>
      </div></details>
      {source && <details className="scene-details source-quote"><summary>Original story excerpt</summary><p className="details-body">{source}</p></details>}
    </fieldset>
  </section>
}
