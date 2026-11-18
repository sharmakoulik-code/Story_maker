import { BookOpen, BookUser, MapPin, PackageOpen, Plus, Trash2, UserRound } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { describeError, useResource } from './api'
import type { Character, Reference, StoryArc, StoryBible } from './planApi'
import { limits, newId } from './planApi'
import { LineField, NoteField } from './PlanChrome'
import { Badge, Busy, Warning } from './ui'
import { blankDesign, copyDesign, fromLibrary, imageUrl, jsonMutation, libraryPath, type LibraryCharacter } from './visualApi'

const plotFields: [keyof StoryArc, string][] = [
  ['main_plot', 'Main plot'], ['beginning', 'Beginning'], ['conflict', 'Conflict'],
  ['emotional_development', 'Emotional development'], ['climax', 'Climax'], ['ending', 'Ending'],
]
export function ArcEditor({ arc, editable, change }: { arc: StoryArc; editable: boolean; change: (arc: StoryArc) => void }) {
  return <section className="panel plan-tab-panel" aria-labelledby="arc-heading">
    <div className="panel-heading"><span className="panel-symbol"><BookOpen size={19} aria-hidden="true" /></span><div><h2 id="arc-heading">Story analysis</h2><p>Draft plot beats and emotion cues pulled from the source. Verify or rewrite them before approval.</p></div></div>
    <fieldset disabled={!editable} className="plan-fields"><NoteField label="Main plot" value={arc.main_plot} onChange={value => change({ ...arc, main_plot: value })} rows={4}/><div className="two-fields plot-fields">
      {plotFields.slice(1).map(([key, label]) => <NoteField key={key} label={label} value={arc[key]} onChange={value => change({ ...arc, [key]: value })} placeholder="Not identified automatically; add if applicable."/>)}
    </div></fieldset>
  </section>
}

const details: [Exclude<keyof Character, keyof Reference | 'role' | 'library_pin'>, string][] = [
  ['appearance', 'Appearance notes'], ['face', 'Face'], ['body', 'Body & proportions'], ['clothing', 'Clothing'], ['hair', 'Hair'], ['eyes', 'Eyes'],
  ['accessories', 'Accessories'], ['personality', 'Personality'], ['age_range', 'Age range'], ['generation_notes', 'Generation instructions'], ['relationships', 'Relationships & continuity'],
]

function EntryHeader({ title, children, onRemove, editable }: { title: string; children?: ReactNode; onRemove: () => void; editable: boolean }) {
  return <div className="entry-header"><h4>{title}</h4>{children}{editable && <button type="button" className="button button-secondary button-small icon-only" aria-label={`Remove ${title}`} onClick={onRemove}><Trash2 size={15} aria-hidden="true"/></button>}</div>
}

function DesignPicker({ items, label, action, apply }: { items: LibraryCharacter[]; label: string; action: string; apply: (item: LibraryCharacter) => void }) {
  const [selected, setSelected] = useState('')
  const item = items.find(entry => entry.id === selected)
  return items.length ? <div className="library-design">
    <label className="field"><span>{label}</span><select value={selected} onChange={event => setSelected(event.target.value)}><option value="">Choose a design…</option>{items.map(entry => <option key={entry.id} value={entry.id}>{entry.design.name}{entry.reference ? ` · ref v${entry.reference.number}` : ' · text only'}</option>)}</select></label>
    <div className="plan-primary-actions"><button type="button" className="button button-secondary button-small" disabled={!item} onClick={() => { if (item) { apply(item); setSelected('') } }}><BookUser size={15} aria-hidden="true"/> {action}</button></div>
  </div> : <p className="inline-empty">No active designs yet. Create one in the <Link className="text-button" to="/characters">Character Library</Link>.</p>
}

function LinkedDesign({ entry, items, editable, change, onCopy }: {
  entry: Character; items: LibraryCharacter[]; editable: boolean; change: (next: Character) => void; onCopy: () => void;
}) {
  const pin = entry.library_pin
  const [missing, setMissing] = useState<string | null>(null)
  return <details className="scene-details library-picker"><summary>{pin ? 'Pinned library design' : 'Library design'}</summary>
    <div className="details-body library-design">
      {pin && <><div className="library-design-bottom">
        {pin.image_id && pin.image_id !== missing && <a href={imageUrl(pin.image_id)} target="_blank" rel="noreferrer" aria-label={`Open pinned reference for ${entry.name}`}><img src={imageUrl(pin.image_id, true)} alt="" loading="lazy" onError={() => setMissing(pin.image_id)}/></a>}
        <Link className="button button-secondary button-small" to={`/characters?character=${pin.character_id}`}>Open library character</Link>
        {editable && <button type="button" className="text-button" onClick={() => change({ ...entry, library_pin: null })}>Detach pin</button>}
      </div><p className="inline-empty">This project keeps its own design and reference version even if the library entry changes.</p></>}
      {editable && <><DesignPicker items={items} label={`Saved design for ${entry.name}`} action="Apply design to this character" apply={item => change({ ...entry, ...fromLibrary(item), name: entry.name })}/>
        <p className="inline-empty">Applying a design keeps this character’s scene links, name, and story relationships.</p>
        {!pin && <div className="plan-primary-actions"><button type="button" className="button button-secondary button-small" onClick={onCopy}><Plus size={14} aria-hidden="true"/> Copy to library</button></div>}
      </>}
    </div>
  </details>
}

function CharacterEditor({ entry, items, editable, change, remove, copy }: { entry: Character; items: LibraryCharacter[]; editable: boolean; change: (entry: Character) => void; remove: () => void; copy: () => void }) {
  return <article className="bible-entry">
    <EntryHeader title={entry.name || 'Unnamed character'} editable={editable} onRemove={remove}><Badge tone={entry.role === 'main' ? 'mint' : 'quiet'}>{entry.role === 'main' ? 'Main' : 'Supporting'}</Badge></EntryHeader>
    <fieldset disabled={!editable} className="plan-fields"><div className="two-fields"><LineField label="Character name" value={entry.name} onChange={value => change({ ...entry, name: value })} required />
      <label className="field"><span>Story role</span><select value={entry.role} onChange={event => change({ ...entry, role: event.target.value as Character['role'] })}><option value="main">Main</option><option value="supporting">Supporting</option></select></label></div>
      <details className="scene-details"><summary>Character details</summary><div className="plan-fields details-body"><NoteField label="Description" value={entry.description} onChange={value => change({ ...entry, description: value })}/>
        <div className="two-fields">{details.map(([key, label]) => key === 'appearance' || key === 'relationships' || key === 'generation_notes' ? <NoteField key={key} label={label} value={entry[key]} onChange={value => change({ ...entry, [key]: value })}/> : <LineField key={key} label={label} value={entry[key]} onChange={value => change({ ...entry, [key]: value })}/>)}</div>
      </div></details>
    </fieldset>
    {(editable || entry.library_pin) && <LinkedDesign entry={entry} items={items} editable={editable} change={change} onCopy={copy}/>}
  </article>
}

function ReferenceSection({ kind, items, editable, change, remove }: {
  kind: 'locations' | 'props'; items: Reference[]; editable: boolean; change: (items: Reference[]) => void; remove: (id: string, name: string) => void;
}) {
  const location = kind === 'locations'
  const label = location ? 'Location' : 'Prop'
  const Icon = location ? MapPin : PackageOpen
  return <section className="bible-section" aria-label={kind}><div className="bible-heading"><div><h3><Icon size={17} aria-hidden="true"/>{location ? 'Locations' : 'Important props'} <span>{items.length}</span></h3><p>{location ? 'Reuse locations in multiple scene plans.' : 'Keep key objects recognizable across scenes.'}</p></div>
    {editable && <button type="button" className="button button-secondary button-small" disabled={items.length >= limits[kind]} onClick={() => change([...items, { id: newId(location ? 'location' : 'prop'), name: `New ${label.toLowerCase()}`, description: '' }])}><Plus size={15} aria-hidden="true"/> Add {label.toLowerCase()}</button>}</div>
    {items.length ? <div className="bible-grid">{items.map((entry, index) => <article key={entry.id} className="bible-entry">
      <EntryHeader title={entry.name || `Unnamed ${label.toLowerCase()}`} editable={editable} onRemove={() => remove(entry.id, entry.name)}/>
      <fieldset disabled={!editable} className="plan-fields"><LineField label={`${label} name`} value={entry.name} required onChange={value => change(items.map((item, ix) => ix === index ? { ...item, name: value } : item))}/>
        <NoteField label={`${label} description`} value={entry.description} rows={2} onChange={value => change(items.map((item, ix) => ix === index ? { ...item, description: value } : item))} placeholder="Add visual details to reuse later."/></fieldset>
    </article>)}</div> : <p className="inline-empty">None identified. Add a reference if the story needs one.</p>}
  </section>
}

export function BibleEditor({ bible, editable, change, remove }: { bible: StoryBible; editable: boolean; change: (bible: StoryBible) => void; remove: (kind: 'characters' | 'locations' | 'props', id: string, name: string) => void }) {
  const library = useResource<LibraryCharacter[]>(libraryPath)
  const designs = library.data?.filter(entry => !entry.archived_at) ?? []
  const [working, setWorking] = useState(false)
  const [libraryError, setLibraryError] = useState('')
  const [copied, setCopied] = useState<LibraryCharacter | null>(null)
  function addCharacter(design = blankDesign('New character'), pin: Character['library_pin'] = null) {
    if (bible.characters.length >= limits.characters) return
    change({ ...bible, characters: [...bible.characters, { ...design, library_pin: pin, id: newId('character'), role: bible.characters.length ? 'supporting' : 'main', relationships: '' }] })
  }
  async function publish(entry: Character) {
    if (working) return
    setWorking(true); setLibraryError(''); setCopied(null)
    try {
      setCopied(await jsonMutation<LibraryCharacter>(libraryPath, 'POST', copyDesign(entry)))
      library.reload()
    } catch (error) { setLibraryError(describeError(error)) }
    finally { setWorking(false) }
  }
  return <section className="panel plan-tab-panel" aria-labelledby="bible-heading">
    <div className="panel-heading"><span className="panel-symbol panel-symbol-lilac"><BookOpen size={19} aria-hidden="true"/></span><div><h2 id="bible-heading">Story Bible</h2><p>One reference for the whole story. Names and descriptors are candidates; add details the text doesn’t specify.</p></div></div>
    <fieldset disabled={!editable} className="plan-fields"><div className="two-fields plot-fields">
      <NoteField label="Story setting" value={bible.setting} onChange={setting => change({ ...bible, setting })} rows={2}/>
      <NoteField label="Visual style" value={bible.visual_style} onChange={visual_style => change({ ...bible, visual_style })} rows={2}/>
    </div><NoteField label="Continuity rules" value={bible.continuity_rules} onChange={continuity_rules => change({ ...bible, continuity_rules })} rows={2}/></fieldset>
    <section className="bible-section" aria-label="Characters"><div className="bible-heading"><div><h3><UserRound size={17} aria-hidden="true"/> Characters <span>{bible.characters.length}</span></h3><p>Keep shared profiles and pin specific reference versions from the Character Library.</p></div>
      {editable && <button type="button" className="button button-secondary button-small" disabled={bible.characters.length >= limits.characters} onClick={() => addCharacter()}><Plus size={15} aria-hidden="true"/> Add character</button>}</div>
      {editable && bible.characters.length < limits.characters && <details className="scene-details library-picker"><summary>Add from Character Library</summary><div className="details-body">
        {library.loading ? <Busy>Reading character designs…</Busy> : <DesignPicker items={designs} label="Saved character to add" action="Add design to cast" apply={item => {
          const { library_pin, ...design } = fromLibrary(item)
          addCharacter(design, library_pin)
        }}/>}</div></details>}
      {library.error && <Warning retry={() => library.reload()}>{library.error}</Warning>}
      {working && <Busy>Copying design to the library…</Busy>}
      {libraryError && <Warning>{libraryError}</Warning>}
      {copied && <p role="status" className="plan-notice"><strong>{copied.design.name}</strong> copied to the <Link to={`/characters?character=${copied.id}`}>Character Library</Link>.</p>}
      {bible.characters.length ? <div className="bible-grid">{bible.characters.map((entry, index) => <CharacterEditor key={entry.id} items={designs} entry={entry} editable={editable} change={next => change({ ...bible, characters: bible.characters.map((character, ix) => ix === index ? next : character) })} remove={() => remove('characters', entry.id, entry.name)} copy={() => void publish(entry)}/>)}</div> : <p className="inline-empty">No character candidates were found. Add the cast if your story has one.</p>}
    </section>
    <ReferenceSection kind="locations" items={bible.locations} editable={editable} change={locations => change({ ...bible, locations })} remove={(id, name) => remove('locations', id, name)}/>
    <ReferenceSection kind="props" items={bible.props} editable={editable} change={props => change({ ...bible, props })} remove={(id, name) => remove('props', id, name)}/>
  </section>
}
