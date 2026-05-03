import FontAwesome from '@expo/vector-icons/FontAwesome';
import { DarkTheme, ThemeProvider } from '@react-navigation/native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useFonts } from 'expo-font';
import { Stack } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import { View } from 'react-native';
import 'react-native-reanimated';

import { OfflineBanner } from '@/components/OfflineBanner';
import { AuthProvider } from '@/context/AuthContext';
import { palette } from '@/constants/palette';

export { ErrorBoundary } from 'expo-router';

export const unstable_settings = {
	initialRouteName: 'index',
};

SplashScreen.preventAutoHideAsync();

const queryClient = new QueryClient({
	defaultOptions: {
		queries: {
			retry: 1,
			staleTime: 30_000,
		},
	},
});

const NavTheme = {
	...DarkTheme,
	colors: {
		...DarkTheme.colors,
		primary: palette.accent,
		background: palette.bg,
		card: palette.bgCard,
		text: palette.text,
		border: palette.border,
		notification: palette.accent,
	},
};

export default function RootLayout() {
	const [loaded, error] = useFonts({
		SpaceMono: require('../assets/fonts/SpaceMono-Regular.ttf'),
		...FontAwesome.font,
	});

	useEffect(() => {
		if (error) throw error;
	}, [error]);

	useEffect(() => {
		if (loaded) SplashScreen.hideAsync();
	}, [loaded]);

	if (!loaded) return null;

	return (
		<QueryClientProvider client={queryClient}>
			<AuthProvider>
				<ThemeProvider value={NavTheme}>
					<View style={{ flex: 1, backgroundColor: palette.bg }}>
						<OfflineBanner />
						<StatusBar style="light" />
						<Stack>
							<Stack.Screen name="index" options={{ headerShown: false }} />
							<Stack.Screen name="login" options={{ headerShown: false }} />
							<Stack.Screen name="(tabs)" options={{ headerShown: false }} />
							<Stack.Screen name="ticket/[id]" options={{ title: 'Ticket', headerTintColor: palette.text }} />
							<Stack.Screen name="task/[id]" options={{ title: 'Task', headerTintColor: palette.text }} />
							<Stack.Screen name="new-ticket" options={{ title: 'New ticket', presentation: 'modal', headerTintColor: palette.text }} />
						</Stack>
					</View>
				</ThemeProvider>
			</AuthProvider>
		</QueryClientProvider>
	);
}
