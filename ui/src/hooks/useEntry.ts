import { useQuery } from '@tanstack/react-query'
import { fetchEntry, fetchEnrichment } from '../api/entries'

export function useEntry(id: number | undefined) {
  return useQuery({
    queryKey: ['entry', id],
    queryFn: () => fetchEntry(id!),
    enabled: !!id,
  })
}

export function useEnrichment(id: number | undefined) {
  return useQuery({
    queryKey: ['enrichment', id],
    queryFn: () => fetchEnrichment(id!),
    enabled: !!id,
  })
}
