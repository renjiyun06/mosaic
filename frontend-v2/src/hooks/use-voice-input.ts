import { useState, useEffect, useRef, useCallback } from "react"

// Extend Window interface for SpeechRecognition
declare global {
  interface Window {
    SpeechRecognition: any
    webkitSpeechRecognition: any
  }
}

interface UseVoiceInputOptions {
  lang?: string
  continuous?: boolean
  interimResults?: boolean
  onError?: (error: string) => void
}

export function useVoiceInput(
  onTranscriptChange: (finalText: string, interimText: string) => void,
  options: UseVoiceInputOptions = {}
) {
  const {
    lang = "zh-CN",
    continuous = true,
    interimResults = true,
    onError,
  } = options

  const [isRecording, setIsRecording] = useState(false)
  const [isSupported, setIsSupported] = useState(false)
  const [interimText, setInterimText] = useState("")
  const [finalText, setFinalText] = useState("")

  const recognitionRef = useRef<any>(null)
  const finalTextRef = useRef("")
  const isStoppingRef = useRef(false)
  const isStartingRef = useRef(false)
  const stopPromiseRef = useRef<Promise<void> | null>(null)

  // Check browser support only, don't create recognition instance here
  useEffect(() => {
    if (typeof window === "undefined") return

    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition

    if (!SpeechRecognition) {
      console.warn("Browser does not support Web Speech API")
      setIsSupported(false)
      return
    }

    setIsSupported(true)

    // Cleanup on unmount
    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop()
        } catch (e) {
          // Ignore errors on cleanup
        }
        recognitionRef.current = null
      }
    }
  }, [])

  // Stop recording
  const stop = useCallback(() => {
    // Return existing promise if already stopping
    if (stopPromiseRef.current) {
      return stopPromiseRef.current
    }

    // Create a promise that resolves when stop is complete
    stopPromiseRef.current = new Promise<void>((resolve) => {
      if (!recognitionRef.current) {
        stopPromiseRef.current = null
        resolve()
        return
      }

      // Create a one-time onend handler
      const handleStopComplete = () => {
        console.log("Stop completed via onend")

        // Clear all event handlers after completion to prevent conflicts
        if (recognitionRef.current) {
          recognitionRef.current.onresult = null
          recognitionRef.current.onerror = null
          recognitionRef.current.onstart = null
          recognitionRef.current.onend = null
        }

        // Reset flags
        isStoppingRef.current = false
        isStartingRef.current = false
        setIsRecording(false)
        setInterimText("")

        // Clear the promise ref
        stopPromiseRef.current = null
        resolve()
      }

      try {
        isStoppingRef.current = true
        recognitionRef.current.onend = handleStopComplete
        recognitionRef.current.stop()

        // Immediately update UI state
        setIsRecording(false)
        setInterimText("")

        // Timeout protection in case onend doesn't fire
        setTimeout(() => {
          if (stopPromiseRef.current) {
            console.log("Stop timeout - forcing completion")
            handleStopComplete()
          }
        }, 500)
      } catch (error: any) {
        console.error("Failed to stop speech recognition:", error)

        // Clear all event handlers
        if (recognitionRef.current) {
          recognitionRef.current.onresult = null
          recognitionRef.current.onerror = null
          recognitionRef.current.onstart = null
          recognitionRef.current.onend = null
        }

        isStoppingRef.current = false
        isStartingRef.current = false
        setIsRecording(false)
        setInterimText("")
        stopPromiseRef.current = null
        resolve()
      }
    })

    return stopPromiseRef.current
  }, [])

  // Start recording
  const start = useCallback(async () => {
    if (!isSupported) {
      onError?.("Browser does not support speech recognition")
      return
    }

    // Prevent starting if already starting
    if (isStartingRef.current) {
      console.log("Already starting, please wait")
      return
    }

    try {
      // Wait for any ongoing stop operation to complete
      if (stopPromiseRef.current) {
        console.log("Waiting for existing stop to complete...")
        await stopPromiseRef.current
        // Wait a bit more after stop completes
        await new Promise(resolve => setTimeout(resolve, 50))
      } else if (recognitionRef.current) {
        // If there's a recognition instance but no stop in progress, clean it up
        console.log("Cleaning up existing recognition...")
        try {
          // Clear all event handlers first to avoid conflicts
          recognitionRef.current.onresult = null
          recognitionRef.current.onerror = null
          recognitionRef.current.onstart = null
          recognitionRef.current.onend = null
          recognitionRef.current.stop()
        } catch (e) {
          // Ignore errors from stopping
        }
        recognitionRef.current = null
        // Wait for cleanup to complete
        await new Promise(resolve => setTimeout(resolve, 100))
      }

      // Create a fresh recognition instance to avoid state issues
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
      const recognition = new SpeechRecognition()
      recognition.continuous = continuous
      recognition.interimResults = interimResults
      recognition.lang = lang
      recognition.maxAlternatives = 1

      // Set up event handlers for the new instance
      recognition.onresult = (event: any) => {
        let interim = ""
        let final = ""

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript
          if (event.results[i].isFinal) {
            final += transcript
          } else {
            interim += transcript
          }
        }

        setInterimText(interim)

        if (final) {
          finalTextRef.current += final
          setFinalText(finalTextRef.current)
          onTranscriptChange(finalTextRef.current, interim)
        } else {
          onTranscriptChange(finalTextRef.current, interim)
        }
      }

      recognition.onerror = (event: any) => {
        console.error("Speech recognition error:", event.error)

        if (event.error === "aborted" && isStoppingRef.current) {
          return
        }

        const errorMessage = getErrorMessage(event.error)
        onError?.(errorMessage)

        isStartingRef.current = false
        isStoppingRef.current = false
        setIsRecording(false)
        setInterimText("")
      }

      recognition.onstart = () => {
        console.log("Speech recognition started")
        isStartingRef.current = false
      }

      recognitionRef.current = recognition

      // Reset state
      finalTextRef.current = ""
      setFinalText("")
      setInterimText("")
      isStartingRef.current = true

      // Try to start the new recognition instance
      try {
        recognitionRef.current.start()
        setIsRecording(true)
        console.log("Speech recognition started successfully")
      } catch (error: any) {
        console.error("Failed to start speech recognition:", error)
        isStartingRef.current = false
        onError?.(error.message || "Failed to start speech recognition")
        setIsRecording(false)
      }
    } catch (error: any) {
      console.error("Failed to prepare speech recognition:", error)
      isStartingRef.current = false
      onError?.(error.message || "Failed to prepare speech recognition")
      setIsRecording(false)
    }
  }, [isSupported, onError, continuous, interimResults, lang, onTranscriptChange])

  return {
    isRecording,
    isSupported,
    interimText,
    finalText,
    start,
    stop,
  }
}

// Helper function to get user-friendly error messages
function getErrorMessage(error: string): string {
  const errorMessages: Record<string, string> = {
    "no-speech": "No speech detected, please try again",
    "audio-capture": "Cannot access microphone, please check permissions",
    "not-allowed": "Microphone permission denied",
    "network": "Network error, please check connection",
    "aborted": "Speech recognition aborted",
    "bad-grammar": "Grammar error",
    "language-not-supported": "Language not supported",
  }

  return errorMessages[error] || `Speech recognition error: ${error}`
}
