import { useState, useCallback } from 'react'
import { flightImageUrl } from '../api/transport'
import ImageLightbox from './ImageLightbox'

interface Props {
  flightId: number
  type: 'aircraft' | 'route'
  hasImage: boolean
  ga?: boolean
  alt?: string
}

export default function FlightImage({ flightId, type, hasImage, ga = false, alt = '' }: Props) {
  const [failed, setFailed] = useState(false)
  const [lightbox, setLightbox] = useState(false)
  const handleError = useCallback(() => setFailed(true), [])

  if (!hasImage || failed) {
    return <div className="h-10 w-16 rounded bg-bg-hover flex items-center justify-center text-xs text-text-secondary">&mdash;</div>
  }

  return (
    <>
      {lightbox && (
        <ImageLightbox
          src={flightImageUrl(flightId, type, 'full', ga)}
          alt={alt}
          onClose={() => setLightbox(false)}
        />
      )}
      <img
        src={flightImageUrl(flightId, type, 'thumb', ga)}
        alt={alt}
        className="h-10 rounded cursor-pointer hover:opacity-80 transition-opacity"
        onError={handleError}
        onClick={(e) => {
          e.stopPropagation()
          setLightbox(true)
        }}
      />
    </>
  )
}
