/**
 * Zone management page — Tenant users only (not rendered for partner tokens).
 *
 * Features:
 * - Select camera → load snapshot image
 * - Draw polygon by clicking on the canvas (click to add vertices, double-click to close)
 * - Choose zone name + type (including staff_exclusion)
 * - Save → POST /v1/zones persisting the polygon + type via RLS
 */
import { useEffect, useRef, useState } from 'react'
import { cameras, zones } from '../api/client'
import type { Camera, ZoneType } from '../types'

const ZONE_TYPES: { value: ZoneType; label: string }[] = [
  { value: 'shelf',           label: 'Góndola / Estante' },
  { value: 'entrance',        label: 'Entrada' },
  { value: 'exit',            label: 'Salida' },
  { value: 'checkout',        label: 'Caja' },
  { value: 'staff_exclusion', label: 'Área de Personal (Staff Exclusion)' },
  { value: 'generic',         label: 'Genérica' },
]

interface Point { x: number; y: number }

export function Zones() {
  const [cameraList, setCameraList] = useState<Camera[]>([])
  const [selectedCam, setSelectedCam] = useState<string>('')
  const [points, setPoints] = useState<Point[]>([])
  const [closed, setClosed] = useState(false)
  const [zoneName, setZoneName] = useState('')
  const [zoneType, setZoneType] = useState<ZoneType>('shelf')
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState('')
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const imgRef = useRef<HTMLImageElement | null>(null)

  // Load cameras (all sites — admin context)
  useEffect(() => {
    cameras.bySite('all').catch(() =>
      // fallback: fetch without site filter
      fetch('/v1/cameras', { headers: { Authorization: `Bearer ${localStorage.getItem('traxia_token') ?? ''}` } })
        .then(r => r.json())
        .then(setCameraList)
        .catch(() => {})
    )
    // for dev/test, load camera list with a broad query
    fetch('/v1/cameras', {
      headers: { Authorization: `Bearer ${localStorage.getItem('traxia_token') ?? ''}` }
    }).then(r => r.ok ? r.json() : []).then(setCameraList).catch(() => {})
  }, [])

  // Redraw canvas when points change
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.clearRect(0, 0, canvas.width, canvas.height)

    // Draw snapshot image if loaded
    if (imgRef.current) {
      ctx.drawImage(imgRef.current, 0, 0, canvas.width, canvas.height)
    } else {
      ctx.fillStyle = '#e2e8f0'
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      ctx.fillStyle = '#94a3b8'
      ctx.font = '14px system-ui'
      ctx.textAlign = 'center'
      ctx.fillText(
        selectedCam ? 'Snapshot no disponible — dibuja sobre la cuadrícula' : 'Selecciona una cámara',
        canvas.width / 2, canvas.height / 2,
      )
    }

    if (!points.length) return

    // Draw polygon fill (semi-transparent)
    const color = zoneType === 'staff_exclusion' ? '239,68,68' : '14,165,233'
    ctx.beginPath()
    ctx.moveTo(points[0].x, points[0].y)
    points.slice(1).forEach(p => ctx.lineTo(p.x, p.y))
    if (closed) ctx.closePath()
    ctx.strokeStyle = `rgb(${color})`
    ctx.lineWidth = 2
    ctx.fillStyle = `rgba(${color},0.15)`
    ctx.fill()
    ctx.stroke()

    // Draw vertex dots
    points.forEach((p, i) => {
      ctx.beginPath()
      ctx.arc(p.x, p.y, i === 0 ? 6 : 4, 0, Math.PI * 2)
      ctx.fillStyle = i === 0 ? `rgb(${color})` : '#fff'
      ctx.strokeStyle = `rgb(${color})`
      ctx.lineWidth = 2
      ctx.fill()
      ctx.stroke()
    })
  }, [points, closed, zoneType, selectedCam])

  function handleCanvasClick(e: React.MouseEvent<HTMLCanvasElement>) {
    if (closed) return
    const rect = canvasRef.current!.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    setPoints(prev => [...prev, { x, y }])
  }

  function handleCanvasDblClick() {
    if (points.length >= 3) setClosed(true)
  }

  function reset() {
    setPoints([])
    setClosed(false)
    setSaveMsg('')
  }

  async function handleSave() {
    if (!closed || !selectedCam || !zoneName.trim()) return
    setSaving(true)
    setSaveMsg('')
    try {
      await zones.create({
        camera_id: selectedCam,
        name: zoneName.trim(),
        zone_type: zoneType,
        coordinates: { type: 'polygon', points: points.map(p => [Math.round(p.x), Math.round(p.y)]) },
      })
      setSaveMsg('Zona guardada correctamente.')
      reset()
    } catch (e: unknown) {
      setSaveMsg(`Error: ${e instanceof Error ? e.message : e}`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Zonas / Cámaras</h1>
      <p style={{ color: '#64748b', marginBottom: 24, fontSize: 14 }}>
        Dibuja polígonos sobre el snapshot para definir zonas de análisis.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 280px', gap: 24 }}>
        {/* Canvas area */}
        <div style={{ background: '#fff', borderRadius: 12, padding: 20, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ fontSize: 13, color: '#64748b', display: 'block', marginBottom: 6 }}>Cámara</label>
            <select
              data-testid="camera-select"
              value={selectedCam}
              onChange={e => { setSelectedCam(e.target.value); reset() }}
              style={{ padding: '8px 12px', border: '1px solid #e2e8f0', borderRadius: 6, fontSize: 14, width: '100%' }}
            >
              <option value="">— Selecciona —</option>
              {cameraList.map(c => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>

          <canvas
            ref={canvasRef}
            data-testid="zone-canvas"
            width={640}
            height={360}
            onClick={handleCanvasClick}
            onDoubleClick={handleCanvasDblClick}
            style={{
              width: '100%', height: 'auto', cursor: closed ? 'default' : 'crosshair',
              border: '1px solid #e2e8f0', borderRadius: 8, display: 'block',
            }}
          />
          <p style={{ fontSize: 12, color: '#94a3b8', marginTop: 8 }}>
            {closed
              ? 'Polígono cerrado. Completa el formulario y guarda.'
              : 'Clic para agregar vértices • Doble clic para cerrar el polígono (mín. 3 puntos)'}
          </p>
        </div>

        {/* Controls */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ background: '#fff', borderRadius: 12, padding: 20, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
            <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Propiedades de la zona</h3>

            <label style={labelStyle}>Nombre</label>
            <input
              data-testid="zone-name-input"
              value={zoneName}
              onChange={e => setZoneName(e.target.value)}
              placeholder="ej. Góndola B3"
              style={inputStyle}
            />

            <label style={labelStyle}>Tipo de zona</label>
            <select
              data-testid="zone-type-select"
              value={zoneType}
              onChange={e => setZoneType(e.target.value as ZoneType)}
              style={inputStyle}
            >
              {ZONE_TYPES.map(t => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>

            {zoneType === 'staff_exclusion' && (
              <div style={{
                background: '#fef2f2', border: '1px solid #fecaca',
                borderRadius: 6, padding: 10, marginTop: 4, fontSize: 12, color: '#b91c1c',
              }}>
                Esta zona se excluirá de los conteos agregados de clientes.
              </div>
            )}

            <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
              <button
                data-testid="zone-save-btn"
                onClick={handleSave}
                disabled={!closed || !zoneName.trim() || saving}
                style={{
                  flex: 1, padding: '10px', background: (!closed || !zoneName.trim() || saving) ? '#94a3b8' : '#0ea5e9',
                  color: '#fff', border: 'none', borderRadius: 6,
                  fontSize: 14, fontWeight: 600, cursor: 'pointer',
                }}
              >
                {saving ? 'Guardando…' : 'Guardar zona'}
              </button>
              <button
                onClick={reset}
                style={{ padding: '10px', background: '#f1f5f9', border: 'none', borderRadius: 6, fontSize: 14, cursor: 'pointer' }}
              >
                Limpiar
              </button>
            </div>

            {saveMsg && (
              <p data-testid="zone-save-msg" style={{ marginTop: 12, fontSize: 13, color: saveMsg.startsWith('Error') ? '#ef4444' : '#16a34a' }}>
                {saveMsg}
              </p>
            )}
          </div>

          <div style={{ background: '#fff', borderRadius: 12, padding: 20, boxShadow: '0 1px 4px rgba(0,0,0,0.06)', fontSize: 13, color: '#64748b' }}>
            <p style={{ fontWeight: 600, marginBottom: 8, color: '#1e293b' }}>Polígono actual</p>
            <p>Vértices: {points.length}</p>
            <p>Estado: {closed ? '✓ Cerrado' : 'Abierto'}</p>
          </div>
        </div>
      </div>
    </div>
  )
}

const labelStyle: React.CSSProperties = { display: 'block', fontSize: 12, color: '#64748b', marginBottom: 4, marginTop: 12 }
const inputStyle: React.CSSProperties = { width: '100%', padding: '8px 10px', border: '1px solid #e2e8f0', borderRadius: 6, fontSize: 14 }
