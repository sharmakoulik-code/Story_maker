// Mirrors backend/motion/engine.py. Native images are 2× the logical stage.
import { sourceFrame, stageHeight, stageWidth, type CameraPose, type Key, type Pose, type Shot } from './motionApi'
export type Matrix = [number, number, number, number, number, number]
export type Draw = { id: string; asset: string; matrix: Matrix; opacity: number }
const half: Matrix = [.5,0,0,.5,0,0]
export function multiply([a,b,c,d,e,f]: Matrix, [u,v,w,z,x,y]: Matrix): Matrix {
  return [a*u+c*v,b*u+d*v,a*w+c*z,b*w+d*z,a*x+c*y+e,b*x+d*y+f]
}
export function sample<T extends Pose | CameraPose>(base: T, keys: Key<T>[], frame: number): T {
  let index = keys.findIndex(key => key.frame > frame)
  if (index === -1) index = keys.length
  const before = index ? keys[index-1] : base
  if (index === keys.length || keys[index].ease === 'hold') return before
  const after = keys[index], start = index ? keys[index-1].frame : 0
  let t = (frame-start)/(after.frame-start)
  if (after.ease === 'smooth') t = t*t*(3-2*t)
  const result = { ...base }
  for (const field of Object.keys(base) as (keyof T)[]) {
    const a = before[field], b = after[field]
    result[field] = (typeof a === 'number' && typeof b === 'number' && a !== b ? a+(b-a)*t : a) as T[keyof T]
  }
  return result
}
export function evaluateFrame(shot: Shot, output: number): { projection: Matrix; draws: Draw[] } {
  const time = sourceFrame(shot,output), byId = new Map(shot.layers.map(layer => [layer.id,layer]))
  const ready = new Map<string,[Matrix,number]>()
  function world(id: string): [Matrix, number] {
    const known = ready.get(id)
    if (known) return known
    const layer = byId.get(id)!
    const p = sample(layer.pose,layer.keys,time), t = p.rotation * Math.PI/180
    const a = Math.cos(t)*p.scale_x, b = Math.sin(t)*p.scale_x, c = -Math.sin(t)*p.scale_y, d = Math.cos(t)*p.scale_y
    let matrix: Matrix = [a,b,c,d,p.x-a*layer.pivot_x-c*layer.pivot_y,p.y-b*layer.pivot_x-d*layer.pivot_y]
    let opacity = p.visible ? p.opacity : 0
    if (layer.parent) {
      const [parent, alpha] = world(layer.parent)
      matrix = multiply(parent,matrix); opacity *= alpha
    }
    const result: [Matrix,number] = [matrix, opacity]
    ready.set(id,result)
    return result
  }
  const camera = shot.camera
  const v = camera.mode === 'locked' ? camera.pose : sample(camera.pose,camera.keys,time)
  let { x,y,zoom } = v
  const target = camera.mode === 'tracking' && camera.target ? byId.get(camera.target) : null
  if (target) {
    const [m] = world(target.id)
    x += m[0]*target.pivot_x + m[2]*target.pivot_y + m[4]
    y += m[1]*target.pivot_x + m[3]*target.pivot_y + m[5]
  }
  const projection: Matrix = [zoom,0,0,zoom,stageWidth/2-x*zoom,stageHeight/2-y*zoom]
  const draws: Draw[] = []
  for (const layer of shot.layers) {
    if (!layer.asset) continue
    const [m,opacity] = world(layer.id)
    if (opacity > 0) draws.push({ id:layer.id, asset:layer.asset, matrix:multiply(multiply(projection,m),half), opacity })
  }
  return { projection, draws }
}
