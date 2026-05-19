const BASE = '/api'

export async function startPipeline(prompt, style) {
  const res = await fetch(`${BASE}/pipeline/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, style }),
  })
  if (!res.ok) throw new Error(`Start failed: ${res.status}`)
  return res.json()
}

export async function getJobStatus(jobId) {
  const res = await fetch(`${BASE}/pipeline/${jobId}/status`)
  if (!res.ok) throw new Error(`Status failed: ${res.status}`)
  return res.json()
}

export async function submitEdit(jobId, query) {
  const res = await fetch(`${BASE}/edit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ job_id: jobId, query }),
  })
  if (!res.ok) throw new Error(`Edit failed: ${res.status}`)
  return res.json()
}

export async function getHistory(jobId) {
  const res = await fetch(`${BASE}/edit/${jobId}/history`)
  if (!res.ok) throw new Error(`History failed: ${res.status}`)
  return res.json()
}

export async function revertVersion(jobId, version) {
  const res = await fetch(`${BASE}/edit/${jobId}/revert/${version}`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error(`Revert failed: ${res.status}`)
  return res.json()
}

export async function rerunPhase(jobId, phase) {
  const res = await fetch(`${BASE}/pipeline/${jobId}/rerun/${phase}`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error(`Rerun failed: ${res.status}`)
  return res.json()
}

export function getVideoUrl(jobId, version = null) {
  const url = `${BASE}/pipeline/${jobId}/video`
  return version !== null ? `${url}?version=${version}` : url
}
