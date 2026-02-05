import { useState, useCallback, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import api from '../api/client';
import { useProjectContext } from './useProjectContext';

export interface AcceptanceCriteria {
    description: string;
    given?: string;
    when?: string;
    then?: string;
    is_edge_case?: boolean;
}

export interface UserStory {
    id: string;
    title: string;
    description: string;
    acceptance_criteria: AcceptanceCriteria[];
    edge_cases: string[];
    technical_notes: string[];
    dependencies: string[];
    estimated_complexity: string | null;
    business_value_score?: number;
    effort_score?: number;
    tags: string[];
}

export interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: number;
}

export interface ArtifactVersion {
    checkpoint_id: string;
    timestamp: number | null;
    summary: string;
    story_count: number;
    is_refinement: boolean;
}

export const useBacklog = (initialThreadId?: string) => {
    const [stories, setStories] = useState<UserStory[]>([]);
    const [messages, setMessages] = useState<Message[]>([]);
    const [versions, setVersions] = useState<ArtifactVersion[]>([]);
    const [activeVersionId, setActiveVersionId] = useState<string | null>(null);
    const [recommendations, setRecommendations] = useState<string[]>([]);
    const [currentThreadId, setCurrentThreadId] = useState<string | undefined>(initialThreadId);
    const { selectedProject } = useProjectContext();

    // Load thread from URL on mount
    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const urlThreadId = params.get('thread');
        if (urlThreadId && !currentThreadId) {
            loadThread(urlThreadId);
        }
    }, []);

    // Sync URL when thread changes
    useEffect(() => {
        if (currentThreadId) {
            const url = new URL(window.location.href);
            url.searchParams.set('thread', currentThreadId);
            window.history.pushState({}, '', url);
        } else {
            const url = new URL(window.location.href);
            url.searchParams.delete('thread');
            window.history.pushState({}, '', url);
        }
    }, [currentThreadId]);

    const fetchVersions = useCallback(async (threadId: string) => {
        try {
            const response = await api.get(`/backlog/history/${threadId}`);
            setVersions(response.data.versions);
        } catch (err) {
            console.error('Failed to fetch versions:', err);
        }
    }, []);

    // Load a specific version/checkpoint
    const loadVersion = useCallback(async (checkpointId: string) => {
        if (!currentThreadId) return;
        setActiveVersionId(checkpointId);
        try {
            const response = await api.get(`/backlog/stories/${currentThreadId}`, {
                params: { checkpoint_id: checkpointId }
            });
            if (response.data.stories) {
                setStories(response.data.stories);
            }
        } catch (err) {
            console.error('Failed to load version:', err);
        }
    }, [currentThreadId]);

    // Unified Chat / Refinement Mutation
    const chatMutation = useMutation({
        mutationFn: async ({ message, localStories }: { message: string, localStories?: UserStory[] }) => {
            // Optimistically add user message
            const userMsg: Message = {
                id: `msg-${Date.now()}`,
                role: 'user',
                content: message,
                timestamp: Date.now()
            };
            setMessages(prev => [...prev, userMsg]);

            let activeThreadId = currentThreadId;
            let response;

            try {
                if (!activeThreadId) {
                    // FIRST MESSAGE: Use the /decompose endpoint which generates the ID
                    response = await api.post(`/backlog/decompose`, {
                        epic_description: message,
                        output_format: 'json'
                    }, {
                        params: { project_key: selectedProject }
                    });
                } else {
                    // SUBSEQUENT MESSAGES: Use /chat/{thread_id}
                    response = await api.post(`/backlog/chat/${activeThreadId}`, {
                        message,
                        stories: localStories,
                        output_format: 'json',
                    }, {
                        params: { project_key: selectedProject }
                    });
                }

                // Add assistant response summary
                const assistantMsg: Message = {
                    id: `msg-${Date.now() + 1}`,
                    role: 'assistant',
                    content: response.data.summary || (activeThreadId ? "Refinement complete." : "Decomposition complete."),
                    timestamp: Date.now()
                };
                setMessages(prev => [...prev, assistantMsg]);

                // ALWAYS update the thread ID from the backend response
                if (response.data.thread_id) {
                    setCurrentThreadId(response.data.thread_id);
                    // Refresh versions after a successful chat
                    fetchVersions(response.data.thread_id);
                    setActiveVersionId(null); // Reset to "Latest"
                }

                return response.data;
            } catch (err: any) {
                console.error(`[BacklogHook] API Error:`, err.response?.data || err.message);
                throw err;
            }
        },
        onSuccess: (data) => {
            if (data.stories) {
                setStories(data.stories);
            }
            if (data.recommendations) {
                setRecommendations(data.recommendations);
            }
        },
    });

    // Load an existing thread
    const loadThread = useCallback(async (threadId: string) => {
        setCurrentThreadId(threadId);
        fetchVersions(threadId);
        try {
            const response = await api.get(`/backlog/stories/${threadId}`);
            if (response.data.stories) {
                setStories(response.data.stories);
            }
            if (response.data.recommendations) {
                setRecommendations(response.data.recommendations);
            }

            // Use messages from backend if provided (Phase 23 fix)
            if (response.data.messages && response.data.messages.length > 0) {
                setMessages(response.data.messages);
            } else if (response.data.metadata?.epic_description) {
                // Fallback for older threads or if messages missing
                const epicMsg: Message = {
                    id: 'msg-initial-epic',
                    role: 'user',
                    content: response.data.metadata.epic_description,
                    timestamp: 0
                };
                const assistMsg: Message = {
                    id: 'msg-initial-assist',
                    role: 'assistant',
                    content: response.data.summary || "Previous decomposition loaded.",
                    timestamp: 1
                };
                setMessages([epicMsg, assistMsg]);
            }

            // Auto-select project from metadata (Feature A)
            if (response.data.metadata?.project_key) {
                console.log(`[BacklogHook] Auto-selecting project: ${response.data.metadata.project_key}`);
            }
            return response.data;
        } catch (err) {
            console.error('Failed to load thread:', err);
            throw err;
        }
    }, [fetchVersions]);

    const updateStoryLocally = useCallback((updatedStory: UserStory) => {
        setStories(prev => prev.map(s => s.id === updatedStory.id ? updatedStory : s));
    }, []);

    const reset = useCallback(() => {
        setStories([]);
        setMessages([]);
        setVersions([]);
        setActiveVersionId(null);
        setRecommendations([]);
        setCurrentThreadId(undefined);
    }, []);

    return {
        stories,
        setStories,
        messages,
        versions,
        activeVersionId,
        loadVersion,
        recommendations,
        currentThreadId,
        loadThread,
        updateStoryLocally,
        reset,
        isProcessing: chatMutation.isPending,
        sendMessage: chatMutation.mutate,
        error: chatMutation.error,
    };
};

