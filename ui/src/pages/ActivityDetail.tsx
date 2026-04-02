import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchActivity, updateActivity, deleteActivity } from '../api/activities'
import ActivityForm from '../components/ActivityForm'

function formatDate(d: string) {
  return new Date(d + 'T00:00:00').toLocaleDateString('en-GB', {
    day: 'numeric', month: 'short', year: 'numeric',
  })
}

function formatDuration(seconds: number | null) {
  if (!seconds) return '-'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}

export default function ActivityDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const { data: activity, isLoading } = useQuery({
    queryKey: ['activity', id],
    queryFn: () => fetchActivity(Number(id)),
    enabled: !!id,
  })

  const update = useMutation({
    mutationFn: (form: {
      title: string; activity_type: string; date: string; start_time: string;
      distance_km: string; duration_seconds: string; elevation_gain: string;
      elevation_loss: string; max_altitude: string; notes: string;
    }) => {
      const payload: Record<string, unknown> = {}
      if (form.title) payload.title = form.title
      if (form.activity_type) payload.activity_type = form.activity_type
      if (form.date) payload.date = form.date
      if (form.start_time) payload.start_time = form.start_time
      if (form.distance_km) payload.distance_km = parseFloat(form.distance_km)
      if (form.duration_seconds) payload.duration_seconds = parseInt(form.duration_seconds)
      if (form.elevation_gain) payload.elevation_gain = parseFloat(form.elevation_gain)
      if (form.elevation_loss) payload.elevation_loss = parseFloat(form.elevation_loss)
      if (form.notes !== undefined) payload.notes = form.notes || null
      return updateActivity(Number(id), payload)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['activity', id] })
      setEditing(false)
    },
  })

  const remove = useMutation({
    mutationFn: () => deleteActivity(Number(id)),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['activities'] })
      navigate('/activities')
    },
  })

  if (isLoading) return <div className="p-6 text-text-secondary">Loading...</div>
  if (!activity) return <div className="p-6 text-text-secondary">Activity not found</div>

  if (editing) {
    return (
      <div className="p-6 max-w-2xl">
        <h2 className="text-xl font-bold text-text-primary mb-4">Edit Activity</h2>
        <ActivityForm
          initial={{
            title: activity.title || '',
            activity_type: activity.activity_type,
            date: activity.date || '',
            start_time: activity.start_time || '',
            distance_km: activity.distance_km != null ? String(activity.distance_km) : '',
            duration_seconds: activity.duration_seconds != null ? String(activity.duration_seconds) : '',
            elevation_gain: activity.elevation_gain != null ? String(activity.elevation_gain) : '',
            elevation_loss: activity.elevation_loss != null ? String(activity.elevation_loss) : '',
            notes: activity.notes || '',
          }}
          onSubmit={form => update.mutate(form)}
          onCancel={() => setEditing(false)}
        />
        {update.isError && (
          <div className="text-xs text-red-600 mt-2">
            Update failed: {(update.error as Error).message}
          </div>
        )}
      </div>
    )
  }

  const typeName = activity.activity_type
    ? activity.activity_type.charAt(0).toUpperCase() + activity.activity_type.slice(1)
    : ''

  return (
    <div className="p-6 max-w-2xl">
      <button
        onClick={() => navigate('/activities')}
        className="text-xs text-text-secondary hover:text-text-primary mb-4 inline-block"
      >
        &larr; Back to activities
      </button>

      <div className="flex items-start justify-between mb-4">
        <div>
          <h2 className="text-xl font-bold text-text-primary">{activity.title || 'Untitled'}</h2>
          <div className="flex items-center gap-2 mt-1">
            <span className={`text-xs px-1.5 py-0.5 rounded ${
              activity.source === 'strava' ? 'bg-orange-500/20 text-orange-400' : 'bg-blue-500/20 text-blue-400'
            }`}>
              {activity.source}
            </span>
            <span className="text-xs text-text-secondary bg-bg-secondary px-1.5 py-0.5 rounded">
              {typeName}
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setEditing(true)}
            className="px-3 py-1.5 text-sm rounded bg-bg-secondary text-text-secondary hover:bg-bg-hover border border-border"
          >
            Edit
          </button>
          {confirmDelete ? (
            <span className="flex gap-1">
              <button onClick={() => remove.mutate()} className="px-3 py-1.5 text-sm rounded bg-red-600 text-white hover:bg-red-700">
                Confirm
              </button>
              <button onClick={() => setConfirmDelete(false)} className="px-3 py-1.5 text-sm rounded bg-bg-secondary text-text-secondary hover:bg-bg-hover border border-border">
                Cancel
              </button>
            </span>
          ) : (
            <button
              onClick={() => setConfirmDelete(true)}
              className="px-3 py-1.5 text-sm rounded text-red-500 hover:text-red-700 border border-border hover:border-red-300"
            >
              Delete
            </button>
          )}
        </div>
      </div>

      <div className="bg-bg-card border border-border rounded-lg p-4 space-y-3">
        <Row label="Date" value={activity.date ? formatDate(activity.date) : '-'} />
        {activity.start_time && <Row label="Start time" value={activity.start_time.slice(0, 5)} />}
        <Row label="Duration" value={formatDuration(activity.moving_time_seconds ?? activity.duration_seconds)} />
        <Row label="Distance" value={activity.distance_km != null ? `${activity.distance_km < 10 ? activity.distance_km.toFixed(1) : Math.round(activity.distance_km)} km` : '-'} />
        {activity.elevation_gain != null && <Row label="Elevation gain" value={`${Math.round(activity.elevation_gain)} m`} />}
        {activity.elevation_loss != null && <Row label="Elevation loss" value={`${Math.round(activity.elevation_loss)} m`} />}
        {activity.max_altitude != null && <Row label="Max altitude" value={`${Math.round(activity.max_altitude)} m`} />}
        {activity.avg_speed_kmh != null && <Row label="Avg speed" value={`${activity.avg_speed_kmh.toFixed(1)} km/h`} />}
        {activity.max_speed_kmh != null && <Row label="Max speed" value={`${activity.max_speed_kmh.toFixed(1)} km/h`} />}
        {activity.avg_heartrate != null && <Row label="Avg HR" value={`${Math.round(activity.avg_heartrate)} bpm`} />}
        {activity.max_heartrate != null && <Row label="Max HR" value={`${Math.round(activity.max_heartrate)} bpm`} />}
        {activity.calories != null && <Row label="Calories" value={`${Math.round(activity.calories)} kcal`} />}
        {activity.strava_activity_id && <Row label="Strava ID" value={String(activity.strava_activity_id)} />}
        {activity.notes && (
          <div>
            <div className="text-xs text-text-secondary mb-1">Notes</div>
            <div className="text-sm text-text-primary whitespace-pre-wrap">{activity.notes}</div>
          </div>
        )}
      </div>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between">
      <span className="text-xs text-text-secondary">{label}</span>
      <span className="text-sm text-text-primary">{value}</span>
    </div>
  )
}
