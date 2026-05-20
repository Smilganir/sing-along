import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { getAuthMe, loginAdmin, logoutAdmin } from '../api/client.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [isAdmin, setIsAdmin] = useState(false);
  const [checked, setChecked] = useState(false);
  const [showUnlock, setShowUnlock] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const data = await getAuthMe();
      setIsAdmin(Boolean(data.admin));
    } catch {
      setIsAdmin(false);
    } finally {
      setChecked(true);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const login = useCallback(async (password) => {
    await loginAdmin(password);
    await refresh();
    setShowUnlock(false);
  }, [refresh]);

  const logout = useCallback(async () => {
    await logoutAdmin();
    setIsAdmin(false);
  }, []);

  const value = useMemo(
    () => ({
      isAdmin,
      checked,
      showUnlock,
      setShowUnlock,
      login,
      logout,
      refresh,
    }),
    [isAdmin, checked, showUnlock, login, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return ctx;
}
