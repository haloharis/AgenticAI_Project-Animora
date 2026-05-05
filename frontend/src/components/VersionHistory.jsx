import React, { useEffect, useState } from 'react'
import { getHistory, revertVersion } from '../services/api'

export default function VersionHistory({ jobId, currentVersion, onReverted }) {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(false)
  const [revertingVersion, setRevertingVersion] = useState(null)

  const fetchHistory = async () => {
    if (!jobId) return
    setLoading(true)
    try {
      const h = await getHistory(jobId)
      setHistory(h)
    } catch (e) {
      console.error('Failed to fetch history', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchHistory()
  }, [jobId, currentVersion])

  const handleRevert = async (version) => {
    setRevertingVersion(version)
    try {
      const result = await revertVersion(jobId, version)
      if (onReverted) onReverted(result)
      await fetchHistory()
    } catch (e) {
      alert(`Revert failed: ${e.message}`)
    } finally {
      setRevertingVersion(null)
    }
  }

  if (!jobId || history.length === 0) return null

  return (
    <div className="version-history">
      <h4>🕐 Version History</h4>
      {loading && <p className="loading-text">Loading...</p>}
      <div className="version-list">
        {history.map((v) => (
          <div
            key={v.version}
            className={`version-row ${v.version === currentVersion ? 'current' : ''}`}
          >
            <span className="version-badge">v{v.version}</span>
            <span className="version-phase">{v.phase || 'init'}</span>
            <span className="version-note">{v.note}</span>
            <span className="version-time">
              {new Date(v.created_at).toLocaleTimeString()}
            </span>
            {v.version !== currentVersion && (
              <button
                className="btn-revert"
                onClick={() => handleRevert(v.version)}
                disabled={revertingVersion === v.version}
              >
                {revertingVersion === v.version ? '⏳' : 'Revert'}
              </button>
            )}
            {v.version === currentVersion && (
              <span className="current-badge">current</span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
