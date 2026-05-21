import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import ChordProSheet from '../components/ChordProSheet.jsx';
import { EnrichmentStatusBadge, EnrichmentStatusIcon } from '../components/EnrichmentStatus.jsx';

import { getSong, getSongs, scrollRoom, subscribeRoomState, syncRoom } from '../api/client.js';

import { useAuth } from '../context/AuthContext.jsx';
import { useLocalStorage } from '../hooks/useLocalStorage.js';
import { youtubeEmbedUrl } from '../utils/chordpro.js';
import { librarySongHref } from '../utils/routes.js';
import { transposeSheet } from '../utils/transpose.js';

import './Sing.css';

const PAGE_SIZE = 50;
const SCROLL_EMIT_MS = 100;
const SUPPRESS_SCROLL_MS = 400;

function getTopmostAnchor(container) {
  if (!container) return null;
  const blocks = container.querySelectorAll('[data-anchor]');
  const containerTop = container.getBoundingClientRect().top;
  let bestAnchor = null;
  let bestDistance = Infinity;

  blocks.forEach((block) => {
    const rect = block.getBoundingClientRect();
    if (rect.bottom <= containerTop) return;
    const distance = Math.abs(rect.top - containerTop);
    if (distance < bestDistance) {
      bestDistance = distance;
      bestAnchor = block.getAttribute('data-anchor');
    }
  });

  return bestAnchor;
}

function scrollSheetToAnchor(container, anchor) {
  if (!container || !anchor) return false;
  const escaped = typeof CSS !== 'undefined' && CSS.escape ? CSS.escape(anchor) : anchor;
  const block = container.querySelector(`[data-anchor="${escaped}"]`);
  if (!block) return false;
  block.scrollIntoView({ block: 'start', behavior: 'smooth' });
  return true;
}

const SORT_OPTIONS = [  { id: 'play_count', label: 'Most played' },
  { id: 'last_played_at', label: 'Recently played' },
  { id: 'favorites', label: 'Favorites' },
];

const STATUS_FILTERS = [
  { id: 'all', label: 'All', status: null },
  { id: 'ready', label: 'Ready only', status: 'ready' },
  { id: 'needs_chords', label: 'Lyrics only (needs chords)', status: 'needs_chords' },
];

function formatEnrichHistoryTooltip(history) {
  if (!history?.length) return '';
  return history
    .slice(-3)
    .reverse()
    .map((attempt) => {
      const when = attempt.ts ? new Date(attempt.ts).toLocaleString() : 'unknown';
      const source = attempt.source || '—';
      const status = attempt.status || 'unknown';
      const error = attempt.error ? ` — ${attempt.error}` : '';
      return `${when} · ${source} · ${status}${error}`;
    })
    .join('\n');
}

export default function Sing() {
  const { isAdmin } = useAuth();
  const [songs, setSongs] = useState([]);  const [totalSongs, setTotalSongs] = useState(0);
  const [page, setPage] = useState(1);
  const [activeTab, setActiveTab] = useState('all');
  const [sortBy, setSortBy] = useState('play_count');
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [selectedSong, setSelectedSong] = useState(null);
  const [easyMode, setEasyMode] = useState(false);
  const [roomState, setRoomState] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [leadScroll, setLeadScroll] = useState(false);
  const [followMode, setFollowMode] = useState('following');
  const [transposeSemitones, setTransposeSemitones] = useState(0);

  const [lyricsOnly, setLyricsOnly] = useLocalStorage('singalong-lyrics-only', false);
  const [showYoutube, setShowYoutube] = useLocalStorage('singalong-show-youtube', false);
  const [favorites] = useLocalStorage('singalong-favorites', []);
  const [sidebarOpen, setSidebarOpen] = useLocalStorage('singalong-sidebar-open', true);
  const [statusFilter, setStatusFilter] = useLocalStorage('singalong-status-filter', 'all');

  const lastRoomUpdated = useRef(null);
  const lastRoomSongId = useRef(null);
  const lastScrollUpdated = useRef(null);
  const lastEmittedAnchor = useRef(null);
  const scrollEmitTimer = useRef(null);
  const suppressScrollUntil = useRef(0);
  const sheetWrapRef = useRef(null);
  const followModeRef = useRef(followMode);
  const leadScrollRef = useRef(leadScroll);
  const isYoutubeFullscreen = useRef(false);
  const selectedSongIdRef = useRef(null);

  followModeRef.current = followMode;
  leadScrollRef.current = leadScroll;
  selectedSongIdRef.current = selectedSong?.id ?? null;

  const langFilter = activeTab === 'he' || activeTab === 'en' ? activeTab : undefined;
  const apiSort = sortBy === 'favorites' ? 'play_count' : sortBy;
  const statusParam = STATUS_FILTERS.find((f) => f.id === statusFilter)?.status ?? null;
  const totalPages = Math.max(1, Math.ceil(totalSongs / PAGE_SIZE));
  const rangeStart = totalSongs === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const canSyncRoom = selectedSong?.source_status === 'ready';
  const isRoomSynced = Boolean(
    selectedSong && roomState?.song_id && roomState.song_id === selectedSong.id,
  );
  const isOnRoomSong = Boolean(
    selectedSong && roomState?.song_id && roomState.song_id === selectedSong.id,
  );

  const applyRoomScroll = useCallback((anchor) => {
    const container = sheetWrapRef.current;
    if (!container || !anchor) return;
    suppressScrollUntil.current = Date.now() + SUPPRESS_SCROLL_MS;
    scrollSheetToAnchor(container, anchor);
  }, []);

  const resumeFollowing = useCallback(() => {
    setFollowMode('following');
    if (roomState?.scroll_anchor) {
      applyRoomScroll(roomState.scroll_anchor);
    }
  }, [applyRoomScroll, roomState?.scroll_anchor]);

  const loadList = useCallback(async () => {
    setLoading(true);
    try {
      const result = await getSongs({
        lang: langFilter,
        q: searchQuery.trim() || undefined,
        sort: apiSort,
        ids: sortBy === 'favorites' ? favorites : undefined,
        status: statusParam,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      });
      setSongs(result.items);
      setTotalSongs(result.total);
    } catch {
      setSongs([]);
      setTotalSongs(0);
    } finally {
      setLoading(false);
    }
  }, [langFilter, searchQuery, sortBy, apiSort, favorites, page, statusParam]);

  useEffect(() => {
    setPage(1);
  }, [langFilter, searchQuery, sortBy, statusFilter]);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  useEffect(() => {
    loadList();
  }, [loadList]);

  useEffect(() => {
    let cancelled = false;

    function handleRoomState(state) {
      if (cancelled) return;

      setRoomState(state);

      const songChanged = Boolean(
        state.song_id
        && (state.song_id !== lastRoomSongId.current
          || state.updated_at !== lastRoomUpdated.current),
      );

      if (songChanged) {
        lastRoomUpdated.current = state.updated_at;
        lastRoomSongId.current = state.song_id;
        lastScrollUpdated.current = null;
        lastEmittedAnchor.current = null;
        setFollowMode('following');
        setLeadScroll(false);
        getSong(state.song_id)
          .then((detail) => {
            if (!cancelled) {
              setSelectedSong(detail);
              setEasyMode(false);
            }
          })
          .catch(() => {
            /* best-effort room sync */
          });
      }
    }

    const unsubscribe = subscribeRoomState(
      handleRoomState,
      () => {
        if (!cancelled) {
          console.warn('Room stream disconnected; reconnecting…');
        }
      },
    );

    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, []);

  async function openSong(songId) {
    setEasyMode(false);
    try {
      const detail = await getSong(songId);
      setSelectedSong(detail);
    } catch {
      setSelectedSong(null);
    }
  }

  async function syncToRoom() {
    if (!selectedSong) return;
    setSyncing(true);
    try {
      const state = await syncRoom(selectedSong.id);
      setRoomState(state);
      lastRoomUpdated.current = state.updated_at;
      lastRoomSongId.current = state.song_id;
      lastScrollUpdated.current = null;
      lastEmittedAnchor.current = null;
      setFollowMode('following');
      setLeadScroll(false);
    } catch {
      /* ignore */
    } finally {
      setSyncing(false);
    }
  }

  const sheetText = useMemo(() => {
    if (!selectedSong) return '';
    let text = '';
    if (easyMode && selectedSong.chordpro_easy) text = selectedSong.chordpro_easy;
    else text = selectedSong.chordpro_full || selectedSong.plain_lyrics || '';

    if (!lyricsOnly && transposeSemitones !== 0 && text) {
      text = transposeSheet(text, transposeSemitones);
    }
    return text;
  }, [selectedSong, easyMode, lyricsOnly, transposeSemitones]);

  useEffect(() => {
    if (!roomState?.scroll_updated_at || !roomState.scroll_anchor) return;
    if (roomState.scroll_updated_at === lastScrollUpdated.current) return;
    lastScrollUpdated.current = roomState.scroll_updated_at;

    if (leadScrollRef.current) return;
    if (followModeRef.current !== 'following') return;
    if (selectedSongIdRef.current !== roomState.song_id) return;
    if (isYoutubeFullscreen.current) return;

    applyRoomScroll(roomState.scroll_anchor);
  }, [
    roomState?.scroll_anchor,
    roomState?.scroll_updated_at,
    roomState?.song_id,
    applyRoomScroll,
  ]);

  useEffect(() => {
    function onFullscreenChange() {
      isYoutubeFullscreen.current = Boolean(document.fullscreenElement);
      if (isYoutubeFullscreen.current) {
        setFollowMode('paused');
      }
    }

    document.addEventListener('fullscreenchange', onFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', onFullscreenChange);
  }, []);

  useEffect(() => {
    const container = sheetWrapRef.current;
    if (!container) return undefined;

    function onUserScroll() {
      if (Date.now() < suppressScrollUntil.current) return;
      if (leadScrollRef.current) return;
      if (selectedSongIdRef.current !== lastRoomSongId.current) return;
      if (isYoutubeFullscreen.current) return;
      setFollowMode('paused');
    }

    container.addEventListener('scroll', onUserScroll, { passive: true });
    return () => container.removeEventListener('scroll', onUserScroll);
  }, [selectedSong?.id, sheetText]);

  useEffect(() => {
    const container = sheetWrapRef.current;
    if (!container || !leadScroll || !isAdmin || !isRoomSynced) return undefined;

    function scheduleEmit(anchor) {
      if (!anchor || anchor === lastEmittedAnchor.current) return;
      clearTimeout(scrollEmitTimer.current);
      scrollEmitTimer.current = setTimeout(() => {
        lastEmittedAnchor.current = anchor;
        scrollRoom(anchor).catch(() => {});
      }, SCROLL_EMIT_MS);
    }

    function updateAnchor() {
      if (Date.now() < suppressScrollUntil.current) return;
      const anchor = getTopmostAnchor(container);
      if (anchor) scheduleEmit(anchor);
    }

    const blocks = container.querySelectorAll('[data-anchor]');
    const observer = new IntersectionObserver(
      () => updateAnchor(),
      { root: container, threshold: [0, 0.01, 0.1, 0.5, 1] },
    );

    blocks.forEach((block) => observer.observe(block));
    container.addEventListener('scroll', updateAnchor, { passive: true });
    updateAnchor();

    return () => {
      observer.disconnect();
      container.removeEventListener('scroll', updateAnchor);
      clearTimeout(scrollEmitTimer.current);
    };
  }, [leadScroll, isAdmin, isRoomSynced, sheetText, selectedSong?.id]);

  useEffect(() => {
    if (!isRoomSynced) {
      setLeadScroll(false);
    }
  }, [isRoomSynced]);

  useEffect(() => {
    setTransposeSemitones(0);
  }, [selectedSong?.id, easyMode]);

  useEffect(() => {
    if (lyricsOnly) setEasyMode(false);
  }, [lyricsOnly]);

  const hasEasy = Boolean(selectedSong?.chordpro_easy?.trim());
  const showChords = !lyricsOnly;
  const showEasyToggle = showChords && Boolean(selectedSong);
  const hasChordSheet = Boolean(
    (easyMode && selectedSong?.chordpro_easy?.trim()) || selectedSong?.chordpro_full?.trim(),
  );
  const showTranspose = showChords && hasChordSheet;

  const easyNote =
    easyMode && selectedSong
      ? selectedSong.language === 'he'
        ? selectedSong.easy_note_he
        : selectedSong.easy_note_en
      : null;

  const embedUrl = showYoutube && selectedSong?.youtube_url
    ? youtubeEmbedUrl(selectedSong.youtube_url)
    : null;

  return (
    <div className="sing-page">
      <header className="sing-header">
        <div>
          <h1>Sing-Along</h1>
          <p className="sing-subtitle">Pick a song and sing together</p>
        </div>
        <div className="sing-view-toggles" role="group" aria-label="Your display options">
          <button
            type="button"
            className={`sing-toggle ${lyricsOnly ? 'sing-toggle--on' : ''}`}
            onClick={() => setLyricsOnly((on) => !on)}
            title="Only you see this — not synced with the room"
          >
            {lyricsOnly ? 'Show chords' : 'Lyrics only'}
          </button>
          {showEasyToggle && (
            <button
              type="button"
              className={`sing-toggle sing-toggle--easy ${easyMode ? 'sing-toggle--on' : ''}`}
              onClick={() => setEasyMode((on) => !on)}
              disabled={!hasEasy}
              title={
                hasEasy
                  ? 'Only you see this — not synced with the room'
                  : 'No easy version available for this song'
              }
            >
              {easyMode ? 'Original' : 'Easy version'}
            </button>
          )}
          {showTranspose && (
            <div className="sing-transpose" role="group" aria-label="Transpose chords">
              <span className="sing-transpose-label">Key</span>
              <button
                type="button"
                className="sing-transpose-btn"
                onClick={() => setTransposeSemitones((n) => n - 1)}
                aria-label="Transpose down one semitone"
              >
                −
              </button>
              <span className="sing-transpose-value" aria-live="polite">
                {transposeSemitones > 0 ? `+${transposeSemitones}` : transposeSemitones}
              </span>
              <button
                type="button"
                className="sing-transpose-btn"
                onClick={() => setTransposeSemitones((n) => n + 1)}
                aria-label="Transpose up one semitone"
              >
                +
              </button>
              {transposeSemitones !== 0 && (
                <button
                  type="button"
                  className="sing-transpose-reset"
                  onClick={() => setTransposeSemitones(0)}
                  title="Reset transpose to original key"
                >
                  Reset
                </button>
              )}
            </div>
          )}
          <button
            type="button"
            className={`sing-toggle ${showYoutube ? 'sing-toggle--on' : ''}`}
            onClick={() => setShowYoutube((on) => !on)}
            title="Only you see this — not synced with the room"
            disabled={!selectedSong?.youtube_url}
          >
            YouTube
          </button>
        </div>
      </header>

      {roomState?.song_id && (
        <p className="sing-room-banner">
          Room song: <strong>{roomState.title}</strong>
          {roomState.artist ? ` — ${roomState.artist}` : ''}
        </p>
      )}

      <p className="sing-personal-note">
        Lyrics-only and YouTube are personal.
        {isAdmin ? ' Use Sync room to share the current song with everyone.' : ' Ask an admin to sync the room song.'}
      </p>
      <div className={`sing-layout ${sidebarOpen ? '' : 'sing-layout--sidebar-collapsed'}`}>
        {!sidebarOpen && (
          <button
            type="button"
            className="sing-sidebar-expand"
            onClick={() => setSidebarOpen(true)}
            aria-label="Show song list"
            title="Show song list"
          >
            Song list
          </button>
        )}

        <aside className={`sing-sidebar ${sidebarOpen ? '' : 'sing-sidebar--collapsed'}`} aria-hidden={!sidebarOpen}>
          <div className="sing-sidebar-header">
            <span className="sing-sidebar-title">Song list</span>
            <button
              type="button"
              className="sing-sidebar-toggle"
              onClick={() => setSidebarOpen(false)}
              aria-label="Hide song list"
              title="Hide song list"
            >
              Hide
            </button>
          </div>

          <div className="sing-toolbar">
            <div className="sing-tabs" role="tablist" aria-label="Language filter">
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
                  className={`sing-tab ${activeTab === tab.id ? 'sing-tab--active' : ''}`}
                  onClick={() => setActiveTab(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="sing-sort" role="group" aria-label="Sort by">
              {SORT_OPTIONS.map((option) => (
                <button
                  key={option.id}
                  type="button"
                  className={`sing-sort-btn ${sortBy === option.id ? 'sing-sort-btn--active' : ''}`}
                  onClick={() => setSortBy(option.id)}
                >
                  {option.label}
                  {option.id === 'favorites' && favorites.length > 0 ? ` (${favorites.length})` : ''}
                </button>
              ))}
            </div>

            <label className="sing-status-filter">
              <span className="sing-status-filter-label">Show:</span>
              <select
                className="sing-status-filter-select"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                aria-label="Filter by enrichment status"
              >
                {STATUS_FILTERS.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>

            <input
              type="search"
              className="sing-search"
              placeholder="Search title or artist…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          {loading ? (
            <p className="sing-empty">Loading…</p>
          ) : songs.length === 0 ? (
            <p className="sing-empty">
              {sortBy === 'favorites'
                ? 'No favorites yet. Mark songs in the Library.'
                : 'No songs match your filters.'}
            </p>
          ) : (
            <ul className="sing-song-list">
              {songs.map((song, index) => (
                <li key={song.id} className="sing-song-row">
                  <button
                    type="button"
                    className={`sing-song-item ${selectedSong?.id === song.id ? 'sing-song-item--active' : ''} ${roomState?.song_id === song.id ? 'sing-song-item--room' : ''}`}
                    dir={song.language === 'he' ? 'rtl' : 'ltr'}
                    onClick={() => openSong(song.id)}
                  >
                    <span className="sing-song-rank">{rangeStart + index}</span>
                    <span className="sing-song-info">
                      <strong>{song.title}</strong>
                      <span>{song.artist || 'Unknown artist'}</span>
                    </span>
                    <EnrichmentStatusIcon status={song.source_status} />
                    {favorites.includes(song.id) && (
                      <span className="sing-song-fav" aria-label="Favorite">❤️</span>
                    )}
                    {roomState?.song_id === song.id && (
                      <span className="sing-song-room" aria-label="Room song">🎤</span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}

          {!loading && totalSongs > 0 && (
            <div className="sing-pagination">
              <button
                type="button"
                className="sing-btn-secondary"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Prev
              </button>
              <span>
                {page}/{totalPages}
              </span>
              <button
                type="button"
                className="sing-btn-secondary"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              >
                Next
              </button>
            </div>
          )}
        </aside>

        <main className="sing-main">
          {!selectedSong ? (
            <div className="sing-placeholder">
              <h2>Select a song</h2>
              <p>Choose from {totalSongs} songs in the list, or wait for the room to sync.</p>
            </div>
          ) : (
            <>
              <div className="sing-main-header" dir={selectedSong.language === 'he' ? 'rtl' : 'ltr'}>
                <div>
                  <div className="sing-main-title-row">
                    <h2>{selectedSong.title}</h2>
                    <EnrichmentStatusBadge status={selectedSong.source_status} />
                    {isAdmin && selectedSong.enrich_history?.length > 0 && (
                      <span
                        className="sing-attempts-badge"
                        title={formatEnrichHistoryTooltip(selectedSong.enrich_history)}
                      >
                        attempts: {selectedSong.enrich_attempts ?? selectedSong.enrich_history.length}
                      </span>
                    )}
                  </div>
                  <p>{selectedSong.artist}</p>
                  <div className="sing-main-meta-links">
                    {selectedSong.source_url && (
                      <a
                        className="sing-source-open"
                        href={selectedSong.source_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Source: {selectedSong.chord_source || 'link'}
                      </a>
                    )}
                    {isAdmin && (
                      <a
                        href={librarySongHref(selectedSong.id)}
                        className="sing-library-link"
                        title="Edit in Library"
                        aria-label={`Edit ${selectedSong.title} in Library`}
                      >
                        Edit
                      </a>
                    )}
                  </div>
                </div>
                <div className="sing-main-actions">
                  {isAdmin && (
                    <button
                      type="button"
                      className={`sing-sync-btn ${isRoomSynced ? 'sing-sync-btn--synced' : ''}`}
                      onClick={syncToRoom}
                      disabled={syncing || isRoomSynced || !canSyncRoom}
                      title={
                        !canSyncRoom
                          ? 'Only songs with chords can be synced to the room'
                          : 'Share this song with everyone viewing the app'
                      }
                    >
                      {syncing ? 'Syncing…' : isRoomSynced ? 'Synced with room' : 'Sync room'}
                    </button>
                  )}
                  {showEasyToggle && (
                    <button
                      type="button"
                      className={`sing-toggle sing-toggle--easy ${easyMode ? 'sing-toggle--on' : ''}`}
                      onClick={() => setEasyMode((on) => !on)}
                      disabled={!hasEasy}
                      title={
                        hasEasy
                          ? 'Switch to simplified chords (capo-friendly)'
                          : 'No easy version available for this song'
                      }
                    >
                      {easyMode ? 'Original' : 'Easy version'}
                    </button>
                  )}
                  {isAdmin && isRoomSynced && (
                    <button
                      type="button"
                      className={`sing-lead-scroll-btn ${leadScroll ? 'sing-lead-scroll-btn--on' : ''}`}
                      onClick={() => setLeadScroll((on) => !on)}
                      title={
                        leadScroll
                          ? 'Stop broadcasting your scroll position'
                          : 'Broadcast your scroll position to everyone on this song'
                      }
                    >
                      {leadScroll ? '● Leading scroll' : 'Lead scroll'}
                    </button>
                  )}
                  {selectedSong.youtube_url && (
                    <a
                      className="sing-yt-link"
                      href={selectedSong.youtube_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Open on YouTube
                    </a>
                  )}
                </div>
              </div>

              {easyNote && <p className="sing-easy-note">{easyNote}</p>}

              {embedUrl && (
                <div className="sing-youtube">
                  <iframe
                    title={`YouTube: ${selectedSong.title}`}
                    src={embedUrl}
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                    allowFullScreen
                  />
                </div>
              )}

              <div className="sing-sheet-wrap" ref={sheetWrapRef}>
                {isOnRoomSong && !leadScroll && (
                  <div className="sing-follow-bar">
                    {followMode === 'following' ? (
                      <span className="sing-follow-status">Following room scroll</span>
                    ) : (
                      <>
                        <span className="sing-follow-status sing-follow-status--paused">Paused</span>
                        <button
                          type="button"
                          className="sing-follow-resume"
                          onClick={resumeFollowing}
                        >
                          Resume
                        </button>
                      </>
                    )}
                  </div>
                )}
                <ChordProSheet
                  text={sheetText}
                  language={selectedSong.language}
                  lyricsOnly={lyricsOnly}
                />
              </div>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
