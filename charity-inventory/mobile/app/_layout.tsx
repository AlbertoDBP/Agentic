import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { AppProvider } from '../src/context/AppContext';

export default function RootLayout() {
  return (
    <AppProvider>
      <StatusBar style="dark" />
      <Stack screenOptions={{ headerShown: true, headerBackTitle: 'Back' }}>
        <Stack.Screen name="index" options={{ headerShown: false }} />
        <Stack.Screen name="login" options={{ title: 'Login' }} />
        <Stack.Screen name="centers" options={{ title: 'Select Center' }} />
        <Stack.Screen name="scan" options={{ title: 'Scan Barcode' }} />
        <Stack.Screen name="product" options={{ title: 'Product' }} />
        <Stack.Screen name="quantity" options={{ title: 'Quantity' }} />
        <Stack.Screen name="summary" options={{ title: 'Session Summary' }} />
      </Stack>
    </AppProvider>
  );
}
