import { Archive, BadgeCheck, BookUser, Image as ImageIcon, Plus, Save, Search, UserRound, UsersRound } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api, describeError, useResource } from './api'
import { LineField, NoteField } from './PlanChrome'
import type { CharacterDesign } from './planApi'
import { OpenStill, StillCredit, StillImage, StillImport, StillVersions } from './StillImages'
import { Badge, Busy, PageHeading, Warning, useWarnUnsaved, useWorkspaceMode } from './ui'
import { blankDesign, charPath, jsonMutation, libraryPath, type LibraryCharacter } from './visualApi'

const designFields: [keyof CharacterDesign, string][] = [
  ['face', 'Face'], ['hair', 'Hair'], ['eyes', 'Eyes'], ['body', 'Body & proportions'],
  ['clothing', 'Outfits'], ['accessories', 'Accessories'], ['age_range', 'Age range'], ['personality', 'Personality'],
]

function CharacterLibrary({ initial, requested, refresh }: { initial: LibraryCharacter[]; requested: string | null; refresh: () => void }) {
  const requestedEntry = initial.find(item => item.id === requested)
  const [items, setItems] = useState(initial)
  const [archived, setArchived] = useState(Boolean(requestedEntry?.archived_at))
  const [selection, setSelection] = useState<string | null>(requestedEntry?.id ?? null)
  const [adding, setAdding] = useState(false)
  const [draft, setDraft] = useState<CharacterDesign | null>(null)
  const [search, setSearch] = useState('')
  const [work, setWork] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const mode = useWorkspaceMode()
  const entries = items.filter(item => Boolean(item.archived_at) === archived).filter(item => item.design.name.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()))
  const selected = adding ? null : entries.find(item => item.id === selection) ?? entries[0] ?? null
  const design = draft ?? selected?.design
  const dirty = Boolean(draft && (!adding || JSON.stringify(draft) !== JSON.stringify(blankDesign())))
  const editable = !work && !selected?.archived_at
  useWarnUnsaved(dirty && !work, 'Leave without saving your character design?')

  function confirmDiscard() { return !dirty || window.confirm('Discard the unsaved character design?') }
  function switchTo(id: string | null, isArchived = archived) {
    if (!confirmDiscard()) return
    setArchived(isArchived); setSelection(id); setAdding(false); setDraft(null); setError(''); setNotice('')
  }
  function add() {
    if (!confirmDiscard()) return
    setDraft(blankDesign()); setAdding(true); setArchived(false); setSearch(''); setError(''); setNotice('')
  }
  function accept(entry: LibraryCharacter, message: string) {
    setItems(previous => [entry, ...previous.filter(item => item.id !== entry.id)])
    setSelection(entry.id); setAdding(false); setDraft(null); setNotice(message); setArchived(Boolean(entry.archived_at))
    if (!entry.design.name.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())) setSearch('')
  }
  async function mutate(command: () => Promise<LibraryCharacter>, message: string, throwError = false) {
    setWork(true); setError(''); setNotice('')
    try { accept(await command(), message) }
    catch (problem) { if (throwError) throw problem; setError(describeError(problem)) }
    finally { setWork(false) }
  }
  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!editable || !design) return
    if (!design.name.trim()) { setError('Enter a character name.'); return }
    void mutate(() => selected ? jsonMutation(charPath(selected.id), 'PUT', { revision: selected.revision, design }) : jsonMutation(libraryPath, 'POST', design), 'Character saved to this library.')
  }
  function setField(key: keyof CharacterDesign, value: string) {
    if (design) setDraft({ ...design, [key]: value })
  }
  return <>
    <PageHeading label="Visual library" title="Character Library" actions={<button className="button button-primary" type="button" onClick={add} disabled={work}><Plus size={18} aria-hidden="true"/> New character</button>}>Keep a consistent design to reuse across stories. Project copies never change automatically.</PageHeading>
    {mode === 'preview' && <p className="demo-note">This demo resets on restart. Use sample images and fictional characters only.</p>}
    {error && <Warning>{error}<div><button type="button" className="text-button" onClick={() => { if (confirmDiscard()) refresh() }}>Reload library</button></div></Warning>}
    {notice && <div className="notice notice-success" role="status"><BadgeCheck size={18} aria-hidden="true"/>{notice}</div>}
    <div className="character-desk">
      <section className="panel character-roster" aria-labelledby="roster-heading">
        <div className="panel-heading"><span className="panel-symbol panel-symbol-lilac"><UsersRound size={20} aria-hidden="true"/></span><div><h2 id="roster-heading">Your cast</h2><p>Designs on this device</p></div></div>
        <div className="filter-group" role="group" aria-label="Character library filter"><button type="button" aria-pressed={!archived} className={!archived ? 'filter-active' : ''} onClick={() => switchTo(null, false)} disabled={work}>Active</button><button type="button" aria-pressed={archived} className={archived ? 'filter-active' : ''} onClick={() => switchTo(null, true)} disabled={work}>Archived</button></div>
        <div className="search-field cast-search"><Search size={16} aria-hidden="true"/><input aria-label="Search characters" placeholder="Find a character…" value={search} autoComplete="off" spellCheck={false} disabled={dirty || work} onChange={event => setSearch(event.target.value)}/></div>
        <div className="cast-grid">{entries.map(item => <button type="button" className="cast-card" key={item.id} aria-pressed={item.id === selected?.id} onClick={() => switchTo(item.id)} disabled={work}>
          <span className="cast-card-art"><StillImage version={item.reference} alt="" fallback="No reference"/></span>
          <span className="cast-card-meta"><strong>{item.design.name}</strong><small>{item.reference_count} {item.reference_count === 1 ? 'reference version' : 'reference versions'}</small></span>
        </button>)}</div>
        {!entries.length && <p className="inline-empty">{search ? 'No matching characters.' : archived ? 'No archived characters.' : 'Create a character here or copy one from a Story Bible.'}</p>}
      </section>
      {design ? <section className="panel character-editor" aria-labelledby="cast-editor-title">
        <div className="panel-heading"><span className="panel-symbol"><UserRound size={20} aria-hidden="true"/></span><div><h2 id="cast-editor-title">{adding ? 'New character design' : selected?.design.name}</h2><p>{selected?.archived_at ? 'Archived · kept for existing project pins' : 'Design sheet · the identity cues to repeat across shots'}</p></div></div>
        {selected && <section className="reference-desk" aria-labelledby="reference-heading">
          <div className="reference-portrait"><StillImage version={selected.reference} alt={`Reference for ${selected.design.name}`} fallback="No reference image"/></div>
          <div className="reference-copy"><h3 id="reference-heading"><ImageIcon size={16} aria-hidden="true"/> Visual reference</h3>
            {selected.reference ? <><Badge tone="lilac">Reference v{selected.reference.number}</Badge><StillCredit version={selected.reference}/></> : <p>Add a face, pose, or outfit sheet that you have permission to use.</p>}
            <div className="plan-primary-actions">
              {selected.reference && <OpenStill version={selected.reference}/>}
              {!selected.archived_at && <StillImport key={`reference-${selected.id}`} disabled={work || dirty} label={selected.reference ? 'Replace reference' : 'Import reference'} submit={body => {
                body.set('revision', String(selected.revision))
                return mutate(() => api(`${charPath(selected.id)}/references`, { method: 'POST', body }), 'Reference saved. Existing project pins did not change.', true)
              }}/>}</div>
            {dirty && <small>Save the character design before changing its reference.</small>}
          </div>
        </section>}
        {selected && <StillVersions key={`versions-${selected.id}`} path={`${charPath(selected.id)}/references`} count={selected.reference_count} activeId={selected.reference?.id ?? null} epoch={selected.revision} disabled={work || dirty} label="Reference versions" choose={selected.archived_at ? undefined : image => {
          void mutate(() => jsonMutation(`${charPath(selected.id)}/reference`, 'PUT', { revision: selected.revision, image_id: image }), 'Reference selected. Existing story pins did not change.')
        }}/>}
        <form className="character-form" onSubmit={save}><fieldset className="plan-fields" disabled={!editable}>
          <LineField label="Character name" value={design.name} required onChange={value => setField('name', value)}/>
          <NoteField label="Description" value={design.description} onChange={value => setField('description', value)} rows={2}/>
          <div className="two-fields">{designFields.map(([key, label]) => <LineField key={key} label={label} value={design[key]} onChange={value => setField(key, value)}/>)}</div>
          <NoteField label="Appearance notes" value={design.appearance} onChange={value => setField('appearance', value)} rows={2}/>
          <NoteField label="Generation instructions" value={design.generation_notes} onChange={value => setField('generation_notes', value)} placeholder="Details to keep consistent, such as the shape of an accessory or a signature palette." rows={2}/>
        </fieldset><div className="character-footer plan-primary-actions">
          {selected && <button className="button button-secondary button-small" type="button" disabled={work} onClick={() => {
            if (!confirmDiscard()) return
            void mutate(() => jsonMutation(`${charPath(selected.id)}/archive`, 'PUT', { revision: selected.revision, archived: !selected.archived_at }), selected.archived_at ? 'Character restored.' : 'Character archived. Its images and existing project pins are intact.')
          }}><Archive size={15} aria-hidden="true"/> {selected.archived_at ? 'Restore character' : 'Archive character'}</button>}
          {!selected?.archived_at && <button className="button button-primary" type="submit" disabled={!editable || !dirty}><Save size={16} aria-hidden="true"/> Save character</button>}
        </div></form>
      </section> : <div className="panel character-empty"><BookUser size={40} aria-hidden="true"/><h2>Keep your cast on model</h2><p>Record face, hair, outfit, and generation notes. You can import a reference and pin that version in any project’s Story Bible.</p><button className="button button-secondary" type="button" onClick={add}><Plus size={16} aria-hidden="true"/> Create a character</button></div>}
    </div>
  </>
}

export function CharactersPage() {
  const resource = useResource<LibraryCharacter[]>(libraryPath)
  const [params] = useSearchParams()
  if (resource.loading) return <Busy>Opening the Character Library…</Busy>
  if (resource.error) return <><PageHeading label="Visual library" title="Character Library"/><Warning retry={() => resource.reload()}>{resource.error}</Warning></>
  return resource.data ? <CharacterLibrary key={params.get('character') ?? 'library'} initial={resource.data} requested={params.get('character')} refresh={() => resource.reload()}/> : null
}
