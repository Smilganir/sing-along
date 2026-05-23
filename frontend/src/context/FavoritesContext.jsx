import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import {
  addFavorite,
  getFavorites,
  removeFavorite,
  subscribeFavorites,
  syncFavorites,
} from '../api/client.js';

const FavoritesContext = createContext(null);

const LEGACY_KEY = 'singalong-favorites';
const MIGRATED_KEY = 'singalong-favorites-migrated';

function normalizeIds(ids) {
  if (!Array.isArray(ids)) return [];
  return [...new Set(
    ids
      .map((id) => Number(id))
      .filter((id) => Number.isInteger(id) && id > 0),
  )];
}

function readLegacyFavorites() {
  try {
    const raw = localStorage.getItem(LEGACY_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return normalizeIds(parsed);
  } catch {
    return [];
  }
}

export function FavoritesProvider({ children }) {
  const [favorites, setFavoritesState] = useState([]);
  const [ready, setReady] = useState(false);
  const favoritesRef = useRef(favorites);
  const pendingToggleRef = useRef(false);

  favoritesRef.current = favorites;

  const setFavorites = useCallback((next) => {
    setFavoritesState((prev) => {
      const raw = typeof next === 'function' ? next(prev) : next;
      return normalizeIds(raw);
    });
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        let data = await getFavorites();
        if (cancelled) return;

        const migrated = localStorage.getItem(MIGRATED_KEY);
        if (!migrated) {
          const legacy = readLegacyFavorites();
          const merged = [...new Set([...normalizeIds(data.ids ?? []), ...legacy])];
          if (merged.length !== normalizeIds(data.ids ?? []).length) {
            data = await syncFavorites(merged);
          }
          localStorage.setItem(MIGRATED_KEY, '1');
          localStorage.removeItem(LEGACY_KEY);
        }

        if (!cancelled) {
          setFavorites(data.ids ?? []);
        }
      } catch {
        if (!cancelled) setFavorites(readLegacyFavorites());
      } finally {
        if (!cancelled) setReady(true);
      }
    }

    init();
    return () => {
      cancelled = true;
    };
  }, [setFavorites]);

  useEffect(() => {
    if (!ready) return undefined;

    return subscribeFavorites(
      (data) => {
        if (pendingToggleRef.current) return;
        if (Array.isArray(data.ids)) {
          setFavorites(data.ids);
        }
      },
      () => {
        /* reconnect handled in client */
      },
    );
  }, [ready, setFavorites]);

  const toggleFavorite = useCallback(async (songId, event) => {
    event?.stopPropagation();
    const sid = Number(songId);
    if (!Number.isInteger(sid) || sid <= 0) return;

    const previous = normalizeIds(favoritesRef.current);
    const wasFavorite = previous.includes(sid);
    const optimistic = wasFavorite
      ? previous.filter((id) => id !== sid)
      : [...previous, sid];

    pendingToggleRef.current = true;
    setFavorites(optimistic);

    try {
      const data = wasFavorite
        ? await removeFavorite(sid)
        : await addFavorite(sid);
      setFavorites(data.ids ?? optimistic);
    } catch {
      try {
        const data = await getFavorites();
        const serverIds = normalizeIds(data.ids ?? []);
        const changed = serverIds.includes(sid) !== wasFavorite;
        setFavorites(changed ? serverIds : previous);
      } catch {
        setFavorites(previous);
      }
    } finally {
      pendingToggleRef.current = false;
    }
  }, [setFavorites]);

  const isFavorite = useCallback(
    (songId) => favorites.some((id) => id === Number(songId)),
    [favorites],
  );

  const value = useMemo(
    () => ({
      favorites,
      ready,
      isFavorite,
      toggleFavorite,
    }),
    [favorites, ready, isFavorite, toggleFavorite],
  );

  return (
    <FavoritesContext.Provider value={value}>{children}</FavoritesContext.Provider>
  );
}

export function useFavorites() {
  const ctx = useContext(FavoritesContext);
  if (!ctx) {
    throw new Error('useFavorites must be used within FavoritesProvider');
  }
  return ctx;
}
