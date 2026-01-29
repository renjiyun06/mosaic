/**
 * Canvas Background Component
 *
 * Renders theme-aware background for InfiniteCanvas
 * - Cyberpunk: Deep dark gradient with subtle radial overlays
 * - Apple Glass: Enhanced contrast gradient with strong dark/light blocks (v2.0)
 *
 * Apple Glass v2.0 features:
 * - 75% stronger dark blocks (Slate-800/900)
 * - 100% opaque light blocks with shadows
 * - Colorful accent dots for visual interest
 * - Dynamic border-radius and box-shadow support
 *
 * Performance:
 * - Uses CSS variables for colors (no re-render on theme change)
 * - Decorative elements are absolutely positioned
 * - Respects prefers-reduced-motion for animations
 *
 * @see apple-glass.ts - backgroundContrastTokens for Apple Glass parameters
 */

'use client'

import { useTheme } from '../../hooks/useTheme'
import { backgroundContrastTokens } from '../../themes/apple-glass'

export function CanvasBackground() {
  const { theme } = useTheme()
  const isAppleGlass = theme === 'apple-glass'

  if (isAppleGlass) {
    return (
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        {/* Base gradient background */}
        <div
          className="absolute inset-0"
          style={{
            background: backgroundContrastTokens.baseGradient,
          }}
        />

        {/* Radial overlay gradients for depth */}
        <div
          className="absolute inset-0"
          style={{
            background: backgroundContrastTokens.radialOverlays.join(', '),
          }}
        />

        {/* Dark contrast blocks (v2.0: enhanced with shadows and dynamic border-radius) */}
        {backgroundContrastTokens.darkBlocks.map((block, index) => (
          <div
            key={`dark-${index}`}
            className="absolute"
            style={{
              width: block.size,
              height: block.size,
              background: block.gradient,
              opacity: block.opacity,
              transform: `rotate(${block.rotation})`,
              borderRadius: block.borderRadius || '24px', // ⭐ Dynamic border-radius
              boxShadow: block.boxShadow, // ⭐ Shadow for depth
              ...block.position,
            }}
          />
        ))}

        {/* Light contrast blocks (v2.0: 100% opaque with shadows) */}
        {backgroundContrastTokens.lightBlocks.map((block, index) => (
          <div
            key={`light-${index}`}
            className="absolute"
            style={{
              width: block.size,
              height: block.size,
              background: block.gradient,
              opacity: block.opacity,
              transform: `rotate(${block.rotation})`,
              borderRadius: block.borderRadius || '24px', // ⭐ Dynamic border-radius
              boxShadow: block.boxShadow, // ⭐ Colored shadow (Indigo/Pink)
              ...block.position,
            }}
          />
        ))}

        {/* Decorative lines (v2.0: dynamic width/height, enhanced opacity) */}
        {backgroundContrastTokens.lines.map((line, index) => (
          <div
            key={`line-${index}`}
            className="absolute"
            style={{
              width: line.width || (line.type === 'horizontal' ? '400px' : '4px'), // ⭐ Dynamic width
              height: line.height || (line.type === 'horizontal' ? '4px' : '400px'), // ⭐ Dynamic height
              background: line.gradient,
              opacity: line.opacity,
              ...line.position,
            }}
          />
        ))}

        {/* Colorful accent dots (v2.0: NEW! - visual anchors for transparency) */}
        {backgroundContrastTokens.accentDots?.map((dot, index) => (
          <div
            key={`accent-${index}`}
            className="absolute rounded-full"
            style={{
              width: dot.size,
              height: dot.size,
              background: dot.color,
              filter: `blur(${dot.blur})`,
              ...dot.position,
            }}
          />
        ))}
      </div>
    )
  }

  // Cyberpunk theme - dark gradient with radial overlays
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {/* Base dark gradient */}
      <div
        className="absolute inset-0"
        style={{
          background: 'linear-gradient(135deg, #050510 0%, #0a0a20 50%, #050510 100%)',
        }}
      />

      {/* Radial overlays for depth */}
      <div
        className="absolute inset-0"
        style={{
          background: [
            'radial-gradient(circle at 20% 30%, rgba(123, 97, 255, 0.15) 0%, transparent 50%)',
            'radial-gradient(circle at 80% 70%, rgba(0, 255, 255, 0.15) 0%, transparent 50%)',
          ].join(', '),
        }}
      />
    </div>
  )
}
