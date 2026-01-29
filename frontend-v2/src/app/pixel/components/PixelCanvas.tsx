"use client"

/**
 * PixelCanvas - Main PixiJS canvas component
 * Renders the pixel art game-style visualization
 */

import { useEffect, useRef } from "react"
import * as PIXI from "pixi.js"

export function PixelCanvas() {
  const canvasRef = useRef<HTMLDivElement>(null)
  const appRef = useRef<PIXI.Application | null>(null)

  useEffect(() => {
    if (!canvasRef.current || appRef.current) return

    // Initialize PixiJS Application
    const initPixi = async () => {
      const app = new PIXI.Application()

      await app.init({
        width: window.innerWidth,
        height: window.innerHeight,
        backgroundColor: 0x1a1a2e,
        resolution: window.devicePixelRatio || 1,
        autoDensity: true,
        antialias: false, // CRITICAL: Disable antialiasing for pixel art
      })

      canvasRef.current?.appendChild(app.canvas as HTMLCanvasElement)
      appRef.current = app

      // Load textures
      await loadAssets(app)

      // Create dungeon background
      createDungeonBackground(app)

      // Add decorations (pond, rocks, variations)
      createDecorations(app)

      // Create test nodes (pixel characters)
      createTestNodes(app)
    }

    initPixi()

    // Cleanup
    return () => {
      if (appRef.current) {
        appRef.current.destroy(true, { children: true })
        appRef.current = null
      }
    }
  }, [])

  // Handle window resize
  useEffect(() => {
    const handleResize = () => {
      if (appRef.current) {
        appRef.current.renderer.resize(window.innerWidth, window.innerHeight)
      }
    }

    window.addEventListener("resize", handleResize)
    return () => window.removeEventListener("resize", handleResize)
  }, [])

  return <div ref={canvasRef} className="w-full h-full" />
}

/**
 * Load all required assets
 */
async function loadAssets(app: PIXI.Application) {
  const assets = [
    { alias: "characters", src: "/assets/pixel/characters/roguelikeChar_transparent.png" },
    { alias: "tiles", src: "/assets/pixel/tiles/roguelikeSheet_transparent.png" },
  ]

  for (const asset of assets) {
    const texture = await PIXI.Assets.load(asset)
    // CRITICAL: Use NEAREST filtering for pixel art to avoid blurry edges and gaps
    texture.source.scaleMode = "nearest"
  }
}

/**
 * Create background with tiles filling the entire screen
 */
function createDungeonBackground(app: PIXI.Application) {
  const tileTexture = PIXI.Assets.get("tiles")
  const tileSize = 16 // Each tile is 16x16 pixels
  const margin = 1 // 1px margin between tiles in spritesheet
  const scale = 1 // 1:1 display, no scaling

  // Calculate how many tiles needed to fill screen (with extra for safety)
  const tilesX = Math.ceil(app.screen.width / tileSize) + 1
  const tilesY = Math.ceil(app.screen.height / tileSize) + 1

  // Two grass tile variations for natural look
  const grassVariations = [
    { x: 5, y: 0 },  // Grass type 1 (row 1, column 6)
    { x: 5, y: 1 },  // Grass type 2 (row 2, column 6)
  ]

  // Create tiled background with random grass variations
  for (let y = 0; y < tilesY; y++) {
    for (let x = 0; x < tilesX; x++) {
      const tile = new PIXI.Sprite(tileTexture)

      // Randomly select grass variation
      const grassTile = grassVariations[Math.floor(Math.random() * grassVariations.length)]

      // Set texture region to extract single tile from spritesheet
      // Account for 1px margin between tiles
      tile.texture = new PIXI.Texture({
        source: tileTexture.source,
        frame: new PIXI.Rectangle(
          grassTile.x * (tileSize + margin),
          grassTile.y * (tileSize + margin),
          tileSize,
          tileSize
        ),
      })

      tile.x = Math.floor(x * tileSize * scale)
      tile.y = Math.floor(y * tileSize * scale)
      tile.scale.set(scale)
      tile.roundPixels = true // Force pixel alignment

      app.stage.addChild(tile)
    }
  }
}

/**
 * Create decorations (pond, rocks, grass variations)
 */
function createDecorations(app: PIXI.Application) {
  const tileTexture = PIXI.Assets.get("tiles")
  const tileSize = 16
  const margin = 1
  const scale = 1

  // Pond tile coordinates (assuming a 3x3 pattern centered at water)
  // Water center is at (3, 1) as confirmed by user
  const pondTiles = {
    topLeft: { x: 2, y: 0 },
    top: { x: 3, y: 0 },
    topRight: { x: 4, y: 0 },
    left: { x: 2, y: 1 },
    center: { x: 3, y: 1 },
    right: { x: 4, y: 1 },
    bottomLeft: { x: 2, y: 2 },
    bottom: { x: 3, y: 2 },
    bottomRight: { x: 4, y: 2 },
  }

  // Create a pond (8x8 tiles)
  const pondStartX = 10
  const pondStartY = 10
  const pondWidth = 8
  const pondHeight = 8

  for (let y = 0; y < pondHeight; y++) {
    for (let x = 0; x < pondWidth; x++) {
      const tile = new PIXI.Sprite(tileTexture)

      // Determine which tile to use based on position
      let tileCoord
      if (y === 0) {
        // Top row
        if (x === 0) tileCoord = pondTiles.topLeft
        else if (x === pondWidth - 1) tileCoord = pondTiles.topRight
        else tileCoord = pondTiles.top
      } else if (y === pondHeight - 1) {
        // Bottom row
        if (x === 0) tileCoord = pondTiles.bottomLeft
        else if (x === pondWidth - 1) tileCoord = pondTiles.bottomRight
        else tileCoord = pondTiles.bottom
      } else {
        // Middle rows
        if (x === 0) tileCoord = pondTiles.left
        else if (x === pondWidth - 1) tileCoord = pondTiles.right
        else tileCoord = pondTiles.center
      }

      tile.texture = new PIXI.Texture({
        source: tileTexture.source,
        frame: new PIXI.Rectangle(
          tileCoord.x * (tileSize + margin),
          tileCoord.y * (tileSize + margin),
          tileSize,
          tileSize
        ),
      })

      tile.x = Math.floor((pondStartX + x) * tileSize * scale)
      tile.y = Math.floor((pondStartY + y) * tileSize * scale)
      tile.scale.set(scale)
      tile.roundPixels = true

      app.stage.addChild(tile)
    }
  }
}

/**
 * Create test pixel character nodes
 */
function createTestNodes(app: PIXI.Application) {
  const charTexture = PIXI.Assets.get("characters")
  const charSize = 16 // Each character is 16x16 pixels
  const margin = 1 // 1px margin between characters in spritesheet
  const scale = 1 // 1:1 display, no scaling

  // Test character positions in spritesheet
  const testChars = [
    { x: 0, y: 2, name: "Mage", posX: 200, posY: 200 },      // Mage
    { x: 1, y: 2, name: "Knight", posX: 400, posY: 200 },    // Knight
    { x: 2, y: 2, name: "Archer", posX: 600, posY: 200 },    // Archer
  ]

  testChars.forEach((char) => {
    // Create character sprite container
    const charContainer = new PIXI.Container()
    charContainer.x = char.posX
    charContainer.y = char.posY

    // Character sprite
    const sprite = new PIXI.Sprite(charTexture)
    // Account for 1px margin between characters
    sprite.texture = new PIXI.Texture({
      source: charTexture.source,
      frame: new PIXI.Rectangle(
        char.x * (charSize + margin),
        char.y * (charSize + margin),
        charSize,
        charSize
      ),
    })
    sprite.scale.set(scale)
    sprite.anchor.set(0.5)
    sprite.roundPixels = true // Force pixel alignment

    // Add idle animation (bobbing up and down)
    let time = 0
    app.ticker.add(() => {
      time += 0.05
      sprite.y = Math.sin(time) * 5
    })

    // Node name text
    const text = new PIXI.Text({
      text: char.name,
      style: {
        fontFamily: "monospace",
        fontSize: 14,
        fill: 0x00ff00,
        align: "center",
      },
    })
    text.anchor.set(0.5)
    text.y = 50

    // Session count badge
    const sessionBadge = new PIXI.Graphics()
    sessionBadge.circle(0, -40, 10)
    sessionBadge.fill(0xff6b6b)

    const sessionText = new PIXI.Text({
      text: "3",
      style: {
        fontFamily: "monospace",
        fontSize: 12,
        fill: 0xffffff,
      },
    })
    sessionText.anchor.set(0.5)
    sessionText.y = -40

    charContainer.addChild(sprite)
    charContainer.addChild(text)
    charContainer.addChild(sessionBadge)
    charContainer.addChild(sessionText)

    // Make interactive
    charContainer.eventMode = "static"
    charContainer.cursor = "pointer"
    charContainer.on("pointerdown", () => {
      console.log(`Clicked on ${char.name}`)
    })

    app.stage.addChild(charContainer)
  })
}

