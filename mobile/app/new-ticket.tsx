import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { useMemo, useState } from 'react';
import {
	ActivityIndicator,
	KeyboardAvoidingView,
	Platform,
	Pressable,
	ScrollView,
	StyleSheet,
	Text,
	TextInput,
	View,
} from 'react-native';

import { useAuth } from '@/context/AuthContext';
import {
	createPortalTicket,
	getPortalTicketCustomers,
	getPortalTicketTypes,
} from '@/lib/portal';
import { palette } from '@/constants/palette';

const PRIORITIES = ['Low', 'Medium', 'High', 'Critical'] as const;

export default function NewTicketScreen() {
	const router = useRouter();
	const qc = useQueryClient();
	const { bootstrap } = useAuth();
	const internal = bootstrap?.logged_in && bootstrap.internal;
	const customers = bootstrap?.logged_in ? bootstrap.customers : [];

	const [customer, setCustomer] = useState('');
	const [ticketType, setTicketType] = useState('');
	const [subject, setSubject] = useState('');
	const [description, setDescription] = useState('');
	const [priority, setPriority] = useState<string>('Medium');

	const customerForTypes = useMemo(() => {
		if (internal) return customer.trim() || undefined;
		if (customers.length === 1) return customers[0];
		return customer.trim() || undefined;
	}, [internal, customers, customer]);

	const portalCustomerRequired = !internal && customers.length > 1;

	const typesQ = useQuery({
		queryKey: ['ticket-types', customerForTypes],
		queryFn: () => getPortalTicketTypes(customerForTypes),
	});

	const custQ = useQuery({
		queryKey: ['portal-customers'],
		queryFn: getPortalTicketCustomers,
		enabled: internal,
	});

	const create = useMutation({
		mutationFn: () =>
			createPortalTicket({
				subject: subject.trim(),
				description: description.trim() || undefined,
				priority,
				customer: internal
					? customer.trim() || undefined
					: portalCustomerRequired
						? customer.trim() || undefined
						: customers[0],
				ticket_type: ticketType.trim(),
			}),
		onSuccess: (res) => {
			void qc.invalidateQueries({ queryKey: ['portal-tickets'] });
			router.replace(`/ticket/${encodeURIComponent(res.name)}`);
		},
	});

	const types = typesQ.data?.types ?? [];

	return (
		<KeyboardAvoidingView style={styles.root} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
			<ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
				<Text style={styles.label}>Subject *</Text>
				<TextInput
					style={styles.input}
					placeholder="Short summary"
					placeholderTextColor={palette.textMuted}
					value={subject}
					onChangeText={setSubject}
				/>

				{internal ? (
					<>
						<Text style={styles.label}>Customer *</Text>
						{custQ.isLoading ? (
							<ActivityIndicator color={palette.accent} />
						) : (
							<View style={styles.chips}>
								{(custQ.data?.customers ?? []).map((c) => (
									<Pressable
										key={c.name}
										onPress={() => setCustomer(c.name)}
										style={[styles.chip, customer === c.name && styles.chipOn]}>
										<Text style={[styles.chipTxt, customer === c.name && styles.chipTxtOn]}>
											{c.customer_name}
										</Text>
									</Pressable>
								))}
							</View>
						)}
					</>
				) : portalCustomerRequired ? (
					<>
						<Text style={styles.label}>Customer *</Text>
						<View style={styles.chips}>
							{customers.map((c: string) => (
								<Pressable
									key={c}
									onPress={() => setCustomer(c)}
									style={[styles.chip, customer === c && styles.chipOn]}>
									<Text style={[styles.chipTxt, customer === c && styles.chipTxtOn]}>{c}</Text>
								</Pressable>
							))}
						</View>
					</>
				) : null}

				<Text style={styles.label}>Ticket type *</Text>
				{typesQ.isLoading ? (
					<ActivityIndicator color={palette.accent} />
				) : (
					<View style={styles.chips}>
						{types.map((t) => (
							<Pressable
								key={t.name}
								onPress={() => setTicketType(t.name)}
								style={[styles.chip, ticketType === t.name && styles.chipOn]}>
								<Text style={[styles.chipTxt, ticketType === t.name && styles.chipTxtOn]}>{t.label}</Text>
							</Pressable>
						))}
					</View>
				)}

				<Text style={styles.label}>Priority</Text>
				<View style={styles.chips}>
					{PRIORITIES.map((p) => (
						<Pressable
							key={p}
							onPress={() => setPriority(p)}
							style={[styles.chip, priority === p && styles.chipOn]}>
							<Text style={[styles.chipTxt, priority === p && styles.chipTxtOn]}>{p}</Text>
						</Pressable>
					))}
				</View>

				<Text style={styles.label}>Details</Text>
				<TextInput
					style={[styles.input, { minHeight: 120 }]}
					multiline
					placeholder="Describe the issue"
					placeholderTextColor={palette.textMuted}
					value={description}
					onChangeText={setDescription}
					textAlignVertical="top"
				/>

				{create.isError ? (
					<Text style={styles.err}>{create.error instanceof Error ? create.error.message : 'Failed'}</Text>
				) : null}

				<Pressable
					style={[styles.primary, create.isPending && { opacity: 0.7 }]}
					disabled={
						create.isPending ||
						!subject.trim() ||
						!ticketType.trim() ||
						(internal && !customer.trim()) ||
						(portalCustomerRequired && !customer.trim())
					}
					onPress={() => create.mutate()}>
					<Text style={styles.primaryTxt}>{create.isPending ? 'Creating…' : 'Create ticket'}</Text>
				</Pressable>

				<Pressable style={styles.cancel} onPress={() => router.back()}>
					<Text style={styles.cancelTxt}>Cancel</Text>
				</Pressable>
			</ScrollView>
		</KeyboardAvoidingView>
	);
}

const styles = StyleSheet.create({
	root: { flex: 1, backgroundColor: palette.bg },
	content: { padding: 16, paddingBottom: 40 },
	label: {
		fontSize: 12,
		fontWeight: '700',
		color: palette.textMuted,
		marginBottom: 8,
		textTransform: 'uppercase',
		letterSpacing: 0.5,
	},
	input: {
		backgroundColor: palette.bgCard,
		borderWidth: 1,
		borderColor: palette.border,
		borderRadius: 12,
		padding: 12,
		fontSize: 16,
		color: palette.text,
		marginBottom: 16,
	},
	chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 16 },
	chip: {
		paddingHorizontal: 12,
		paddingVertical: 8,
		borderRadius: 999,
		backgroundColor: palette.bgCard,
		borderWidth: 1,
		borderColor: palette.border,
	},
	chipOn: { borderColor: palette.accent, backgroundColor: palette.bgElevated },
	chipTxt: { color: palette.textMuted, fontSize: 13, fontWeight: '600' },
	chipTxtOn: { color: palette.accent },
	primary: {
		backgroundColor: palette.accent,
		borderRadius: 14,
		padding: 16,
		alignItems: 'center',
		marginTop: 8,
	},
	primaryTxt: { color: '#0c1222', fontWeight: '800', fontSize: 16 },
	cancel: { marginTop: 16, alignItems: 'center' },
	cancelTxt: { color: palette.textMuted, fontWeight: '600' },
	err: { color: palette.danger, marginBottom: 12 },
});
