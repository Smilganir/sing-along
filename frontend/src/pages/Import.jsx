import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  addSong,
  enrichSong,
  enrichSongFromUrl,
  enrichTop,
  getLibraryStatus,
  getSong,
  getSongs,
  removeSong,
  saveSongSheet,
} from '../api/client.js';
import { useAuth } from '../context/AuthContext.jsx';
import { useLocalStorage } from '../hooks/useLocalStorage.js';import { parseLibrarySongId } from '../utils/routes.js';
import './Import.css';

const PAGE_SIZE = 50;

const SORT_OPTIONS = [
  { id: 'play_count', label: 'Most played' },
  { id: 'last_played_at', label: 'Recently played' },
  { id: 'favorites', label: 'Favorites' },
];

const EMPTY_FORM = {
  title: '',
  artist: '',
  language: 'auto',
  youtube_url: '',
  source_url: '',
  play_count: '0',
};

function statusLabel(status) {
  if (status === 'ready') return 'Ready';
  if (status === 'needs_chords') return 'Needs chords';
  if (status === 'failed') return 'Failed';
  return 'Not fetched';
}

export default function Import() {
  const { isAdmin } = useAuth();
  const [status, setStatus] = useState(null);  const [songs, setSongs] = useState([]);
  const [totalSongs, setTotalSongs] = useState(0);
  const [page, setPage] = useState(1);
  const [sortBy, setSortBy] = useState('play_count');
  const [favorites, setFavorites] = useLocalStorage('singalong-favorites', []);
  const [activeTab, setActiveTab] = useState('all');
  const [statusFilter, setStatusFilter] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [enriching, setEnriching] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [error, setError] = useState('');
  const [selectedSong, setSelectedSong] = useState(null);
  const [fullDraft, setFullDraft] = useState('');
  const [easyDraft, setEasyDraft] = useState('');
  const [easyMode, setEasyMode] = useState(false);
  const [removeTarget, setRemoveTarget] = useState(null);
  const [removing, setRemoving] = useState(false);
  const [sourceLinkDraft, setSourceLinkDraft] = useState('');

  const langFilter = activeTab === 'he' || activeTab === 'en' ? activeTab : undefined;
  const apiSort = sortBy === 'favorites' ? 'play_count' : sortBy;
  const totalPages = Math.max(1, Math.ceil(totalSongs / PAGE_SIZE));

  const loadData = useCallback(async () => {
    setLoading(true);
    setError('');
    let songError = '';

    try {
      const result = await getSongs({
        lang: langFilter,
        q: searchQuery.trim() || undefined,
        sort: apiSort,
        status: statusFilter || undefined,
        ids: sortBy === 'favorites' ? favorites : undefined,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      });
      setSongs(result.items);
      setTotalSongs(result.total);
    } catch (err) {
      songError = err.message;
      setSongs([]);
      setTotalSongs(0);
    }

    try {
      const libraryStatus = await getLibraryStatus();
      setStatus(libraryStatus);
    } catch (err) {
      setError(songError || err.message);
    } finally {
      if (!songError) setError('');
      setLoading(false);
    }
  }, [langFilter, searchQuery, sortBy, apiSort, favorites, page, statusFilter]);

  useEffect(() => {
    setPage(1);
  }, [langFilter, searchQuery, sortBy, statusFilter]);

  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    function openFromHash() {
      const songId = parseLibrarySongId();
      if (songId) openSong(songId);
    }

    openFromHash();
    window.addEventListener('hashchange', openFromHash);
    return () => window.removeEventListener('hashchange', openFromHash);
  }, []);

  useEffect(() => {
    if (!enriching) return undefined;
    const timer = setInterval(loadData, 5000);
    return () => clearInterval(timer);
  }, [enriching, loadData]);

  const hebrewCount = useMemo(
    () => songs.filter((song) => song.language === 'he').length,
    [songs]
  );

  const rangeStart = totalSongs === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const rangeEnd = Math.min(page * PAGE_SIZE, totalSongs);

  function toggleFavorite(songId, event) {
    event?.stopPropagation();
    setFavorites((prev) =>
      prev.includes(songId) ? prev.filter((id) => id !== songId) : [...prev, songId]
    );
  }

  async function handleAddSong(event) {
    event.preventDefault();
    if (!form.title.trim()) return;

    setSaving(true);
    setError('');
    const sourceUrl = form.source_url.trim() || null;
    try {
      const created = await addSong({
        title: form.title.trim(),
        artist: form.artist.trim(),
        language: form.language === 'auto' ? null : form.language,
        youtube_url: form.youtube_url.trim() || null,
        source_url: sourceUrl,
        play_count: Number(form.play_count) || 0,
      });

      if (sourceUrl) {
        try {
          await enrichSongFromUrl(created.id, sourceUrl);
        } catch (err) {
          setError(`Song saved, but chords fetch failed: ${err.message}`);
          await loadData();
          return;
        }
      }

      setForm(EMPTY_FORM);
      setShowAddForm(false);
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleEnrichTop() {
    setEnriching(true);
    setError('');
    try {
      await enrichTop(100, true);
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setTimeout(() => setEnriching(false), 60000);
    }
  }

  async function openSong(songId) {
    setError('');
    setEasyMode(false);
    try {
      const detail = await getSong(songId);
      setSelectedSong(detail);
      setFullDraft(detail.chordpro_full || '');
      setEasyDraft(detail.chordpro_easy || '');
      setSourceLinkDraft(detail.source_url || '');
    } catch (err) {
      setError(err.message);
    }
  }

  async function handleRefetchSong() {
    if (!selectedSong) return;
    setSaving(true);
    setEasyMode(false);
    try {
      const detail = await enrichSong(selectedSong.id);
      setSelectedSong(detail);
      setFullDraft(detail.chordpro_full || '');
      setEasyDraft(detail.chordpro_easy || '');
      setSourceLinkDraft(detail.source_url || '');
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleApplySourceLink(event) {
    event.preventDefault();
    if (!selectedSong || !sourceLinkDraft.trim()) return;
    setSaving(true);
    setEasyMode(false);
    try {
      const detail = await enrichSongFromUrl(selectedSong.id, sourceLinkDraft.trim());
      setSelectedSong(detail);
      setFullDraft(detail.chordpro_full || '');
      setEasyDraft(detail.chordpro_easy || '');
      setSourceLinkDraft(detail.source_url || sourceLinkDraft.trim());
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveSheet() {
    if (!selectedSong) return;
    setSaving(true);
    try {
      const detail = await saveSongSheet(selectedSong.id, {
        chordpro_full: fullDraft,
        chordpro_easy: easyDraft || null,
      });
      setSelectedSong(detail);
      setFullDraft(detail.chordpro_full || '');
      setEasyDraft(detail.chordpro_easy || '');
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  const hasEasy = Boolean(selectedSong?.chordpro_easy || easyDraft);
  const activeNote = easyMode
    ? (selectedSong?.language === 'he'
        ? selectedSong?.easy_note_he
        : selectedSong?.easy_note_en) || selectedSong?.easy_note_en
    : null;
  const sheetValue = easyMode && hasEasy ? easyDraft : fullDraft;

  function handleSheetChange(value) {
    if (easyMode && hasEasy) {
      setEasyDraft(value);
    } else {
      setFullDraft(value);
    }
  }

  async function handleConfirmRemove() {
    if (!removeTarget) return;
    setRemoving(true);
    setError('');
    try {
      await removeSong(removeTarget.id);
      if (selectedSong?.id === removeTarget.id) {
        setSelectedSong(null);
        setFullDraft('');
        setEasyDraft('');
        setEasyMode(false);
      }
      setRemoveTarget(null);
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setRemoving(false);
    }
  }

  function toggleStatusFilter(nextStatus) {
    setStatusFilter((current) => (current === nextStatus ? null : nextStatus));
  }

  return (
    <div className="import-page">
      <header className="import-header">
        <div>
          <h1>Sing-Along</h1>
          <p className="import-subtitle">Library setup — browse, edit, and curate songs</p>
        </div>
        {isAdmin && (
          <div className="import-header-actions">
            <button
              type="button"
              className="import-secondary-btn"
              onClick={handleEnrichTop}
              disabled={enriching}
            >
              {enriching ? 'Fetching lyrics/chords…' : 'Fetch top 100'}
            </button>
            <button
              type="button"
              className="import-sync-btn"
              onClick={() => setShowAddForm((open) => !open)}
            >
              {showAddForm ? 'Close' : 'Add song'}
            </button>
          </div>
        )}      </header>

      <section className="import-status">
        <button
          type="button"
          className={`import-status-card import-status-card--filter ${statusFilter === null ? 'import-status-card--active' : ''}`}
          onClick={() => setStatusFilter(null)}
          aria-pressed={statusFilter === null}
        >
          <span className="import-status-label">Total songs</span>
          <strong>{status?.total_songs ?? 0}</strong>
        </button>
        <button
          type="button"
          className={`import-status-card import-status-card--filter import-status-card--ready ${statusFilter === 'ready' ? 'import-status-card--active' : ''}`}
          onClick={() => toggleStatusFilter('ready')}
          aria-pressed={statusFilter === 'ready'}
        >
          <span className="import-status-label">Ready</span>
          <strong>{status?.ready_songs ?? 0}</strong>
        </button>
        <button
          type="button"
          className={`import-status-card import-status-card--filter import-status-card--needs ${statusFilter === 'needs_chords' ? 'import-status-card--active' : ''}`}
          onClick={() => toggleStatusFilter('needs_chords')}
          aria-pressed={statusFilter === 'needs_chords'}
        >
          <span className="import-status-label">Needs chords</span>
          <strong>{status?.needs_chords_songs ?? 0}</strong>
        </button>
      </section>

      {isAdmin && showAddForm && (
        <form className="import-add-form" onSubmit={handleAddSong}>
          <h2>Add a song</h2>
          <div className="import-add-grid">
            <label>
              Title
              <input
                type="text"
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                required
              />
            </label>
            <label>
              Artist
              <input
                type="text"
                value={form.artist}
                onChange={(e) => setForm({ ...form, artist: e.target.value })}
              />
            </label>
            <label>
              Language
              <select
                value={form.language}
                onChange={(e) => setForm({ ...form, language: e.target.value })}
              >
                <option value="auto">Auto detect</option>
                <option value="he">Hebrew</option>
                <option value="en">English</option>
              </select>
            </label>
            <label>
              YouTube URL (optional)
              <input
                type="url"
                value={form.youtube_url}
                onChange={(e) => setForm({ ...form, youtube_url: e.target.value })}
                placeholder="https://music.youtube.com/watch?v=..."
              />
            </label>
            <label>
              Lyrics / chords URL (optional)
              <input
                type="text"
                value={form.source_url}
                onChange={(e) => setForm({ ...form, source_url: e.target.value })}
                placeholder="https://guitartuna.com/... or tabs.ultimate-guitar.com/..."
                dir="ltr"
              />
            </label>
            <label>
              Play count
              <input
                type="number"
                min="0"
                value={form.play_count}
                onChange={(e) => setForm({ ...form, play_count: e.target.value })}
              />
            </label>
          </div>
          <button type="submit" className="import-sync-btn" disabled={saving}>
            {saving ? 'Saving…' : 'Save song'}
          </button>
        </form>
      )}

      {error && <div className="import-banner import-banner--error">{error}</div>}

      <div className="import-toolbar">
        <div className="import-tabs" role="tablist" aria-label="Language filter">
          {[
            { id: 'all', label: 'All' },
            { id: 'he', label: 'Hebrew' },
            { id: 'en', label: 'English' },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={activeTab === tab.id}
              className={`import-tab ${activeTab === tab.id ? 'import-tab--active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="import-sort" role="group" aria-label="Sort by">
          {SORT_OPTIONS.map((option) => (
            <button
              key={option.id}
              type="button"
              className={`import-sort-btn ${sortBy === option.id ? 'import-sort-btn--active' : ''}`}
              onClick={() => setSortBy(option.id)}
            >
              {option.label}
              {option.id === 'favorites' && favorites.length > 0 ? ` (${favorites.length})` : ''}
            </button>
          ))}
        </div>
        <input
          type="search"
          className="import-search"
          placeholder="Search title or artist…"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>

      <div className="import-layout">
        <div className="import-list-panel">
          {loading ? (
            <p className="import-empty">Loading…</p>
          ) : songs.length === 0 ? (
            <p className="import-empty">
              {sortBy === 'favorites'
                ? 'No favorites yet. Click the heart on a song to save it here.'
                : statusFilter === 'needs_chords'
                  ? 'No songs need chords right now.'
                  : statusFilter === 'ready'
                    ? 'No ready songs match your filters.'
                    : 'No songs match your filters.'}
            </p>
          ) : (
            <div className="import-list">
              {songs.map((song, index) => {
                const isFavorite = favorites.includes(song.id);
                return (
                <div
                  key={song.id}
                  className={`import-row ${selectedSong?.id === song.id ? 'import-row--active' : ''}`}
                >
                  <button
                    type="button"
                    className="import-row-main"
                    dir={song.language === 'he' ? 'rtl' : 'ltr'}
                    onClick={() => openSong(song.id)}
                  >
                    <span className="import-rank">{rangeStart + index}</span>
                    {song.thumbnail_url ? (
                      <img
                        className="import-thumb"
                        src={song.thumbnail_url}
                        alt=""
                        loading="lazy"
                      />
                    ) : (
                      <div className="import-thumb import-thumb--placeholder" aria-hidden />
                    )}
                    <div className="import-row-body">
                      <h2 className="import-title">{song.title}</h2>
                      <p className="import-artist">{song.artist || 'Unknown artist'}</p>
                    </div>
                    <div className="import-row-meta" dir="ltr">
                      <span className="import-plays">{song.play_count} plays</span>
                      <span className={`import-status-badge import-status-badge--${song.source_status}`}>
                        {statusLabel(song.source_status)}
                      </span>
                    </div>
                  </button>
                  <button
                    type="button"
                    className={`import-row-fav ${isFavorite ? 'import-row-fav--on' : ''}`}
                    aria-label={isFavorite ? 'Remove from favorites' : 'Add to favorites'}
                    onClick={(e) => toggleFavorite(song.id, e)}
                  >
                    {isFavorite ? '❤️' : '🤍'}
                  </button>
                  {isAdmin && (
                    <button
                      type="button"
                      className="import-row-remove"
                      aria-label={`Remove ${song.title}`}
                      onClick={() => setRemoveTarget(song)}
                    >
                      Remove
                    </button>
                  )}                </div>
              );
              })}
            </div>
          )}

          {!loading && totalSongs > 0 && (
            <div className="import-pagination">
              <button
                type="button"
                className="import-secondary-btn"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Previous
              </button>
              <span className="import-pagination-label">
                Page {page} of {totalPages}
              </span>
              <button
                type="button"
                className="import-secondary-btn"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              >
                Next
              </button>
            </div>
          )}
        </div>

        <aside className="import-sheet-panel">
          {!selectedSong ? (
            <p className="import-empty">Click a song to view or edit lyrics and chords.</p>
          ) : (
            <>
              <div className="import-sheet-header" dir={selectedSong.language === 'he' ? 'rtl' : 'ltr'}>
                <div className="import-sheet-title-row">
                  <div>
                    <h2>{selectedSong.title}</h2>
                    <p>{selectedSong.artist}</p>
                  </div>
                  <button
                    type="button"
                    className={`import-sheet-fav ${favorites.includes(selectedSong.id) ? 'import-sheet-fav--on' : ''}`}
                    aria-label={favorites.includes(selectedSong.id) ? 'Remove from favorites' : 'Add to favorites'}
                    onClick={() => toggleFavorite(selectedSong.id)}
                  >
                    {favorites.includes(selectedSong.id) ? '❤️' : '🤍'}
                  </button>
                </div>
                {selectedSong.source_url && (
                  <a href={selectedSong.source_url} target="_blank" rel="noreferrer">
                    Source: {selectedSong.chord_source}
                  </a>
                )}
                {selectedSong.enrich_error && (
                  <p className="import-sheet-error">{selectedSong.enrich_error}</p>
                )}
              </div>
              {isAdmin && (
                <div className="import-sheet-actions">
                  {hasEasy && (
                    <button
                      type="button"
                      className={`import-easy-toggle ${easyMode ? 'import-easy-toggle--on' : ''}`}
                      onClick={() => setEasyMode((on) => !on)}
                    >
                      {easyMode ? 'Original' : 'Easy version'}
                    </button>
                  )}
                  <button type="button" className="import-secondary-btn" onClick={handleRefetchSong} disabled={saving}>
                    Re-fetch
                  </button>
                  <button type="button" className="import-sync-btn" onClick={handleSaveSheet} disabled={saving}>
                    Save edits
                  </button>
                </div>
              )}
              {isAdmin && (
                <form className="import-source-link" onSubmit={handleApplySourceLink}>
                  <label className="import-source-link-label" htmlFor="import-source-url">
                    Correct source URL
                  </label>
                  <div className="import-source-link-row">
                    <input
                      id="import-source-url"
                      type="text"
                      className="import-source-link-input"
                      value={sourceLinkDraft}
                      onChange={(e) => setSourceLinkDraft(e.target.value)}
                      placeholder="https://guitartuna.com/... or tabs.ultimate-guitar.com/..."
                      dir="ltr"
                    />
                    <button
                      type="submit"
                      className="import-secondary-btn"
                      disabled={saving || !sourceLinkDraft.trim()}
                    >
                      {saving ? 'Applying…' : 'Apply link'}
                    </button>
                  </div>
                  <p className="import-source-link-hint">
                    Ultimate Guitar, GuitarTuna, Tab4U, e-chords, Negina, or Nagnu — replaces auto-matched chords.
                  </p>
                </form>
              )}
              {!isAdmin && hasEasy && (
                <div className="import-sheet-actions">
                  <button
                    type="button"
                    className={`import-easy-toggle ${easyMode ? 'import-easy-toggle--on' : ''}`}
                    onClick={() => setEasyMode((on) => !on)}
                  >
                    {easyMode ? 'Original' : 'Easy version'}
                  </button>
                </div>
              )}              {activeNote && <p className="import-sheet-note">{activeNote}</p>}
              <textarea
                className="import-sheet-editor"
                dir="ltr"
                value={sheetValue}
                onChange={(e) => handleSheetChange(e.target.value)}
                readOnly={!isAdmin}
                placeholder="Lyrics and chords will appear here. Paste from Tab4U or Nagnu if needed."
              />            </>
          )}
        </aside>
      </div>

      {totalSongs > 0 && (
        <p className="import-footer-note">
          Showing {rangeStart}–{rangeEnd} of {totalSongs}
          {statusFilter === 'needs_chords' ? ' needing chords' : ''}
          {statusFilter === 'ready' ? ' ready' : ''}
          {activeTab === 'all' && songs.length > 0 ? ` (${hebrewCount} Hebrew on this page)` : ''}
        </p>
      )}

      {removeTarget && (
        <div className="import-modal-overlay" role="presentation" onClick={() => !removing && setRemoveTarget(null)}>
          <div
            className="import-modal"
            role="alertdialog"
            aria-labelledby="remove-dialog-title"
            aria-describedby="remove-dialog-desc"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="remove-dialog-title">Remove song?</h2>
            <p id="remove-dialog-desc">
              <strong dir={removeTarget.language === 'he' ? 'rtl' : 'ltr'}>{removeTarget.title}</strong>
              {removeTarget.artist ? ` — ${removeTarget.artist}` : ''} will be hidden from your library.
              The data stays in the database and can be restored later if needed.
            </p>
            <div className="import-modal-actions">
              <button
                type="button"
                className="import-secondary-btn"
                disabled={removing}
                onClick={() => setRemoveTarget(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="import-remove-confirm-btn"
                disabled={removing}
                onClick={handleConfirmRemove}
              >
                {removing ? 'Removing…' : 'Remove'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
