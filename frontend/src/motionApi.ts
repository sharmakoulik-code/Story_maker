import { api } from './api'

export const stageWidth = 540, stageHeight = 960, fps = 30, maxFrames = 1800
export type Ease = 'smooth' | 'linear' | 'hold'
export interface Pose { x: number; y: number; scale_x: number; scale_y: number; rotation: number; opacity: number; visible: boolean }
export interface CameraPose { x: number; y: number; zoom: number }
export type Key<T> = T & { frame: number; ease: Ease }
export interface Layer { id: string; name: string; asset: string | null; parent: string | null; pivot_x: number; pivot_y: number; pose: Pose; keys: Key<Pose>[] }
export interface Camera { mode: 'locked' | 'keyframed' | 'tracking'; target: string | null; pose: CameraPose; keys: Key<CameraPose>[] }
export interface Shot { id: string; name: string; frames: number; speed: number; camera: Camera; layers: Layer[] }
export interface Sequence { title: string; shots: Shot[] }
export interface SequenceSummary { id: string; revision: number; title: string; sample: boolean; frames: number; shots: number; updated_at: string }
export interface Asset { id: string; name: string; width: number; height: number; url: string }
export interface SequenceView extends SequenceSummary { document: Sequence; assets: Asset[] }
export type EncoderMode = 'auto' | 'software'
export interface ExportJob { id: string; sequence_id: string; revision: number; state: 'queued' | 'rendering' | 'cancelling' | 'cancelled' | 'failed' | 'complete'; done: number; frames: number; encoder: string | null; message: string; filename: string; output_path: string | null; created_at: string; updated_at: string }

export const motionRoot = '/api/animation'
export const motionPath = (id: string) => `${motionRoot}/${id}`
export const motionPage = (id: string) => `/animation/${id}`
export const exportPath = (id: string, job?: string) => `${motionPath(id)}/exports${job ? `/${job}` : ''}`
export const videoUrl = (id: string, job: string) => `${exportPath(id, job)}/video`
export const activeJob = (job: ExportJob) => ['queued','rendering','cancelling'].includes(job.state)
export const json = (method: 'POST' | 'PUT', data: unknown): RequestInit => ({ method, body: JSON.stringify(data) })
export const loadBlueFlower = () => api<SequenceView>(`${motionRoot}/sample`, { method: 'POST' })
export const newSequence = (title: string) => api<SequenceView>(motionRoot, json('POST',{ title }))
export const saveSequence = (id: string, revision: number, document: Sequence) => api<SequenceView>(motionPath(id), json('PUT',{ revision, document }))
export function importAsset(id: string, image: File) {
  const body = new FormData()
  body.set('image', image)
  return api<Asset>(`${motionPath(id)}/assets`, { method: 'POST', body })
}
export const idFor = (label: string) => `${label}-${crypto.randomUUID().slice(0,8)}`
export const defaultPose: Pose = { x:0, y:0, scale_x:1, scale_y:1, rotation:0, opacity:1, visible:true }
export const defaultCamera: CameraPose = { x:270, y:480, zoom:1 }
export const defaultShot = (name: string): Shot => ({ id:idFor('shot'), name, frames:90, speed:1, camera:{ mode:'locked', target:null, pose:{...defaultCamera}, keys:[] }, layers:[] })
export const shotFrames = (shot: Shot) => Math.ceil(shot.frames / shot.speed)
export const sourceFrame = (shot: Shot, output: number) => Math.min(shot.frames - 1, Math.max(0, output) * shot.speed)
export const duration = (frames: number) => `${(frames / fps).toFixed(2).replace(/0+$/, '').replace(/\.$/,'')}s`
export function timecode(frame: number) {
  return [Math.floor(frame / 1800), Math.floor(frame / 30) % 60, frame % 30].map(value => String(value).padStart(2,'0')).join(':')
}
