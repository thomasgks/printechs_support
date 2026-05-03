import NetInfo from '@react-native-community/netinfo';
import { useEffect, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { palette } from '@/constants/palette';

export function OfflineBanner() {
	const [offline, setOffline] = useState(false);

	useEffect(() => {
		const sub = NetInfo.addEventListener((s) => {
			setOffline(s.isConnected === false);
		});
		return () => sub();
	}, []);

	if (!offline) return null;

	return (
		<View style={styles.bar} accessibilityRole="alert">
			<Text style={styles.text}>Offline — showing cached data where available</Text>
		</View>
	);
}

const styles = StyleSheet.create({
	bar: {
		backgroundColor: palette.warning,
		paddingVertical: 8,
		paddingHorizontal: 16,
	},
	text: {
		color: '#1a1a1a',
		fontSize: 13,
		fontWeight: '600',
		textAlign: 'center',
	},
});
