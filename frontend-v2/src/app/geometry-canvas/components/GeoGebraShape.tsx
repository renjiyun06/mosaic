'use client'

import {
  BaseBoxShapeUtil,
  HTMLContainer,
  TLBaseShape,
  useEditor,
} from 'tldraw'
import { useEffect, useRef } from 'react'

// Global storage: instance number -> GeoGebra API
const geogebraAPIs = new Map<number, any>()

// Export function to get API (for external use)
export function getGeoGebraAPI(instanceNumber: number): any | null {
  return geogebraAPIs.get(instanceNumber) || null
}

// Define GeoGebra shape type
export type GeoGebraShape = TLBaseShape<
  'geogebra',
  {
    w: number
    h: number
    instanceNumber: number
    appletId?: string
  }
>

// Define GeoGebra shape utility class
export class GeoGebraShapeUtil extends BaseBoxShapeUtil<GeoGebraShape> {
  static override type = 'geogebra' as const

  // Default properties
  getDefaultProps(): GeoGebraShape['props'] {
    const BASE_WIDTH = 800
    const BASE_HEIGHT = 450
    return {
      w: BASE_WIDTH,
      h: BASE_HEIGHT,
      instanceNumber: 1,
    }
  }

  // Basic configuration
  override canBind = () => false
  override canEdit = () => true
  override canResize = () => true
  override canCrop = () => false
  override isAspectRatioLocked = () => true // Lock aspect ratio 800:450

  // Enable native pointer events (allow GeoGebra to receive user interaction)
  override allowPointerEvents = () => true

  // Render component
  component(shape: GeoGebraShape) {
    const editor = useEditor()
    const containerRef = useRef<HTMLDivElement>(null)

    // Base dimensions (GeoGebra fixed creation size)
    const BASE_WIDTH = 800
    const BASE_HEIGHT = 450

    // Actual render dimensions (user-adjusted size, tldraw ensures 800:450 ratio)
    const actualWidth = shape.props.w
    const actualHeight = shape.props.h

    // Calculate scale ratio
    const scale = actualWidth / BASE_WIDTH

    // Initialize GeoGebra (execute only once on creation)
    useEffect(() => {
      if (typeof window === 'undefined' || !containerRef.current) return
      if (!(window as any).GGBApplet) {
        console.warn('GGBApplet not loaded yet')
        return
      }

      const containerId = `ggb-container-${shape.id}`
      const container = containerRef.current

      // Clear container
      container.innerHTML = ''

      // Create GeoGebra div
      const ggbDiv = document.createElement('div')
      ggbDiv.id = containerId
      container.appendChild(ggbDiv)

      const params = {
        appName: 'classic',
        width: BASE_WIDTH,
        height: BASE_HEIGHT,
        showToolBar: true,
        showAlgebraInput: true,
        showMenuBar: true,
        enableRightClick: true,
        enableShiftDragZoom: true,
        borderColor: null,
        appletOnLoad: (api: any) => {
          console.log(`GeoGebra API loaded for instance #${shape.props.instanceNumber}`)
          geogebraAPIs.set(shape.props.instanceNumber, api)
        },
      }

      const applet = new (window as any).GGBApplet(params, true)
      applet.inject(containerId)

      return () => {
        geogebraAPIs.delete(shape.props.instanceNumber)
      }
    }, [shape.id, shape.props.instanceNumber])

    return (
      <HTMLContainer
        style={{
          width: actualWidth,
          height: actualHeight,
          pointerEvents: 'auto',
          overflow: 'hidden',
          border: '2px solid hsl(var(--primary))',
          borderRadius: '6px',
          backgroundColor: 'hsl(var(--background))',
        }}
      >
        {/* GeoGebra scaling container */}
        <div
          ref={containerRef}
          style={{
            width: `${BASE_WIDTH}px`,
            height: `${BASE_HEIGHT}px`,
            transform: `scale(${scale})`,
            transformOrigin: 'top left',
            pointerEvents: 'auto',
          }}
          onPointerDown={(e) => {
            editor.markEventAsHandled(e)
          }}
          onPointerUp={(e) => {
            editor.markEventAsHandled(e)
          }}
          onPointerMove={(e) => {
            editor.markEventAsHandled(e)
          }}
          onClick={(e) => {
            editor.markEventAsHandled(e)
          }}
        />
      </HTMLContainer>
    )
  }

  indicator(shape: GeoGebraShape) {
    return <rect width={shape.props.w} height={shape.props.h} />
  }
}
