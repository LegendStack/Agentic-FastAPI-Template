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
    is_duplicate?: boolean;
    duplicate_reason?: string;
    jira_key?: string;
    jira_url?: string;
    test_scenarios?: string[];
}

export interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: number;
    input_tokens?: number;
    output_tokens?: number;
}

export interface ArtifactVersion {
    checkpoint_id: string;
    timestamp: number | null;
    summary: string;
    story_count: number;
    is_refinement: boolean;
}

export interface Epic {
    title: string;
    description: string;
    key?: string;
    summary?: string;
}

export interface DecomposeResponse {
    thread_id: string;
    stories: UserStory[];
    summary: string | null;
    recommendations?: string[];
    usage?: any;
    jira_base_url?: string;
    messages?: any[];
    is_locked?: boolean;
    metadata?: any;
    response?: {
        epic: Epic;
    };
}

export const useBacklog = (initialThreadId?: string) => {
    const [stories, setStories] = useState<UserStory[]>([]);
    const [messages, setMessages] = useState<Message[]>([]);
    const [versions, setVersions] = useState<ArtifactVersion[]>([]);
    const [activeVersionId, setActiveVersionId] = useState<string | null>(null);
    const [jiraBaseUrl, setJiraBaseUrl] = useState<string | null>(null);
    const [recommendations, setRecommendations] = useState<string[]>([]);
    const [currentEpic, setCurrentEpic] = useState<Epic | null>(null);
    const [currentThreadId, setCurrentThreadId] = useState<string | undefined>(initialThreadId);
    const [isLocked, setIsLocked] = useState<boolean>(false);
    const { selectedProject, selectedEpic } = useProjectContext();

    // Load thread from URL on mount
    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const urlThreadId = params.get('thread');
        if (urlThreadId && !currentThreadId) {
            loadThread(urlThreadId);
        }
    }, [currentThreadId]);

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
                    response = await api.post<DecomposeResponse>('/backlog/decompose', {
                        epic_description: message,
                        output_format: 'json',
                        parent_epic_id: selectedEpic?.key
                    }, {
                        params: { project_key: selectedProject }
                    });
                } else {
                    // SUBSEQUENT MESSAGES: Use /chat/{thread_id}
                    response = await api.post<DecomposeResponse>(`/backlog/chat/${activeThreadId}`, {
                        message,
                        stories: localStories,
                        output_format: 'json',
                        parent_epic_id: selectedEpic?.key
                    }, {
                        params: { project_key: selectedProject }
                    });
                }

                // Add assistant response summary
                const assistantMsg: Message = {
                    id: `msg-${Date.now() + 1}`,
                    role: 'assistant',
                    content: response.data.summary || (activeThreadId ? "Refinement complete." : "Decomposition complete."),
                    timestamp: Date.now(),
                    input_tokens: response.data.usage?.input_tokens,
                    output_tokens: response.data.usage?.output_tokens
                };
                setMessages(prev => [...prev, assistantMsg]);

                // ALWAYS update the thread ID from the backend response
                if (response.data.thread_id) {
                    setCurrentThreadId(response.data.thread_id);
                    // Refresh versions after a successful chat
                    fetchVersions(response.data.thread_id);
                    setActiveVersionId(null); // Reset to "Latest"
                }

                if (response.data.jira_base_url) {
                    setJiraBaseUrl(response.data.jira_base_url);
                }

                return response.data;
            } catch (err: any) {
                console.error(`[BacklogHook] API Error: `, err.response?.data || err.message);
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
            if (data.response?.epic) {
                setCurrentEpic(data.response.epic);
            }
            if (data.is_locked !== undefined) {
                setIsLocked(data.is_locked);
            }
        },
    });

    // Load an existing thread
    const loadThread = useCallback(async (threadId: string) => {
        setCurrentThreadId(threadId);
        fetchVersions(threadId);
        try {
            const response = await api.get<DecomposeResponse>(`/backlog/stories/${threadId}`);
            if (response.data.stories) {
                setStories(response.data.stories);
            }
            if (response.data.recommendations) {
                setRecommendations(response.data.recommendations);
            }
            if (response.data.jira_base_url) {
                setJiraBaseUrl(response.data.jira_base_url);
            }
            if (response.data.response?.epic) {
                setCurrentEpic(response.data.response.epic);
            }
            if (response.data.is_locked !== undefined) {
                setIsLocked(response.data.is_locked);
            }

            // Use messages from backend if provided (Phase 23 fix)
            if (response.data.messages && (response.data.messages as any).length > 0) {
                setMessages(response.data.messages as any);
            } else if ((response.data as any).metadata?.epic_description) {
                // Fallback for older threads or if messages missing
                const epicMsg: Message = {
                    id: 'msg-initial-epic',
                    role: 'user',
                    content: (response.data as any).metadata.epic_description,
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
            if ((response.data as any).metadata?.project_key) {
                console.log(`[BacklogHook] Auto-selecting project: ${(response.data as any).metadata.project_key}`);
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
        setIsLocked(false);
    }, []);

    // Phase 43: Save to JIRA mutation
    const saveToJiraMutation = useMutation({
        mutationFn: async (threadId: string) => {
            const response = await api.post(`/backlog/export/${threadId}`);
            return response.data;
        },
        onSuccess: (data, threadId) => {
            if (data.stories) {
                setStories(data.stories);
            }
            if (data.is_locked !== undefined) {
                setIsLocked(data.is_locked);
            } else {
                setIsLocked(true); // Fallback to true if we just saved
            }
            // Refresh messages/thread to show the new JIRA links assistant message
            if (threadId) {
                loadThread(threadId);
            }
        }
    });

    // Import Spec Mutation
    const importSpecMutation = useMutation({
        mutationFn: async (file: File) => {
            const formData = new FormData();
            formData.append('file', file);

            const response = await api.post('/backlog/import', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            });
            return response.data; // Returns { epic_description: "..." }
        }
    });

    return {
        stories,
        setStories,
        messages,
        versions,
        activeVersionId,
        loadVersion,
        recommendations,
        currentThreadId,
        currentEpic,
        loadThread,
        updateStoryLocally,
        reset,
        jiraBaseUrl,
        isProcessing: chatMutation.isPending || importSpecMutation.isPending,
        isLocked,
        sendMessage: chatMutation.mutate,
        error: chatMutation.error || importSpecMutation.error,
        saveToJira: (threadId: string) => saveToJiraMutation.mutate(threadId),
        isSavingToJira: saveToJiraMutation.isPending,
        importSpec: importSpecMutation.mutateAsync,
        isImporting: importSpecMutation.isPending
    };
};
