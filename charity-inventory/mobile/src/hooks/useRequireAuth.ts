import { useEffect } from 'react';
import { router } from 'expo-router';
import { useApp } from '../context/AppContext';

export function useRequireAuth() {
  const { user, loading } = useApp();

  useEffect(() => {
    if (!loading && !user) {
      router.replace('/login');
    }
  }, [user, loading]);

  return { user, loading };
}

export function useRequireSession() {
  const { selectedCenter, sessionId, loading } = useApp();
  const auth = useRequireAuth();

  useEffect(() => {
    if (!auth.loading && auth.user && (!selectedCenter || !sessionId)) {
      router.replace('/centers');
    }
  }, [auth.loading, auth.user, selectedCenter, sessionId]);

  return { ...auth, selectedCenter, sessionId };
}
