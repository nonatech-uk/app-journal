import { useState, useRef, useCallback, useEffect } from 'react'

interface Props {
  onRecorded: (blob: Blob) => void
  onClear: () => void
  hasRecording: boolean
}

export default function VoiceRecorder({ onRecorded, onClear, hasRecording }: Props) {
  const [state, setState] = useState<'idle' | 'recording' | 'recorded'>('idle')
  const [duration, setDuration] = useState(0)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<number | null>(null)

  useEffect(() => {
    if (!hasRecording && state === 'recorded') {
      setState('idle')
      setAudioUrl(null)
      setDuration(0)
    }
  }, [hasRecording, state])

  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
          ? 'audio/webm;codecs=opus'
          : 'audio/webm',
      })
      chunksRef.current = []
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop())
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        const url = URL.createObjectURL(blob)
        setAudioUrl(url)
        onRecorded(blob)
        setState('recorded')
      }
      mediaRecorderRef.current = recorder
      recorder.start()
      setState('recording')
      setDuration(0)
      timerRef.current = window.setInterval(() => setDuration((d) => d + 1), 1000)
    } catch {
      // microphone permission denied or unavailable
    }
  }, [onRecorded])

  const stopRecording = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    mediaRecorderRef.current?.stop()
  }, [])

  const reRecord = useCallback(() => {
    if (audioUrl) URL.revokeObjectURL(audioUrl)
    setAudioUrl(null)
    setDuration(0)
    onClear()
    setState('idle')
  }, [audioUrl, onClear])

  const formatDuration = (s: number) =>
    `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

  return (
    <div className="flex items-center gap-3">
      {state === 'idle' && (
        <button
          type="button"
          onClick={startRecording}
          className="flex items-center gap-2 px-3 py-1.5 text-sm rounded border border-border text-text-secondary hover:text-accent hover:border-accent/30 transition-colors"
        >
          <span className="w-2 h-2 rounded-full bg-red-500" />
          Record voice note
        </button>
      )}

      {state === 'recording' && (
        <>
          <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
          <span className="text-sm text-red-500 font-mono">{formatDuration(duration)}</span>
          <button
            type="button"
            onClick={stopRecording}
            className="px-3 py-1.5 text-sm rounded bg-red-500 text-white hover:bg-red-600 transition-colors"
          >
            Stop
          </button>
        </>
      )}

      {state === 'recorded' && audioUrl && (
        <div className="flex items-center gap-2">
          <audio src={audioUrl} controls className="h-8" />
          <span className="text-xs text-text-secondary">{formatDuration(duration)}</span>
          <button
            type="button"
            onClick={reRecord}
            className="text-xs px-2 py-1 rounded border border-border text-text-secondary hover:text-accent hover:border-accent/30 transition-colors"
          >
            Re-record
          </button>
        </div>
      )}
    </div>
  )
}
