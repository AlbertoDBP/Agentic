import { Redirect } from 'expo-router';
import { LoadingState } from '../src/components/ui';
import { useApp } from '../src/context/AppContext';

export default function IndexScreen() {
  const { user, loading } = useApp();

  if (loading) {
    return <LoadingState />;
  }

  if (!user) {
    return <Redirect href="/login" />;
  }

  return <Redirect href="/centers" />;
}
