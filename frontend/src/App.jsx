import { Suspense, lazy, useEffect, useState } from 'react';

import AdminUnlockModal from './components/AdminUnlockModal.jsx';
import { AuthProvider, useAuth } from './context/AuthContext.jsx';
import { FavoritesProvider } from './context/FavoritesContext.jsx';
import { parseRouteBase } from './utils/routes.js';
import './App.css';

const Sing = lazy(() => import('./pages/Sing.jsx'));
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

  return route === 'admin' ? 'admin' : 'sing';
}

function AppNav() {
  const route = useRoute();
  const { isAdmin, setShowUnlock, logout } = useAuth();

  return (
    <nav className="app-nav" aria-label="Main navigation">
      <h1 className="app-nav-brand">
        <img
          className="app-nav-logo"
          src={`${import.meta.env.BASE_URL}sing-along-logo.png`}
          alt="Sing-Along"
          width={320}
          height={54}
        />
      </h1>
      <div className="app-nav-bar">
        <div className="app-nav-tabs" role="tablist" aria-label="Pages">
          <a
            href="#sing"
            role="tab"
            aria-selected={route === 'sing'}
            className={`app-nav-tab ${route === 'sing' ? 'app-nav-tab--active' : ''}`}
          >
            Sing
          </a>
          <a
            href="#admin"
            role="tab"
            aria-selected={route === 'admin'}
            className={`app-nav-tab ${route === 'admin' ? 'app-nav-tab--active' : ''}`}
          >
            Admin
          </a>
        </div>
        <div className="app-nav-end">
          {isAdmin ? (
            <button type="button" className="app-nav-tab-action" onClick={() => logout()}>
              Log out
            </button>
          ) : (
            <button type="button" className="app-nav-tab-action" onClick={() => setShowUnlock(true)}>
              Unlock admin
            </button>
          )}
        </div>
      </div>
    </nav>
  );
}

function AppRoutes() {
  const route = useRoute();
  return route === 'admin' ? <Import /> : <Sing />;
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
