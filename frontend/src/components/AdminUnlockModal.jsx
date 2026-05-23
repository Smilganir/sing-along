import { useState } from 'react';

import { useAuth } from '../context/AuthContext.jsx';

import './AdminUnlockModal.css';

export default function AdminUnlockModal() {
  const { showUnlock, setShowUnlock, login } = useAuth();
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (!showUnlock) return null;

  async function handleSubmit(event) {
    event.preventDefault();
    if (!password.trim()) return;
    setSubmitting(true);
    setError('');
    try {
      await login(password);
      setPassword('');
    } catch (err) {
      setError(err.message || 'Login failed');
    } finally {
      setSubmitting(false);
    }
  }

  function handleClose() {
    if (submitting) return;
    setShowUnlock(false);
    setPassword('');
    setError('');
  }

  return (
    <div className="admin-unlock-overlay" role="presentation" onClick={handleClose}>
      <div
        className="admin-unlock-modal"
        role="dialog"
        aria-labelledby="admin-unlock-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="admin-unlock-title">Unlock admin</h2>
        <p className="admin-unlock-desc">
          Enter the admin password to manage songs, sync the room, and edit sheets.
        </p>
        <form onSubmit={handleSubmit}>
          <label className="admin-unlock-label" htmlFor="admin-unlock-password">
            Password
          </label>
          <input
            id="admin-unlock-password"
            type="password"
            className="admin-unlock-input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            autoFocus
          />
          {error && <p className="admin-unlock-error">{error}</p>}
          <div className="admin-unlock-actions">
            <button type="button" className="admin-unlock-btn-secondary" onClick={handleClose}>
              Cancel
            </button>
            <button type="submit" className="admin-unlock-btn-primary" disabled={submitting}>
              {submitting ? 'Unlocking…' : 'Unlock'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
