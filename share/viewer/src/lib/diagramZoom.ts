export const MIN_DIAGRAM_ZOOM = 0.5
export const MAX_DIAGRAM_ZOOM = 2.5
export const DIAGRAM_ZOOM_STEP = 0.15

export type DiagramZoomAction = 'in' | 'out' | 'reset'

export function getNextDiagramZoom(current: number, action: DiagramZoomAction): number {
  if (action === 'reset') return 1

  const next = action === 'in' ? current + DIAGRAM_ZOOM_STEP : current - DIAGRAM_ZOOM_STEP
  return clampZoom(next)
}

export function clampZoom(value: number): number {
  const clamped = Math.min(MAX_DIAGRAM_ZOOM, Math.max(MIN_DIAGRAM_ZOOM, value))
  return Math.round(clamped * 100) / 100
}
