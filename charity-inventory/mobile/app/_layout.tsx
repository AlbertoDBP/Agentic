import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { AppProvider } from '../src/context/AppContext';

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <AppProvider>
        <StatusBar style="dark" />
        <Stack
          screenOptions={{
            headerShown: true,
            headerBackTitle: 'Back',
            headerTintColor: '#1d4ed8',
            headerStyle: { backgroundColor: '#f8fafc' },
            contentStyle: { backgroundColor: '#f8fafc' },
          }}
        >
          <Stack.Screen name="index" options={{ headerShown: false }} />
          <Stack.Screen name="login" options={{ title: 'Sign In', headerShown: false }} />
          <Stack.Screen name="centers" options={{ title: 'Select Center' }} />
          <Stack.Screen name="scan" options={{ title: 'Scan Barcode', headerBackVisible: false }} />
          <Stack.Screen name="product" options={{ title: 'Product' }} />
          <Stack.Screen name="quantity" options={{ title: 'Quantity' }} />
          <Stack.Screen name="summary" options={{ title: 'Session Summary' }} />
        </Stack>
      </AppProvider>
    </SafeAreaProvider>
  );
}
