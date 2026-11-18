import { ArrowRight, BookOpen, FileText, Film } from 'lucide-react'
import { useId } from 'react'
import { NavLink } from 'react-router-dom'
import type { ProjectSummary } from './api'
import { planLabels, planPage } from './planApi'
import { Badge } from './ui'
import { boardPage } from './visualApi'

export function ProjectSteps({ project }: { project: ProjectSummary }) {
  const status = project.plan_status
  return <nav className="production-nav" aria-label="Project workflow">
    <NavLink to={`/projects/${project.id}`} end><span className="step-num">01</span><FileText size={16} aria-hidden="true"/><strong>Story draft</strong></NavLink>
    <ArrowRight size={13} aria-hidden="true" className="step-arrow"/>
    <NavLink to={planPage(project.id)}><span className="step-num">02</span><BookOpen size={16} aria-hidden="true"/><strong>Story plan</strong><Badge tone={status === 'approved' ? 'mint' : status === 'stale' ? 'amber' : status === 'draft' ? 'lilac' : 'quiet'}>{planLabels[status]}</Badge></NavLink>
    <ArrowRight size={13} aria-hidden="true" className="step-arrow"/>
    <NavLink to={boardPage(project.id)}><span className="step-num">03</span><Film size={16} aria-hidden="true"/><strong>Storyboard</strong></NavLink>
  </nav>
}

export function NoteField({ label, value, onChange, rows = 3, placeholder, maxLength = 1800 }: {
  label: string; value: string; onChange: (value: string) => void; rows?: number; placeholder?: string; maxLength?: number;
}) {
  const id = useId()
  return <div className="field"><label htmlFor={id}>{label}</label><textarea id={id} spellCheck={false} autoComplete="off" maxLength={maxLength} rows={rows} value={value} onChange={event => onChange(event.target.value)} placeholder={placeholder}/></div>
}

export function LineField({ label, value, onChange, placeholder, required = false }: {
  label: string; value: string; onChange: (value: string) => void; placeholder?: string; required?: boolean;
}) {
  return <label className="field"><span>{label}</span><input autoComplete="off" spellCheck={false} maxLength={120} value={value} required={required} onChange={event => onChange(event.target.value)} placeholder={placeholder}/></label>
}
