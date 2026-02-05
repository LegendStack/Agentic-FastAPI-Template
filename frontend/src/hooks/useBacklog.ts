import { useState, useCallback, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import api from '../api/client';
import { useProjectContext } from './useProjectContext';

export interface UserStory {
    id: string;
    title: string;
    description: string;
    acceptance_criteria: any[];
    edge_cases: string[];
    technical_notes: string[];
    dependencies: string[];
    estimated_complexity: string | null;
    tags: string[];
}

export const useBacklog = (initialThreadId?: string) => {
    const [stories, setStories] = useState<UserStory[]>([]);
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

    // Unified Chat / Refinement Mutation
    const chatMutation = useMutation({
        mutationFn: async ({ message, localStories }: { message: string, localStories?: UserStory[] }) => {
            // For new chats, we use a placeholder or let the backend generate it.
            // But since our API expects a thread_id in the path, we can pass 'new' 
            // and have the backend handle redirect/creation, or we can use a temporary ID 
            // that gets replaced by the authoritative one from the response.
            //
            // BETTER APPROACH for this API: Use 'new' or a distinct indicator if API supports it.
            // However, looking at backlog.py, it expects a thread_id path param.
            // Let's generate a temporary client-side ID to start, but IMMEDIATELY replace it 
            // with the one returned by the server if they differ (or just trust the server response).

            // Actually, the user wants to AVOID client-generated IDs like "thread-xxxx".
            // Let's use 'new' as the thread ID for the initial request if supported, 
            // OR let's just make the initial request to /decompose (which returns a thread_id)
            // instead of /chat/{thread_id} for the first message?

            // Looking at existing API:
            // POST /backlog/decompose -> Body: { epic_description } -> Returns { thread_id, ... }
            // POST /backlog/chat/{thread_id} -> Body: { message }

            let activeThreadId = currentThreadId;
            let response;

            try {
                if (!activeThreadId) {
                    // FIRST MESSAGE: Use the /decompose endpoint which generates the ID
                    console.log(`[BacklogHook] Starting new decomposition via /decompose`);
                    response = await api.post(`/backlog/decompose`, {
                        epic_description: message,
                        output_format: 'json'
                    }, {
                        params: { project_key: selectedProject }
                    });
                } else {
                    // SUBSEQUENT MESSAGES: Use /chat/{thread_id}
                    console.log(`[BacklogHook] Calling /chat/${activeThreadId}`);
                    response = await api.post(`/backlog/chat/${activeThreadId}`, {
                        message,
                        stories: localStories,
                        output_format: 'json',
                    }, {
                        params: { project_key: selectedProject }
                    });
                }

                console.log(`[BacklogHook] API Success!`, response.data);

                // ALWAYS update the thread ID from the backend response
                if (response.data.thread_id) {
                    setCurrentThreadId(response.data.thread_id);
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
        try {
            const response = await api.get(`/backlog/stories/${threadId}`);
            if (response.data.stories) {
                setStories(response.data.stories);
            }
            if (response.data.recommendations) {
                setRecommendations(response.data.recommendations);
            }
            // Auto-select project from metadata (Feature A)
            if (response.data.metadata?.project_key) {
                console.log(`[BacklogHook] Auto-selecting project: ${response.data.metadata.project_key}`);
                // Since this hook is often called from App.tsx or similar, 
                // we rely on the project context to be available.
            }
            return response.data;
        } catch (err) {
            console.error('Failed to load thread:', err);
            throw err;
        }
    }, []);

    const updateStoryLocally = useCallback((updatedStory: UserStory) => {
        setStories(prev => prev.map(s => s.id === updatedStory.id ? updatedStory : s));
    }, []);

    const reset = useCallback(() => {
        setStories([]);
        setRecommendations([]);
        setCurrentThreadId(undefined);
    }, []);

    return {
        stories,
        setStories,
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

