import { api, type Profile, type ProjectSummary } from './api'

export type PlanStatus = 'not_started' | 'draft' | 'approved' | 'stale'
export const planLabels: Record<PlanStatus, string> = { not_started: 'Not started', draft: 'Plan draft', approved: 'Plan approved', stale: 'Plan out of date' }
export const limits = { scenes: 40, characters: 24, locations: 20, props: 24, dialogue: 32 } as const

export interface StoryArc {
  main_plot: string
  beginning: string
  conflict: string
  emotional_development: string
  climax: string
  ending: string
}
export interface Reference { id: string; name: string; description: string }
export interface CharacterDesign {
  name: string
  description: string
  appearance: string
  face: string
  body: string
  clothing: string
  hair: string
  eyes: string
  accessories: string
  generation_notes: string
  personality: string
  age_range: string
}
export interface Character extends CharacterDesign {
  id: string
  role: 'main' | 'supporting'
  relationships: string
  library_pin: { character_id: string; image_id: string | null } | null
}
export interface StoryBible {
  setting: string
  visual_style: string
  continuity_rules: string
  characters: Character[]
  locations: Reference[]
  props: Reference[]
}
export interface Scene {
  id: string
  title: string
  duration_seconds: number
  narration: string
  dialogue: { character_id: string | null; speaker: string; text: string }[]
  cast: { character_id: string; emotion: string }[]
  location_id: string | null
  environment: string
  prop_ids: string[]
  visual_description: string
  image_prompt_override: string
  camera: string
  animation: string
  sound_effects: string
  transition: 'cut' | 'dissolve' | 'fade_to_black' | 'slide' | 'zoom'
}
export interface PlanDocument { analysis: StoryArc; bible: StoryBible; scenes: Scene[] }
export interface SceneTiming {
  scene_id: string
  number: number
  start_seconds: number
  end_seconds: number
  spoken_words: number
  speech_seconds: number
  minimum_seconds: number
  fits: boolean
  image_prompt: string
}
export interface SavedPlan {
  revision: number
  status: Exclude<PlanStatus, 'not_started'>
  created_at: string
  updated_at: string
  approved_at: string | null
  profile: Profile
  document: PlanDocument
  source: { engine: 'local-rules-v1'; script_hint: string; story_words: number; source_beats: number; spoken_beats: number; excerpts: Record<string, string> }
  timing: { target_seconds: number; planned_seconds: number; words_per_minute: number; spoken_words: number; scenes: SceneTiming[]; issues: string[]; cautions: string[]; can_approve: boolean }
}
export interface PlanView { project: ProjectSummary; has_story: boolean; can_adopt_target: boolean; plan: SavedPlan | null }

export interface PlanHistoryResponse {
  versions: { revision: number; saved_at: string; approved_at: string | null; can_restore: boolean }[]
  next_before: number | null
}

export const transitions: Record<Scene['transition'], string> = {
  cut: 'Cut', dissolve: 'Cross dissolve', fade_to_black: 'Fade to black', slide: 'Slide', zoom: 'Zoom',
}
export function planEndpoint(id: string) { return `/api/projects/${encodeURIComponent(id)}/plan` }
export function planPage(id: string) { return `/projects/${encodeURIComponent(id)}/plan` }
export function generatePlan(id: string, expected: number | null = null) {
  return api<PlanView>(planEndpoint(id), { method: 'POST', body: JSON.stringify({ expected_revision: expected }) })
}
export function stamp(seconds: number) {
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`
}
export function newId(prefix: string) { return `${prefix}-${crypto.randomUUID()}` }
export function newScene(number: number): Scene {
  return { id: newId('scene'), title: `New scene ${number}`, duration_seconds: 4, narration: '', dialogue: [], cast: [], location_id: null, environment: '', prop_ids: [], visual_description: '', image_prompt_override: '', camera: '', animation: '', sound_effects: '', transition: 'cut' }
}
