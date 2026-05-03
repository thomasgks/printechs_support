import FontAwesome from '@expo/vector-icons/FontAwesome';
import { Redirect, Tabs } from 'expo-router';
import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { useAuth } from '@/context/AuthContext';
import { palette } from '@/constants/palette';

function TabIcon({ name, color }: { name: React.ComponentProps<typeof FontAwesome>['name']; color: string }) {
	return <FontAwesome size={22} name={name} color={color} />;
}

export default function TabLayout() {
	const { ready, auth, bootstrap } = useAuth();

	if (!ready) {
		return (
			<View style={styles.center}>
				<ActivityIndicator color={palette.accent} size="large" />
			</View>
		);
	}

	if (!auth || !bootstrap?.logged_in) {
		return <Redirect href="/login" />;
	}

	return (
		<Tabs
			screenOptions={{
				tabBarActiveTintColor: palette.accent,
				tabBarInactiveTintColor: palette.textMuted,
				tabBarStyle: {
					backgroundColor: palette.bgCard,
					borderTopColor: palette.border,
				},
				headerStyle: { backgroundColor: palette.bg },
				headerTintColor: palette.text,
				headerShadowVisible: false,
			}}>
			<Tabs.Screen
				name="index"
				options={{
					title: 'Home',
					tabBarIcon: ({ color }) => <TabIcon name="home" color={color} />,
				}}
			/>
			<Tabs.Screen
				name="tickets"
				options={{
					title: 'Tickets',
					tabBarIcon: ({ color }) => <TabIcon name="ticket" color={color} />,
				}}
			/>
			<Tabs.Screen
				name="tasks"
				options={{
					title: 'Tasks',
					tabBarIcon: ({ color }) => <TabIcon name="tasks" color={color} />,
				}}
			/>
			<Tabs.Screen
				name="agenda"
				options={{
					title: 'Agenda',
					tabBarIcon: ({ color }) => <TabIcon name="calendar" color={color} />,
				}}
			/>
			<Tabs.Screen
				name="more"
				options={{
					title: 'More',
					tabBarIcon: ({ color }) => <TabIcon name="ellipsis-h" color={color} />,
				}}
			/>
		</Tabs>
	);
}

const styles = StyleSheet.create({
	center: {
		flex: 1,
		justifyContent: 'center',
		alignItems: 'center',
		backgroundColor: palette.bg,
	},
});
