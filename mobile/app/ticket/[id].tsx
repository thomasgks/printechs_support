import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import {
	ActivityIndicator,
	KeyboardAvoidingView,
	Platform,
	RefreshControl,
	ScrollView,
	StyleSheet,
	Text,
	TextInput,
	Pressable,
	View,
} from 'react-native';

import {
	addPortalTicketComment,
	getPortalBootstrap,
	getPortalTicket,
	getPortalTicketComments,
	type TicketComment,
} from '@/lib/portal';
import { palette } from '@/constants/palette';

function stripHtml(html: string): string {
	return html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
}

function getConversationRole(
	viewerIsInternalUser: boolean,
	isMe: boolean,
	isInternalComment: boolean,
): 'customer' | 'technician' {
	if (!viewerIsInternalUser) {
		return isMe ? 'customer' : 'technician';
	}
	if (isInternalComment) {
		return 'technician';
	}
	return isMe ? 'technician' : 'customer';
}

export default function TicketDetailScreen() {
	const { id } = useLocalSearchParams<{ id: string }>();
	const router = useRouter();
	const qc = useQueryClient();
	const ticketName = decodeURIComponent(id ?? '');

	const [reply, setReply] = useState('');

	const ticketQ = useQuery({
		queryKey: ['ticket', ticketName],
		queryFn: () => getPortalTicket(ticketName),
		enabled: !!ticketName,
	});

	const commentsQ = useQuery({
		queryKey: ['ticket-comments', ticketName],
		queryFn: () => getPortalTicketComments(ticketName),
		enabled: !!ticketName,
	});

	const bootstrapQ = useQuery({
		queryKey: ['portal-bootstrap'],
		queryFn: () => getPortalBootstrap(),
	});

	const send = useMutation({
		mutationFn: () => addPortalTicketComment(ticketName, `<p>${reply.replace(/</g, '')}</p>`, false),
		onSuccess: () => {
			setReply('');
			void qc.invalidateQueries({ queryKey: ['ticket-comments', ticketName] });
		},
	});

	if (!ticketName) {
		return (
			<View style={styles.center}>
				<Text style={styles.err}>Invalid ticket</Text>
			</View>
		);
	}

	const doc = ticketQ.data;

	return (
		<KeyboardAvoidingView style={styles.root} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
			<ScrollView
				contentContainerStyle={styles.content}
				refreshControl={
					<RefreshControl
						refreshing={ticketQ.isFetching || commentsQ.isFetching}
						onRefresh={() => {
							void ticketQ.refetch();
							void commentsQ.refetch();
						}}
						tintColor={palette.accent}
					/>
				}>
				{ticketQ.isLoading ? (
					<ActivityIndicator color={palette.accent} style={{ marginTop: 24 }} />
				) : ticketQ.isError ? (
					<Text style={styles.err}>{ticketQ.error instanceof Error ? ticketQ.error.message : 'Error'}</Text>
				) : doc ? (
					<>
						<Text style={styles.title}>{String(doc.subject ?? '')}</Text>
						<Text style={styles.meta}>
							{String(doc.name)} · {String(doc.status ?? '')} · {String(doc.priority ?? '')}
						</Text>
						{doc.description ? (
							<Text style={styles.body}>{stripHtml(String(doc.description))}</Text>
						) : null}
					</>
				) : null}

				<Text style={styles.section}>Conversation</Text>
				{(commentsQ.data ?? []).map((c: TicketComment) => {
					const boot = bootstrapQ.data;
					const ready = bootstrapQ.isSuccess && boot != null;
					const loggedIn = boot && 'logged_in' in boot && boot.logged_in;
					const user = loggedIn && 'user' in boot ? boot.user : '';
					const viewerInternal = Boolean(loggedIn && 'internal' in boot && boot.internal);
					const isMe = Boolean(user && c.comment_by === user);
					const internalComment = Boolean(
						c.internal_only || String(c.comment_type ?? '') === 'Internal Note',
					);
					const lane = ready ? getConversationRole(viewerInternal, isMe, internalComment) : null;
					const isCustomerLane = lane === 'customer';
					const author = String(c.author_name || c.comment_by || 'User');
					const roleTitle = lane === null ? null : isCustomerLane ? 'Customer' : 'Technician';
					return (
						<View
							key={String(c.name ?? c.creation)}
							style={[
								styles.bubbleRow,
								lane == null ? styles.bubbleRowLeft : isCustomerLane ? styles.bubbleRowLeft : styles.bubbleRowRight,
							]}>
							<View
								style={[
									styles.bubble,
									lane == null
										? styles.bubbleNeutral
										: isCustomerLane
											? styles.bubbleCustomer
											: styles.bubbleTechnician,
									internalComment && lane != null && styles.bubbleInternal,
								]}>
								{roleTitle ? <Text style={styles.roleTitle}>{roleTitle}</Text> : null}
								{internalComment ? (
									<Text style={styles.internalBadge}>Internal — team only</Text>
								) : null}
								<Text style={styles.authorName}>{author}</Text>
								<Text style={styles.bubbleText}>{stripHtml(String(c.content ?? ''))}</Text>
								<Text style={styles.bubbleMeta}>
									{String(c.comment_on ?? c.creation ?? '')} · {String(c.comment_type ?? 'Message')}
								</Text>
							</View>
						</View>
					);
				})}

				<TextInput
					style={styles.input}
					placeholder="Write a message…"
					placeholderTextColor={palette.textMuted}
					multiline
					value={reply}
					onChangeText={setReply}
				/>
				<Pressable
					style={[styles.btn, send.isPending && { opacity: 0.6 }]}
					disabled={send.isPending || !reply.trim()}
					onPress={() => send.mutate()}>
					<Text style={styles.btnTxt}>Send</Text>
				</Pressable>
				<Pressable style={styles.back} onPress={() => router.back()}>
					<Text style={styles.backTxt}>← Back</Text>
				</Pressable>
			</ScrollView>
		</KeyboardAvoidingView>
	);
}

const styles = StyleSheet.create({
	root: { flex: 1, backgroundColor: palette.bg },
	content: { padding: 16, paddingBottom: 40 },
	center: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: palette.bg },
	title: { fontSize: 22, fontWeight: '800', color: palette.text },
	meta: { fontSize: 13, color: palette.textMuted, marginTop: 8, marginBottom: 16 },
	body: { fontSize: 15, lineHeight: 22, color: palette.text },
	section: {
		fontSize: 12,
		fontWeight: '800',
		color: palette.accent,
		marginTop: 20,
		marginBottom: 10,
		letterSpacing: 1,
	},
	bubbleRow: {
		width: '100%',
		marginBottom: 10,
		flexDirection: 'row',
	},
	bubbleRowLeft: { justifyContent: 'flex-start' },
	bubbleRowRight: { justifyContent: 'flex-end' },
	bubble: {
		maxWidth: '92%',
		borderRadius: 14,
		padding: 12,
		borderWidth: 1,
	},
	bubbleCustomer: {
		backgroundColor: '#F1F1F1',
		borderColor: 'rgba(148, 163, 184, 0.45)',
	},
	bubbleTechnician: {
		backgroundColor: '#E7F0FF',
		borderColor: 'rgba(125, 211, 252, 0.65)',
	},
	bubbleInternal: {
		backgroundColor: '#fffbeb',
		borderColor: 'rgba(245, 158, 11, 0.55)',
	},
	bubbleNeutral: {
		backgroundColor: palette.bgCard,
		borderColor: palette.border,
		maxWidth: '100%',
	},
	roleTitle: {
		fontSize: 10,
		fontWeight: '800',
		color: palette.textMuted,
		letterSpacing: 0.8,
		textTransform: 'uppercase',
	},
	internalBadge: {
		marginTop: 4,
		fontSize: 10,
		fontWeight: '700',
		color: '#92400e',
	},
	authorName: {
		marginTop: 4,
		fontSize: 14,
		fontWeight: '700',
		color: palette.text,
	},
	bubbleMeta: { fontSize: 11, color: palette.textMuted, marginTop: 8 },
	bubbleText: { fontSize: 14, color: palette.text, lineHeight: 20, marginTop: 6 },
	input: {
		minHeight: 88,
		backgroundColor: palette.bgCard,
		borderRadius: 12,
		padding: 12,
		borderWidth: 1,
		borderColor: palette.border,
		color: palette.text,
		marginTop: 12,
		textAlignVertical: 'top',
	},
	btn: {
		backgroundColor: palette.accent,
		borderRadius: 12,
		padding: 14,
		alignItems: 'center',
		marginTop: 10,
	},
	btnTxt: { color: '#0c1222', fontWeight: '800' },
	back: { marginTop: 20 },
	backTxt: { color: palette.textMuted, fontWeight: '600' },
	err: { color: palette.danger },
});
