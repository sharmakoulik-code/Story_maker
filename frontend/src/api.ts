import { useEffect, useState } from 'react'
import type { PlanStatus } from './planApi'

export type Style = 'storybook' | 'cel' | 'moonlit'
export type Language = 'en' | 'hi' | 'bn'
export type Resolution = '540p' | '720p' | '1080p'
export type Animation = 'subtle' | 'balanced' | 'expressive'
export interface Profile {
  duration_seconds: number
  language: Language
  style: Style
  resolution: Resolution
  fps: 15 | 18 | 24
  animation: Animation
}
export interface Draft { title: string; story: string; profile: Profile }
export interface ProjectSummary {
  id: string
  title: string
  excerpt: string
  profile: Profile
  created_at: string
  updated_at: string
  archived_at: string | null
  plan_status: PlanStatus
}
export interface Project extends ProjectSummary { story: string; folder: string; folder_exists: boolean }
export interface WorkspaceInfo { app: string; version: string; mode: 'local' | 'preview' }
export interface Settings {
  projects_dir: string
  models_dir: string
  outputs_dir: string
  logs_dir: string
  ffmpeg_path: string
  ffprobe_path: string
}
export interface SettingsView { values: Settings; defaults: Settings; data_dir: string; editable: boolean }
export interface StorageReport { path: string; total_bytes: number | null; free_bytes: number | null }
export interface MediaTool { state: 'ready' | 'error' | 'missing'; path: string | null; version: string | null }
export interface HardwareReport {
  os: string
  architecture: string
  mode: 'cpu'
  checked_at: string
  cpu: { name: string | null; physical_cores: number | null; logical_cores: number | null }
  memory: { total_bytes: number | null; available_bytes: number | null }
  gpus: { name: string; memory_bytes: number | null; memory_source: string | null }[]
  storage: Record<'workspace' | 'projects' | 'models' | 'outputs', StorageReport>
  media: { ffmpeg: MediaTool; ffprobe: MediaTool; features: Record<'h264' | 'aac' | 'subtitles', boolean | null> }
  engines: { name: string; state: 'responding' | 'installed' | 'missing'; version: string | null }[]
}

export const languageNames: Record<Language, string> = { en: 'English', hi: 'Hindi', bn: 'Bengali' }
export const styleNames: Record<Style, string> = { storybook: 'Watercolor storybook', cel: 'Cel-shaded anime', moonlit: 'Moonlit ink' }
export const resolutionNames: Record<Resolution, string> = { '540p': '540 × 960', '720p': '720 × 1280', '1080p': '1080 × 1920' }
export const standardProfile: Profile = { duration_seconds: 60, language: 'en', style: 'storybook', resolution: '720p', fps: 24, animation: 'balanced' }

export function describeError(error: unknown) {
  return error instanceof Error ? error.message : 'Something went wrong. Try again.'
}

export async function api<T>(url: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    const headers = new Headers(init?.headers)
    headers.set('Accept', 'application/json')
    if (init?.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
    response = await fetch(url, { ...init, headers })
  } catch (error) {
    if (init?.signal?.aborted) throw error
    throw new Error('Could not reach the studio. Check that it is running and try again.')
  }
  if (!response.ok) {
    const problem = await response.json().catch(() => null)
    if (response.status === 413 && !problem?.detail) throw new Error('This file or request is too large. Try a smaller still image.')
    if (typeof problem?.detail === 'string') throw new Error(problem.detail)
    if (Array.isArray(problem?.detail) && problem.detail.length) {
      const issue = problem.detail[0]
      if (issue.field === 'title') throw new Error('Enter a project title between 1 and 120 characters.')
      if (issue.field === 'story') throw new Error('Story text must be 100,000 characters or fewer.')
      throw new Error(`${issue.field ? `${issue.field}: ` : ''}${issue.message}`)
    }
    throw new Error(`The studio could not complete the request (${response.status}).`)
  }
  return response.json() as Promise<T>
}

type Resource<T> = { path: string; data: T | null; error: string | null; loading: boolean }

export function useResource<T>(path: string) {
  const [request, setRequest] = useState({ count: 0, url: '' })
  const [state, setState] = useState<Resource<T>>({ path, data: null, error: null, loading: true })
  useEffect(() => {
    const controller = new AbortController()
    const actual = request.url && request.url.split('?')[0] === path ? request.url : path
    setState(previous => ({ path, data: previous.path === path ? previous.data : null, error: null, loading: true }))
    api<T>(actual, { signal: controller.signal }).then(
      data => { if (!controller.signal.aborted) setState({ path, data, error: null, loading: false }) },
      error => {
        if (!controller.signal.aborted) setState(previous => ({ ...previous, path, error: describeError(error), loading: false }))
      },
    )
    return () => controller.abort()
  }, [path, request])
  return {
    ...(state.path === path ? state : { path, data: null, error: null, loading: true }),
    reload: (url = '') => setRequest(previous => ({ count: previous.count + 1, url })),
  }
}

export function size(bytes: number | null) {
  if (bytes === null) return 'Unknown'
  const gib = bytes / 1024 ** 3
  return gib >= 1 ? `${gib.toFixed(1)} GiB` : `${Math.round(bytes / 1024 ** 2)} MiB`
}

export function formatDuration(seconds: number) {
  const min = Math.floor(seconds / 60)
  const sec = seconds % 60
  return min ? `${min}m${sec ? ` ${sec}s` : ''}` : `${sec}s`
}

export function dateLabel(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(value))
}
