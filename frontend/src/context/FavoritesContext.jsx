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

function readLegacyFavorites() {
  try {
    const raw = localStorage.getItem(LEGACY_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((id) => Number.isInteger(id)) : [];
  } catch {
    return [];
  }
}

export function FavoritesProvider({ children }) {
  const [favorites, setFavorites] = useState([]);
  const [ready, setReady] = useState(false);
  const favoritesRef = useRef(favorites);

  favoritesRef.current = favorites;

  useEffect(() => {
    let cancelled = false;

    async function init() {
      try {
        let data = await getFavorites();
        if (cancelled) return;

        const migrated = localStorage.getItem(MIGRATED_KEY);
        if (!migrated) {
          const legacy = readLegacyFavorites();
          const merged = [...new Set([...(data.ids ?? []), ...legacy])];
          if (merged.length !== (data.ids ?? []).length) {
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
  }, []);

  useEffect(() => {
    if (!ready) return undefined;

    return subscribeFavorites(
      (data) => {
        if (Array.isArray(data.ids)) {
          setFavorites(data.ids);
        }
      },
      () => {
        /* reconnect handled in client */
      },
    );
  }, [ready]);

  const toggleFavorite = useCallback(async (songId, event) => {
    event?.stopPropagation();
    const previous = favoritesRef.current;
    const wasFavorite = previous.includes(songId);
    const optimistic = wasFavorite
      ? previous.filter((id) => id !== songId)
      : [...previous, songId];

    setFavorites(optimistic);

    try {
      const data = wasFavorite
        ? await removeFavorite(songId)
        : await addFavorite(songId);
      setFavorites(data.ids ?? optimistic);
    } catch {
      setFavorites(previous);
    }
  }, []);

  const isFavorite = useCallback(
    (songId) => favorites.includes(songId),
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
