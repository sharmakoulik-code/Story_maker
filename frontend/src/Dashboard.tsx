import { ArrowRight, Cpu, Film, HardDrive, MemoryStick, Plus, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import { size, useResource, type HardwareReport, type ProjectSummary } from './api'
import forest from './assets/lantern-woods.svg'
import { EmptyProjects, ProjectCard } from './Projects'
import { boardPage } from './visualApi'
import { ActionLink, Badge, Busy, PageHeading, Warning, useWorkspaceMode } from './ui'

export function WorkstationMetrics({ hardware }: { hardware: HardwareReport }) {
  const logical = hardware.cpu.logical_cores
  const total = hardware.memory.total_bytes
  const free = hardware.storage.workspace.free_bytes
  const media = hardware.media.ffmpeg.state === 'ready' && hardware.media.ffprobe.state === 'ready'
  return <div className="metric-grid">
    <div className="metric"><div className="metric-icon"><Cpu size={19} aria-hidden="true"/></div><div className="min-w-0"><span>Processor</span><strong>{logical ?? 'Unknown'}{logical !== null ? ' threads' : ''}</strong><small title={hardware.cpu.name || undefined}>{hardware.cpu.name || 'CPU model not reported'}</small></div></div>
    <div className="metric"><div className="metric-icon metric-purple"><MemoryStick size={19} aria-hidden="true"/></div><div className="min-w-0"><span>System memory</span><strong>{size(total)}</strong><small>{hardware.memory.available_bytes === null ? 'Available RAM unknown' : `${size(hardware.memory.available_bytes)} available`}</small></div></div>
    <div className="metric"><div className="metric-icon metric-blue"><HardDrive size={19} aria-hidden="true"/></div><div className="min-w-0"><span>Workspace storage</span><strong>{size(free)}</strong><small>Free on workspace drive</small></div></div>
    <div className="metric"><div className="metric-icon metric-gold"><Film size={19} aria-hidden="true"/></div><div className="min-w-0"><span>Video tools</span><strong>{media ? 'Detected' : 'Not ready'}</strong><small>{media ? 'FFmpeg & FFprobe respond' : 'Check FFmpeg & FFprobe'}</small></div></div>
  </div>
}

export function Dashboard() {
  const projects = useResource<ProjectSummary[]>('/api/projects')
  const workstation = useResource<HardwareReport>('/api/hardware')
  const mode = useWorkspaceMode()
  const recent = (projects.data ?? []).filter(item => !item.archived_at).slice(0, 3)
  const sample = mode === 'preview' ? recent.find(item => item.title === 'The Blue Flower') : undefined
  return <>
    <PageHeading label="Your workspace" title="Studio overview" />
    <section className="studio-hero" aria-labelledby="hero-title">
      <img className="hero-art" src={forest} alt="" />
      <div className="hero-gel" />
      <div className="hero-content">
        <p className="hero-kicker"><Sparkles size={15} aria-hidden="true"/> THE ANIME STORY STUDIO</p>
        <h2 id="hero-title">Every story starts<br/>with <em>a frame.</em></h2>
        <p>Write a story, save your visual direction, and pick up right where you left off.</p>
        <div className="hero-actions"><Link to="/new" className="button button-primary"><Plus size={19} aria-hidden="true" /> New story</Link><Link to="/projects" className="button button-hero"><FolderGlyph /> Browse projects <ArrowRight size={15} aria-hidden="true" /></Link></div>
      </div>
      <p className="hero-caption"><span /> ILLUSTRATED STUDY / 01</p>
    </section>
    <section className="dashboard-section" aria-labelledby="recent-title">
      <div className="section-heading"><div><h2 id="recent-title">Recent projects</h2><p>{mode === 'preview' ? 'Sample stories and locally imported artwork.' : 'Pick up where you left off.'}</p></div>{sample ? <ActionLink to={boardPage(sample.id)}>Open sample storyboard</ActionLink> : <ActionLink to="/projects">All projects</ActionLink>}</div>
      {projects.error && <Warning retry={() => projects.reload()}>{projects.error}</Warning>}
      {projects.loading && !projects.data && <Busy>Loading your drafts…</Busy>}
      {projects.data && (recent.length ? <div className="project-grid">{recent.map(project => <ProjectCard key={project.id} project={project}/>)}</div> : <EmptyProjects/>) }
    </section>
    <section className="dashboard-section workstation" aria-labelledby="workstation-title">
      <div className="section-heading"><div><h2 id="workstation-title">Workstation</h2><p>{mode === 'preview' ? 'Measured in the demo sandbox, not on your PC.' : 'Detected on this device.'}</p></div><ActionLink to="/settings">System details</ActionLink></div>
      {workstation.error && <Warning retry={() => workstation.reload()}>{workstation.error}</Warning>}
      {workstation.loading && !workstation.data && <Busy>Checking available resources…</Busy>}
      {workstation.data && <><WorkstationMetrics hardware={workstation.data} /><div className="runtime-strip"><strong>Optional engines</strong>{workstation.data.engines.map(engine => <Badge key={engine.name} tone={engine.state === 'missing' ? 'quiet' : 'lilac'}>{engine.name}: {engine.state === 'responding' ? 'detected on loopback' : engine.state === 'installed' ? 'executable found' : 'not detected'}</Badge>)}</div></>}
    </section>
  </>
}

function FolderGlyph() {
  return <svg width="17" height="17" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>
}
