import { api } from './api'
import type { Character, CharacterDesign, PlanView } from './planApi'

export interface StillVersion {
  id: string
  number: number
  original_name: string
  source: string
  license_note: string
  width: number
  height: number
  bytes: number
  created_at: string
  last_approved_at: string | null
  available: boolean
}
export interface StillHistory { versions: StillVersion[]; next_before: number | null }
export interface LibraryCharacter {
  id: string
  revision: number
  design: CharacterDesign
  reference: StillVersion | null
  reference_count: number
  created_at: string
  updated_at: string
  archived_at: string | null
}
export type ShotStatus = 'empty' | 'review' | 'approved' | 'changed' | 'missing'
export interface BoardShot {
  scene_id: string
  title: string
  revision: number
  active: StillVersion | null
  version_count: number
  status: ShotStatus
}
export interface StoryboardView { plan: PlanView; shots: BoardShot[]; off_board: BoardShot[]; off_board_count: number }

export const shotLabels: Record<ShotStatus, string> = { empty: 'No frame', review: 'Needs review', approved: 'Approved', changed: 'Direction changed', missing: 'File missing' }
export const libraryPath = '/api/characters'
export const charPath = (id: string) => `${libraryPath}/${encodeURIComponent(id)}`
export const boardPage = (id: string) => `/projects/${encodeURIComponent(id)}/storyboard`
export const boardPath = (id: string) => `/api${boardPage(id)}`
export const shotPath = (project: string, scene: string) => `${boardPath(project)}/${encodeURIComponent(scene)}`
export const imageUrl = (id: string, thumbnail = false) => `/api/images/${encodeURIComponent(id)}${thumbnail ? '?thumbnail=true' : ''}`
export const imageBytes = (bytes: number) => bytes >= 1024 ** 2 ? `${(bytes / 1024 ** 2).toFixed(1)} MiB` : `${Math.max(1, Math.round(bytes / 1024))} KiB`
export const maxImageBytes = 16 * 1024 ** 2

export const blankDesign = (name = ''): CharacterDesign => ({
  name, description: '', appearance: '', face: '', body: '', clothing: '', hair: '', eyes: '', accessories: '', generation_notes: '', personality: '', age_range: '',
})
export function copyDesign(entry: Character): CharacterDesign {
  const { id: _id, role: _role, relationships: _relationships, library_pin: _pin, ...design } = entry
  return design
}
export function fromLibrary(item: LibraryCharacter) {
  return { ...item.design, library_pin: { character_id: item.id, image_id: item.reference?.id ?? null } }
}
export function jsonMutation<T>(path: string, method: 'PUT' | 'POST', data: unknown) {
  return api<T>(path, { method, body: JSON.stringify(data) })
}
