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

  // Check browser support and initialize SpeechRecognition
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

    const recognition = new SpeechRecognition()
    recognition.continuous = continuous
    recognition.interimResults = interimResults
    recognition.lang = lang
    recognition.maxAlternatives = 1

    // Handle speech recognition results
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

      // Update interim text
      setInterimText(interim)

      // Accumulate final text
      if (final) {
        finalTextRef.current += final
        setFinalText(finalTextRef.current)
        onTranscriptChange(finalTextRef.current, interim)
      } else {
        onTranscriptChange(finalTextRef.current, interim)
      }
    }

    // Handle errors
    recognition.onerror = (event: any) => {
      console.error("Speech recognition error:", event.error)

      // Don't treat "aborted" as error if we're intentionally stopping
      if (event.error === "aborted" && isStoppingRef.current) {
        return
      }

      const errorMessage = getErrorMessage(event.error)
      onError?.(errorMessage)

      // Stop recording on error
      isStartingRef.current = false
      isStoppingRef.current = false
      setIsRecording(false)
      setInterimText("")
    }

    // Handle recognition end
    recognition.onend = () => {
      console.log("Speech recognition ended")
      isStartingRef.current = false
      isStoppingRef.current = false
      setIsRecording(false)
      setInterimText("")
    }

    recognitionRef.current = recognition

    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop()
        } catch (e) {
          // Ignore errors on cleanup
        }
      }
    }
  }, [lang, continuous, interimResults, onTranscriptChange, onError])

  // Start recording
  const start = useCallback(() => {
    if (!isSupported || !recognitionRef.current) {
      onError?.("Browser does not support speech recognition")
      return
    }

    // Prevent starting if already starting or stopping
    if (isStartingRef.current || isStoppingRef.current) {
      console.log("Recognition is busy, please wait")
      return
    }

    try {
      // Force stop any existing recognition session first
      try {
        recognitionRef.current.stop()
      } catch (e) {
        // Ignore errors from stopping (might not be running)
      }

      // Reset state
      finalTextRef.current = ""
      setFinalText("")
      setInterimText("")
      isStartingRef.current = true
      isStoppingRef.current = false

      // Small delay to ensure previous session is fully stopped
      setTimeout(() => {
        try {
          recognitionRef.current.start()
          setIsRecording(true)
        } catch (error: any) {
          console.error("Failed to start speech recognition:", error)
          isStartingRef.current = false
          onError?.(error.message || "Failed to start speech recognition")
          setIsRecording(false)
        }
      }, 100)
    } catch (error: any) {
      console.error("Failed to prepare speech recognition:", error)
      isStartingRef.current = false
      onError?.(error.message || "Failed to prepare speech recognition")
      setIsRecording(false)
    }
  }, [isSupported, onError])

  // Stop recording
  const stop = useCallback(() => {
    if (!recognitionRef.current) return

    // Prevent stopping if already stopping
    if (isStoppingRef.current) {
      console.log("Already stopping")
      return
    }

    try {
      isStoppingRef.current = true
      recognitionRef.current.stop()

      // Immediately update UI state to prevent button from getting stuck
      setIsRecording(false)
      setInterimText("")

      // Set a timeout to reset flags if onend doesn't fire
      setTimeout(() => {
        isStoppingRef.current = false
        isStartingRef.current = false
      }, 1000)
    } catch (error: any) {
      console.error("Failed to stop speech recognition:", error)
      isStoppingRef.current = false
      setIsRecording(false)
      setInterimText("")
    }
  }, [])

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
