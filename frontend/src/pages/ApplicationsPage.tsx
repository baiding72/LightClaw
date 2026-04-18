import { useEffect, useState } from 'react'
import { api } from '../lib/api'

interface ApplicationItem {
  application_id: string
  company_name: string
  role_title: string
  status: string
  source_url?: string | null
  location?: string | null
  notes?: string | null
  next_action?: string | null
  created_at: string
  updated_at: string
}

export default function ApplicationsPage() {
  const [applications, setApplications] = useState<ApplicationItem[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [form, setForm] = useState({
    company_name: '',
    role_title: '',
    source_url: '',
    location: '',
    notes: '',
    next_action: 'Review company careers page and prepare profile mapping.',
  })

  useEffect(() => {
    void loadApplications()
  }, [])

  const loadApplications = async () => {
    setLoading(true)
    try {
      const response = await api.get<{ applications: ApplicationItem[] }>('/applications', {
        params: { limit: 20 },
      })
      setApplications(response.data.applications)
    } catch (error) {
      console.error('Failed to load applications:', error)
    } finally {
      setLoading(false)
    }
  }

  const createApplication = async () => {
    if (!form.company_name || !form.role_title) {
      alert('Please enter a company and role.')
      return
    }

    setSubmitting(true)
    try {
      await api.post('/applications', {
        ...form,
        source_url: form.source_url || undefined,
        location: form.location || undefined,
        notes: form.notes || undefined,
        next_action: form.next_action || undefined,
      })
      setForm({
        company_name: '',
        role_title: '',
        source_url: '',
        location: '',
        notes: '',
        next_action: 'Review company careers page and prepare profile mapping.',
      })
      await loadApplications()
    } catch (error) {
      console.error('Failed to create application:', error)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h2 className="text-2xl font-semibold text-gray-900">Applications</h2>
        <p className="text-sm text-gray-600">
          Track internship targets, source links, and next actions for the job application loop.
        </p>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-medium text-gray-900">Add Target</h3>
          <div className="mt-4 space-y-4">
            {[
              ['company_name', 'Company'],
              ['role_title', 'Role'],
              ['source_url', 'Source URL'],
              ['location', 'Location'],
            ].map(([key, label]) => (
              <div key={key}>
                <label className="block text-sm font-medium text-gray-700 mb-2">{label}</label>
                <input
                  value={form[key as keyof typeof form]}
                  onChange={(e) => setForm((prev) => ({ ...prev, [key]: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            ))}

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Next Action</label>
              <input
                value={form.next_action}
                onChange={(e) => setForm((prev) => ({ ...prev, next_action: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Notes</label>
              <textarea
                value={form.notes}
                onChange={(e) => setForm((prev) => ({ ...prev, notes: e.target.value }))}
                rows={4}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <button
              onClick={() => void createApplication()}
              disabled={submitting}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {submitting ? 'Saving...' : 'Create Application'}
            </button>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-lg font-medium text-gray-900">Tracker</h3>
            <button
              onClick={() => void loadApplications()}
              className="px-3 py-2 text-sm border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
            >
              Refresh
            </button>
          </div>

          <div className="mt-4 space-y-3">
            {loading ? (
              <div className="text-sm text-gray-500">Loading applications...</div>
            ) : applications.length === 0 ? (
              <div className="text-sm text-gray-500">No applications tracked yet.</div>
            ) : (
              applications.map((item) => (
                <div key={item.application_id} className="rounded border p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="font-medium text-gray-900">{item.company_name}</div>
                      <div className="text-sm text-gray-600">{item.role_title}</div>
                    </div>
                    <span className="rounded border bg-gray-50 px-2 py-1 text-xs text-gray-700">
                      {item.status}
                    </span>
                  </div>

                  {item.source_url ? (
                    <a
                      href={item.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-2 block break-all text-sm text-sky-700 hover:text-sky-900"
                    >
                      {item.source_url}
                    </a>
                  ) : null}

                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <div>
                      <div className="text-xs uppercase tracking-wide text-gray-500">Next Action</div>
                      <div className="mt-1 text-sm text-gray-700">{item.next_action || 'Not set'}</div>
                    </div>
                    <div>
                      <div className="text-xs uppercase tracking-wide text-gray-500">Location</div>
                      <div className="mt-1 text-sm text-gray-700">{item.location || 'Unspecified'}</div>
                    </div>
                  </div>

                  {item.notes ? (
                    <div className="mt-3 rounded border bg-gray-50 px-3 py-2 text-sm text-gray-700 whitespace-pre-wrap">
                      {item.notes}
                    </div>
                  ) : null}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
