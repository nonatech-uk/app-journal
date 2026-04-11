import { useEffect } from 'react'

interface Props {
  src: string
  alt: string
  onClose: () => void
  downloadUrl?: string
  downloadFilename?: string
}

export default function ImageLightbox({ src, alt, onClose, downloadUrl, downloadFilename }: Props) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/80"
      onClick={onClose}
    >
      <div className="relative max-w-[90vw] max-h-[90vh]" onClick={(e) => e.stopPropagation()}>
        <div className="absolute -top-3 -right-3 flex items-center gap-1.5">
          {downloadUrl && (
            <a
              href={downloadUrl}
              download={downloadFilename || ''}
              className="w-8 h-8 rounded-full bg-bg-secondary text-text-primary flex items-center justify-center hover:bg-bg-hover shadow transition-colors text-sm"
              title="Download original"
              onClick={(e) => e.stopPropagation()}
            >
              &#8615;
            </a>
          )}
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-bg-secondary text-text-primary flex items-center justify-center hover:bg-bg-hover shadow transition-colors text-lg"
          >
            &times;
          </button>
        </div>
        <img src={src} alt={alt} className="max-w-[90vw] max-h-[90vh] rounded" />
      </div>
    </div>
  )
}
