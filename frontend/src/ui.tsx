import { AlertCircle, ArrowRight, ChevronRight, Clapperboard, FolderOpen, LayoutGrid, LoaderCircle, SlidersHorizontal, SquarePen, UsersRound, WifiOff } from 'lucide-react'
import { createContext, useContext, useEffect, type ReactNode } from 'react'
import { Link, NavLink, Outlet, useBlocker, useLocation } from 'react-router-dom'
import { useResource, type WorkspaceInfo } from './api'

const WorkspaceMode = createContext<WorkspaceInfo['mode'] | null>(null)
export const useWorkspaceMode = () => useContext(WorkspaceMode)

export function useWarnUnsaved(shouldWarn: boolean, message: string) {
  const blocker = useBlocker(shouldWarn)
  useEffect(() => {
    if (blocker.state !== 'blocked') return
    if (window.confirm(message)) blocker.proceed()
    else blocker.reset()
  }, [blocker, message])
  useEffect(() => {
    if (!shouldWarn) return
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = true }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [shouldWarn])
}

export function ActionLink({ to, children, className = '' }: { to: string; children: ReactNode; className?: string }) {
  return <Link className={`action-link ${className}`} to={to}>{children}<ArrowRight size={16} aria-hidden="true" /></Link>
}

export function Badge({ children, tone = 'quiet' }: { children: ReactNode; tone?: 'quiet' | 'mint' | 'lilac' | 'amber' }) {
  return <span className={`badge badge-${tone}`}>{children}</span>
}

export function PageHeading({ label, title, children, actions }: { label: string; title: string; children?: ReactNode; actions?: ReactNode }) {
  return <div className="page-heading"><div className="min-w-0"><p className="eyebrow">{label}</p><h1>{title}</h1>{children && <div className="page-lede">{children}</div>}</div>{actions && <div className="page-actions">{actions}</div>}</div>
}

export function Warning({ children, retry }: { children: ReactNode; retry?: () => void }) {
  return <div className="notice notice-error" role="alert"><AlertCircle size={18} aria-hidden="true"/><div>{children}</div>{retry && <button className="text-button" type="button" onClick={retry}>Try again</button>}</div>
}

export function Busy({ children = 'Loading from the studio…' }: { children?: ReactNode }) {
  return <div className="busy" role="status"><LoaderCircle size={17} aria-hidden="true" /> {children}</div>
}

const links = [
  { to: '/', icon: LayoutGrid, label: 'Overview' },
  { to: '/new', icon: SquarePen, label: 'New story' },
  { to: '/projects', icon: FolderOpen, label: 'My projects' },
  { to: '/characters', icon: UsersRound, label: 'Character Library' },
  { to: '/animation', icon: Clapperboard, label: 'Animation Studio' },
]

export function StudioShell() {
  const { data: info } = useResource<WorkspaceInfo>('/api/health')
  const location = useLocation()
  const library = location.pathname.startsWith('/projects')
  const isProject = library && location.pathname !== '/projects' && location.pathname !== '/projects/'
  const isPlan = isProject && /\/plan\/?$/.test(location.pathname)
  const projectCrumb = isPlan ? 'Story plan' : /\/storyboard\/?$/.test(location.pathname) ? 'Storyboard' : 'Story draft'
  const current = location.pathname === '/' ? 'Overview' : location.pathname.startsWith('/new') ? 'New story' : library ? 'My projects' : location.pathname.startsWith('/characters') ? 'Character Library' : location.pathname.startsWith('/animation') ? 'Animation Studio' : location.pathname.startsWith('/settings') ? 'System & models' : 'Not found'
  const preview = info?.mode === 'preview'
  useEffect(() => {
    document.title = `${isProject ? projectCrumb : current} · Koma Studio`
    window.scrollTo(0, 0)
  }, [current, isProject, projectCrumb, location.pathname])
  return (
    <WorkspaceMode.Provider value={info?.mode ?? null}>
      <a className="skip-link" href="#main">Skip to content</a>
      <div className="studio-shell">
        <aside className="sidebar">
          <Link className="brand" to="/" aria-label="Koma Studio overview"><img src="/koma.svg" alt="" width="39" height="39" /><span className="brand-type"><strong>Koma<span> Studio</span></strong><small>ANIME WORKSPACE</small></span></Link>
          <nav className="navigation" aria-label="Main navigation">
            <div className="nav-group"><p className="eyebrow nav-label">Workspace</p>
              {links.map(({ to, icon: Icon, label }) => <NavLink key={to} to={to} end={to === '/'} className="nav-link" title={label}><Icon size={19} aria-hidden="true" /><span>{label}</span></NavLink>)}
            </div>
            <div className="nav-group"><p className="eyebrow nav-label">Preferences</p><NavLink to="/settings" className="nav-link" title="System & models"><SlidersHorizontal size={19} aria-hidden="true" /><span>System & models</span></NavLink></div>
          </nav>
          <div className="sidebar-footer">
            <div className="sidebar-mode"><span className={`status-dot ${preview ? 'dot-amber' : info ? 'dot-mint' : ''}`}/><div><strong>{preview ? 'Demo workspace' : info ? 'On this device' : 'Koma workspace'}</strong><small>{preview ? 'Use sample content only' : 'No cloud account required'}</small></div></div>
            {info && <p className="edition"><Clapperboard size={13} aria-hidden="true"/> Motion & export <span>v{info.version}</span></p>}
          </div>
        </aside>
        <div className="stage min-w-0">
          <header className="topbar">
            <nav className="breadcrumbs" aria-label="Breadcrumb">
              <Link to="/" className="crumb-home">Workspace</Link><ChevronRight size={14} aria-hidden="true"/>
              {isProject ? <><Link to="/projects">My projects</Link><ChevronRight size={14} aria-hidden="true"/><span aria-current="page">{projectCrumb}</span></> : <span aria-current="page">{current}</span>}
            </nav>
            {info && <span className={`connection ${preview ? 'connection-demo' : ''}`}><WifiOff size={15} aria-hidden="true"/><span>{preview ? 'Demo preview' : 'Local only'}</span></span>}
          </header>
          <main id="main" className="page-content" tabIndex={-1}><Outlet /></main>
        </div>
      </div>
    </WorkspaceMode.Provider>
  )
}

export function MissingPage() {
  return <><PageHeading label="Workspace" title="Page not found">This page isn’t part of the studio.</PageHeading><ActionLink to="/">Back to overview</ActionLink></>
}
