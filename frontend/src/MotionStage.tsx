import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react'
import { LockKeyhole, Scan, Video } from 'lucide-react'
import { stageHeight, stageWidth, type Asset, type Shot } from './motionApi'
import { evaluateFrame } from './motionMath'

export function MotionStage({ shot, next, frame, globalFrame, assets, children }: { shot: Shot; next?: Shot; frame: number; globalFrame: number; assets: Asset[]; children: ReactNode }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const images = useRef(new Map<string, HTMLImageElement>())
  const failed = useRef(new Set<string>())
  const [version,setVersion] = useState(0)
  const keys = [...new Set([shot, ...(next ? [next] : [])].flatMap(item => item.layers.flatMap(layer => layer.asset || [])))].sort().join(',')
  useEffect(() => {
    const current = images.current, errors = failed.current
    const desired = new Set(keys.split(',').filter(Boolean))
    for (const key of [...current.keys(),...errors]) if (!desired.has(key)) { current.delete(key); errors.delete(key) }
    for (const key of desired) {
      if (current.get(key)?.naturalWidth || errors.has(key)) continue
      const asset = assets.find(item => item.id === key)
      if (!asset) continue
      const image = new Image()
      current.set(key,image)
      image.onload = () => { if (current.get(key) === image) setVersion(value => value + 1) }
      image.onerror = () => { if (current.get(key) === image) { errors.add(key); setVersion(value => value + 1) } }
      image.src = asset.url
    }
    return () => { for (const [key,image] of current) if (!image.complete) current.delete(key) }
  }, [keys, assets])
  const missing = shot.layers.some(layer => layer.asset && failed.current.has(layer.asset))
  const hasAssets = shot.layers.some(layer => layer.asset)
  const loading = shot.layers.some(layer => layer.asset && !images.current.get(layer.asset)?.naturalWidth)
  useLayoutEffect(() => {
    const ctx = canvas.current?.getContext('2d', { alpha:false })
    if (!ctx) return
    const { draws } = evaluateFrame(shot, frame)
    ctx.setTransform(1,0,0,1,0,0)
    ctx.globalAlpha = 1
    ctx.fillStyle = '#09101c'
    ctx.fillRect(0,0,stageWidth,stageHeight)
    ctx.imageSmoothingEnabled = true
    for (const draw of draws) {
      const image = images.current.get(draw.asset)
      if (image?.naturalWidth) {
        ctx.setTransform(...draw.matrix)
        ctx.globalAlpha = draw.opacity
        ctx.drawImage(image,0,0)
      }
    }
  }, [shot, frame, version])
  return <div className="motion-stage panel" aria-label="Animation preview">
    <header><span><Video size={15}/> Camera preview</span><span className={shot.camera.mode === 'locked' ? 'motion-lock' : ''}>{shot.camera.mode === 'locked' ? <><LockKeyhole size={13}/> Locked camera</> : <><Scan size={13}/> {shot.camera.mode === 'tracking' ? 'Tracking camera' : 'Keyframed camera'}</>}</span></header>
    <div className="motion-screen">
      <div className="motion-canvas"><canvas ref={canvas} width={stageWidth} height={stageHeight} data-frame={globalFrame} data-ready={!loading} aria-label="Rendered animation frame" />
        {!hasAssets && <div className="motion-screen-message">Import a background or transparent layer to start this shot.</div>}
        {missing && <div className="motion-screen-message">A layer’s image is unavailable.</div>}
        {loading && !missing && <div className="motion-screen-message">Loading local layers…</div>}
      </div>
    </div>
    {children}
  </div>
}
