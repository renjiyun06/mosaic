'use client'

import { Tldraw, TLUiOverrides, createShapeId } from 'tldraw'
import 'tldraw/tldraw.css'
import { GeoGebraShapeUtil } from './GeoGebraShape'

// Custom shape utilities
const customShapeUtils = [GeoGebraShapeUtil]

// Global counter: track GeoGebra instance number
let geogebraInstanceCounter = 0

// Custom UI toolbar
const uiOverrides: TLUiOverrides = {
  tools(editor, tools) {
    // Add GeoGebra tool button
    tools.geogebra = {
      id: 'geogebra',
      icon: 'geo-icon',
      label: 'GeoGebra',
      kbd: 'g',
      onSelect: () => {
        // Create GeoGebra shape
        geogebraInstanceCounter++ // Increment counter
        const id = createShapeId()
        const viewport = editor.getViewportPageBounds()
        const centerX = viewport.x + viewport.w / 2
        const centerY = viewport.y + viewport.h / 2
        editor.createShapes([{
          id,
          type: 'geogebra',
          x: centerX - 405,
          y: centerY - 316,
          props: {
            instanceNumber: geogebraInstanceCounter,
          },
        }])
        editor.setSelectedShapes([id])
        editor.setCurrentTool('select')
      },
    }
    return tools
  },
}

interface TldrawCanvasProps {
  onEditorReady?: (editor: any) => void
}

export default function TldrawCanvas({ onEditorReady }: TldrawCanvasProps) {
  return (
    <div style={{ width: '100%', height: '100%' }}>
      <Tldraw
        shapeUtils={customShapeUtils}
        overrides={uiOverrides}
        onMount={(editor) => {
          if (onEditorReady) {
            onEditorReady(editor)
          }
        }}
      />
    </div>
  )
}
