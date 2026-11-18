import { ArrowUpRight, Clock3, FolderOpen, Plus, Search, X } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { dateLabel, formatDuration, languageNames, useResource, type ProjectSummary, type Style } from './api'
import { planLabels } from './planApi'
import forest from './assets/lantern-woods.svg'
import violet from './assets/violet-pass.svg'
import tide from './assets/moonlit-tide.svg'
import { Badge, Busy, PageHeading, Warning } from './ui'

export const covers: Record<Style, string> = { storybook: forest, cel: violet, moonlit: tide }

export function ProjectCard({ project }: { project: ProjectSummary }) {
  const status = project.archived_at ? 'Archived' : project.plan_status === 'not_started' ? 'Draft' : planLabels[project.plan_status]
  return <Link className="project-card" to={`/projects/${project.id}`}>
    <div className={`project-art art-${project.profile.style}`}><img src={covers[project.profile.style]} alt="" loading="lazy"/>
      <div className="project-card-overlay"><span className="cover-badge"><span className={`status-dot ${project.archived_at ? '' : project.plan_status === 'stale' ? 'dot-amber' : 'dot-mint'}`} />{status}</span><span className="cover-ratio">9:16</span></div>
    </div>
    <div className="project-card-body">
      <div className="card-name"><h3>{project.title}</h3><ArrowUpRight className="card-arrow" size={18} aria-hidden="true" /></div>
      <p className="card-meta"><span><Clock3 size={13} aria-hidden="true"/>{formatDuration(project.profile.duration_seconds)}</span><span>{languageNames[project.profile.language]}</span><time dateTime={project.updated_at} title={`Updated ${dateLabel(project.updated_at)}`}>{dateLabel(project.updated_at)}</time></p>
    </div>
  </Link>
}

export function EmptyProjects({ kind = 'active', search, clear }: { kind?: 'active' | 'archived' | 'all'; search?: boolean; clear?: () => void }) {
  return <div className="empty-state">
    <span className="empty-icon"><FolderOpen size={23} aria-hidden="true"/></span>
    <div><h3>{search ? 'No matching projects' : kind === 'archived' ? 'No archived projects' : 'Your first story belongs here'}</h3>
      <p>{search ? 'Try another title or clear the search.' : kind === 'archived' ? 'Archived stories will stay here until you restore them.' : 'Start a draft and it will appear here, ready to reopen any time.'}</p></div>
    {search ? <button type="button" className="button button-secondary" onClick={clear}>Clear search</button> : kind !== 'archived' && <Link to="/new" className="button button-secondary"><Plus size={16} aria-hidden="true"/> New story</Link>}
  </div>
}

const filters = ['active', 'archived', 'all'] as const
export function ProjectLibrary() {
  const projects = useResource<ProjectSummary[]>('/api/projects')
  const [filter, setFilter] = useState<typeof filters[number]>('active')
  const [search, setSearch] = useState('')
  const items = projects.data ?? []
  const counts = { all: items.length, archived: items.filter(project => project.archived_at).length, active: items.filter(project => !project.archived_at).length }
  const results = items.filter(project => filter === 'all' || Boolean(project.archived_at) === (filter === 'archived'))
    .filter(project => project.title.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase()))
  return <>
    <PageHeading label="Project library" title="My projects" actions={<Link to="/new" className="button button-primary"><Plus size={18} aria-hidden="true"/> New story</Link>}>
      Open a draft, or archive it without deleting any files.
    </PageHeading>
    <div className="library-toolbar">
      <div className="filter-group" role="group" aria-label="Project status">{filters.map(item => <button key={item} type="button" onClick={() => setFilter(item)} aria-pressed={filter === item} className={filter === item ? 'filter-active' : ''}>{item}<span>{counts[item]}</span></button>)}</div>
      <div className="search-field"><Search size={17} aria-hidden="true"/><input autoComplete="off" spellCheck={false} aria-label="Search project titles" placeholder="Search by title…" value={search} onChange={event => setSearch(event.target.value)}/>{search && <button type="button" aria-label="Clear project search" onClick={() => setSearch('')}><X size={17} /></button>}</div>
    </div>
    {projects.loading && !projects.data && <Busy>Opening the project library…</Busy>}
    {projects.error && <Warning retry={() => projects.reload()}>{projects.error}</Warning>}
    {projects.data && (results.length ? <><div className="library-results"><Badge>{results.length} {results.length === 1 ? 'project' : 'projects'}</Badge></div><div className="project-grid">{results.map(project => <ProjectCard key={project.id} project={project} />)}</div></> : <EmptyProjects kind={filter} search={Boolean(search.trim())} clear={() => setSearch('')}/>)}
  </>
}
