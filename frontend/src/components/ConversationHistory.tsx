import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, Pencil, Trash2, Check, X } from 'lucide-react';
import { toast } from 'sonner';
import api from '../api/client';
import { useState } from 'react';

interface Conversation {
    id: number;
    thread_id: string;
    title: string | null;
    agent_name: string;
    status: string;
    metadata: {
        project_key?: string;
    } | null;
    created_at: string;
    updated_at: string | null;
}

interface GroupedConversations {
    [key: string]: Conversation[];
}

interface ConversationHistoryProps {
    onSelectThread: (threadId: string) => void;
    onNewConversation: () => void;
    currentThreadId?: string;
    isMinimized?: boolean;
}

const formatRelativeTime = (dateString: string): string => {
    // Force UTC if no timezone is present
    const normalizedDate = dateString.endsWith('Z') || dateString.includes('+')
        ? dateString
        : `${dateString}Z`;

    const date = new Date(normalizedDate);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();

    // Handle potential clock skew or future dates
    if (diffMs < 0) return 'Just now';

    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
};

const getGroupName = (dateString: string): string => {
    const date = new Date(dateString);
    const now = new Date();

    // Reset times to compare dates only
    const dDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    const dNow = new Date(now.getFullYear(), now.getMonth(), now.getDate());

    const diffDays = Math.floor((dNow.getTime() - dDate.getTime()) / 86400000);

    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return 'This Week';
    if (diffDays < 30) return 'This Month';
    return 'Older';
};

export const ConversationHistory = ({
    onSelectThread,
    onNewConversation,
    currentThreadId,
    isMinimized
}: ConversationHistoryProps) => {
    const queryClient = useQueryClient();
    const [editingThreadId, setEditingThreadId] = useState<string | null>(null);
    const [editTitle, setEditTitle] = useState('');

    const { data, isLoading } = useQuery({
        queryKey: ['conversations', 'backlog_assistant'],
        queryFn: async () => {
            const response = await api.get('/agents/conversations', {
                params: { agent_name: 'backlog_assistant', limit: 50 },
            });
            const conversations = response.data.conversations || [];

            return conversations.map((conv: any) => ({
                ...conv,
                metadata: typeof conv.metadata === 'string' ? JSON.parse(conv.metadata) : conv.metadata
            })) as Conversation[];
        },
        refetchInterval: 30000,
    });

    const renameMutation = useMutation({
        mutationFn: async ({ threadId, title }: { threadId: string, title: string }) => {
            await api.patch(`/agents/conversations/${threadId}`, { title });
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['conversations'] });
            setEditingThreadId(null);
        }
    });



    const deleteMutation = useMutation({
        mutationFn: async (threadId: string) => {
            console.log("Delete mutation started for thread:", threadId);
            await api.delete(`/agents/conversations/${threadId}`);
        },
        onSuccess: () => {
            console.log("Delete mutation success. Invalidating queries.");
            queryClient.invalidateQueries({ queryKey: ['conversations', 'backlog_assistant'] });
            toast.success('Conversation deleted');
        },
        onError: (err) => {
            console.error("Delete mutation error:", err);
            toast.error('Failed to delete conversation');
            console.error('Delete failed:', err);
        }
    });

    const handleStartEdit = (e: React.MouseEvent, conv: Conversation) => {
        e.stopPropagation();
        setEditingThreadId(conv.thread_id);
        setEditTitle(conv.title || 'Untitled Chat');
    };

    const handleSaveEdit = (e: React.MouseEvent, threadId: string) => {
        e.stopPropagation();
        if (editTitle.trim()) {
            renameMutation.mutate({ threadId, title: editTitle.trim() });
        } else {
            setEditingThreadId(null);
        }
    };

    const handleDelete = (e: React.MouseEvent, threadId: string) => {
        e.preventDefault();
        e.stopPropagation();
        console.log("Delete button clicked for thread:", threadId);
        // Optimistic delete with Undo - no confirmation dialog needed
        deleteMutation.mutate(threadId);
    };

    const groupedData = data?.reduce((acc: GroupedConversations, conv) => {
        const group = getGroupName(conv.updated_at || conv.created_at);
        if (!acc[group]) acc[group] = [];
        acc[group].push(conv);
        return acc;
    }, {});

    const groupOrder = ['Today', 'Yesterday', 'This Week', 'This Month', 'Older'];

    return (
        <div className="flex flex-col h-full">
            <div className="px-4 py-3 border-b border-border-primary">
                <button
                    onClick={onNewConversation}
                    title={isMinimized ? "New Chat" : undefined}
                    className={`w-full flex items-center justify-center gap-2 bg-accent-primary/10 hover:bg-accent-primary/20 border border-accent-primary/30 rounded-xl transition-all text-accent-primary font-semibold text-sm ${isMinimized ? 'p-2.5' : 'px-4 py-2.5'}`}
                >
                    <Plus className="w-4 h-4 flex-shrink-0" />
                    {!isMinimized && <span>New Chat</span>}
                </button>
            </div>

            <div className="flex-1 overflow-y-auto px-2 py-3 custom-scrollbar">
                {isMinimized ? null : (
                    isLoading ? (
                        <div className="px-4 py-8 text-center text-text-secondary text-sm">
                            Loading history...
                        </div>
                    ) : data && data.length > 0 ? (
                        <AnimatePresence>
                            {groupOrder.map(group => {
                                const conversations = groupedData?.[group];
                                if (!conversations || conversations.length === 0) return null;

                                return (
                                    <div key={group} className="mb-6 last:mb-2 text-center">
                                        {!isMinimized && (
                                            <h4 className="px-3 mb-2 text-[10px] font-bold text-text-tertiary uppercase tracking-widest text-left">
                                                {group}
                                            </h4>
                                        )}
                                        {conversations.map((conv) => (
                                            <motion.div
                                                key={conv.thread_id}
                                                initial={{ opacity: 0, x: -10 }}
                                                animate={{ opacity: 1, x: 0 }}
                                                exit={{ opacity: 0, x: -10 }}
                                                onClick={() => onSelectThread(conv.thread_id)}
                                                className={`w-full flex items-start rounded-lg transition-all text-left mb-1 group/item cursor-pointer ${currentThreadId === conv.thread_id
                                                    ? 'bg-accent-primary/10 shadow-sm'
                                                    : 'hover:bg-bg-tertiary'
                                                    } ${isMinimized ? 'p-2 justify-center' : 'px-3 py-2.5'}`}
                                            >
                                                {!isMinimized && (
                                                    <div className="flex-1 min-w-0">
                                                        <div className="flex items-center justify-between gap-2 overflow-hidden">
                                                            {editingThreadId === conv.thread_id ? (
                                                                <div className="flex-1 flex items-center gap-1 min-w-0" onClick={e => e.stopPropagation()}>
                                                                    <input
                                                                        autoFocus
                                                                        type="text"
                                                                        value={editTitle}
                                                                        onChange={e => setEditTitle(e.target.value)}
                                                                        onKeyDown={e => e.key === 'Enter' && handleSaveEdit(e as any, conv.thread_id)}
                                                                        className="flex-1 bg-bg-primary border border-accent-primary/50 rounded px-1.5 py-0.5 text-xs text-text-primary outline-none focus:border-accent-primary"
                                                                    />
                                                                    <button onClick={e => handleSaveEdit(e, conv.thread_id)} className="p-1 hover:text-accent-primary text-text-tertiary">
                                                                        <Check className="w-3 h-3" />
                                                                    </button>
                                                                    <button onClick={e => { e.stopPropagation(); setEditingThreadId(null); }} className="p-1 hover:text-red-400 text-text-tertiary">
                                                                        <X className="w-3 h-3" />
                                                                    </button>
                                                                </div>
                                                            ) : (
                                                                <>
                                                                    <div className="flex flex-col min-w-0 flex-1">
                                                                        <p className={`text-xs font-semibold truncate mb-1.5 ${currentThreadId === conv.thread_id
                                                                            ? 'text-accent-primary'
                                                                            : 'text-text-primary'
                                                                            }`}>
                                                                            {conv.title || 'Untitled Chat'}
                                                                        </p>
                                                                        <div className="flex items-center justify-between">
                                                                            <div className="flex items-center gap-2 min-w-0">
                                                                                {conv.metadata?.project_key && (
                                                                                    <span className="px-1.5 py-0.5 rounded-md bg-accent-primary/20 text-[9px] uppercase tracking-tighter text-accent-primary font-mono flex-shrink-0 font-bold">
                                                                                        {conv.metadata.project_key}
                                                                                    </span>
                                                                                )}
                                                                                <p className="text-[10px] text-text-secondary truncate">
                                                                                    {formatRelativeTime(conv.updated_at || conv.created_at)}
                                                                                </p>
                                                                            </div>
                                                                            <div className="flex items-center gap-1 opacity-0 group-hover/item:opacity-100 transition-opacity flex-shrink-0">
                                                                                <button
                                                                                    onClick={(e) => handleStartEdit(e, conv)}
                                                                                    className="p-1 hover:text-accent-primary text-text-tertiary transition-colors"
                                                                                >
                                                                                    <Pencil className="w-3 h-3" />
                                                                                </button>
                                                                                <button
                                                                                    onClick={(e) => handleDelete(e, conv.thread_id)}
                                                                                    className="p-1 hover:text-red-400 text-text-tertiary transition-colors"
                                                                                >
                                                                                    <Trash2 className="w-3 h-3" />
                                                                                </button>
                                                                            </div>
                                                                        </div>
                                                                    </div>
                                                                </>
                                                            )}
                                                        </div>
                                                    </div>
                                                )}
                                                {isMinimized && conv.metadata?.project_key && (
                                                    <span className="px-1.5 py-0.5 rounded-md bg-accent-primary/20 text-[9px] uppercase tracking-tighter text-accent-primary font-mono flex-shrink-0 font-bold">
                                                        {conv.metadata.project_key[0]}
                                                    </span>
                                                )}
                                            </motion.div>
                                        ))}
                                    </div>
                                );
                            })}
                        </AnimatePresence>
                    ) : (
                        <div className="px-4 py-8 text-center text-text-secondary text-sm">
                            No recent chats found.
                        </div>
                    )
                )}
            </div>
        </div>
    );
};
