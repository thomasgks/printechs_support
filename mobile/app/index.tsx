import { Redirect } from 'expo-router';
import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { useAuth } from '@/context/AuthContext';
import { palette } from '@/constants/palette';

export default function Index() {
	const { ready, auth, bootstrap } = useAuth();

	if (!ready) {
		return (
			<View style={styles.center}>
				<ActivityIndicator size="large" color={palette.accent} />
			</View>
		);
	}

	if (!auth || !bootstrap || !bootstrap.logged_in) {
		return <Redirect href="/login" />;
	}

	return <Redirect href="/(tabs)" />;
}

const styles = StyleSheet.create({
	center: {
		flex: 1,
		justifyContent: 'center',
		alignItems: 'center',
		backgroundColor: palette.bg,
	},
});
