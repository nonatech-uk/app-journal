import { apiFetch } from '@mees/shared-ui'
import type { MemoirsResponse, MemoirDetail } from './types.ts'

export function fetchMemoirs() {
  return apiFetch<MemoirsResponse>('/memoirs')
}

export function fetchMemoir(id: number) {
  return apiFetch<MemoirDetail>(`/memoirs/${id}`)
}

export function createMemoir(data: {
  title: string
  parent_id?: number | null
  start_year?: number | null
  start_month?: number | null
  end_year?: number | null
  end_month?: number | null
  date_label?: string | null
  description?: string | null
  markdown_text?: string | null
  cover_asset_id?: string | null
  sort_order?: number
}) {
  return apiFetch<MemoirDetail>('/memoirs', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function updateMemoir(id: number, data: Record<string, unknown>) {
  return apiFetch<MemoirDetail>(`/memoirs/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export function deleteMemoir(id: number) {
  return apiFetch<{ ok: boolean }>(`/memoirs/${id}`, { method: 'DELETE' })
}

export function autoLinkEntries(id: number) {
  return apiFetch<{ linked: number }>(`/memoirs/${id}/entries/auto`, { method: 'POST' })
}
