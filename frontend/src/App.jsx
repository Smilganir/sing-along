import { Suspense, lazy, useEffect, useState } from 'react';

import AdminUnlockModal from './components/AdminUnlockModal.jsx';
import { AuthProvider, useAuth } from './context/AuthContext.jsx';
import { FavoritesProvider } from './context/FavoritesContext.jsx';
import Sing from './pages/Sing.jsx';
import { parseRouteBase } from './utils/routes.js';
import './App.css';

const Import = lazy(() => import('./pages/Import.jsx'));

function useRoute() {
  const [route, setRoute] = useState(() => parseRouteBase(window.location.hash));

  useEffect(() => {
    function onHashChange() {
      setRoute(parseRouteBase(window.location.hash));
    }
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  return route === 'library' ? 'library' : 'sing';
}

function AppNav() {
  const route = useRoute();
  const { isAdmin, setShowUnlock, logout } = useAuth();

  return (
    <nav className="app-nav" aria-label="Main navigation">
      <div className="app-nav-start">
        <a
          href="#sing"
          className={`app-nav-link ${route === 'sing' ? 'app-nav-link--active' : ''}`}
        >
          Sing
        </a>
        <a
          href="#library"
          className={`app-nav-link ${route === 'library' ? 'app-nav-link--active' : ''}`}
        >
          Library
        </a>
      </div>
      <h1 className="app-nav-title">Sing-Along</h1>
      <div className="app-nav-end">
        {isAdmin ? (
          <button type="button" className="app-nav-btn" onClick={() => logout()}>
            Log out
          </button>
        ) : (
          <button type="button" className="app-nav-btn app-nav-btn--primary" onClick={() => setShowUnlock(true)}>
            Unlock admin
          </button>
        )}
      </div>
    </nav>
  );
}

function AppRoutes() {
  const route = useRoute();
  return route === 'library' ? <Import /> : <Sing />;
}

export default function App() {
  return (
    <AuthProvider>
      <FavoritesProvider>
        <AppNav />
        <Suspense fallback={<div style={{ padding: '2rem', textAlign: 'center' }}>Loading…</div>}>
          <AppRoutes />
        </Suspense>
        <AdminUnlockModal />
      </FavoritesProvider>
    </AuthProvider>
  );
}
