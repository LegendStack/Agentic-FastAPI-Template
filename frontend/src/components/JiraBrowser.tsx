import { useState, useEffect } from 'react';
import {
    Building2,
    ScrollText,
    FileText,
    ChevronRight,
    ChevronDown,
    Wand2,
    Sparkles,
    ExternalLink,
    Search,
    Loader2,
    X,
    Pin,
    Trophy,
    Brain,
    History as HistoryIcon
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useProjectContext } from '../hooks/useProjectContext';

interface JiraBrowserProps {
    onDecomposeEpic: (epic: { key: string, summary: string }) => void;
    onImproveStory: (story: { key: string, summary: string }) => void;
    onClose: () => void;
    jiraBaseUrl?: string | null;
}

interface JiraNode {
    id: string;
    key: string;
    summary?: string;
    name?: string; // for projects
    status?: string;
    type: 'project' | 'epic' | 'story' | 'task' | 'issue';
    issuetype?: string;
    labels?: string[];
    url?: string;
}

interface TreeNodeProps {
    node: JiraNode;
    isExpanded: boolean;
    children?: JiraNode[];
    isLoading?: boolean;
    onToggle: () => void;
    expandedNodes: Record<string, boolean>;
    nodeChildren: Record<string, JiraNode[]>;
    loadingNodes: Record<string, boolean>;
    onNodeToggle: (node: JiraNode) => void;
    onDecomposeEpic: (epic: { key: string, summary: string }) => void;
    onImproveStory: (story: { key: string; summary: string }) => void;
    isPinned?: boolean;
    onClear?: () => void;
    jiraBaseUrl?: string | null;
}

const TreeNode = ({
    node,
    isExpanded,
    children,
    isLoading,
    onToggle,
    expandedNodes,
    nodeChildren,
    loadingNodes,
    onNodeToggle,
    onDecomposeEpic,
    onImproveStory,
    isPinned,
    onClear,
    jiraBaseUrl
}: TreeNodeProps) => {
    return (
        <div className="select-none">
            <div
                className={`group flex items-center gap-2 p-2 rounded-lg transition-all cursor-pointer border ${isPinned ? 'border-accent-primary/30 bg-accent-primary/5 shadow-sm' : 'border-transparent hover:bg-bg-tertiary/50'
                    }`}
                onClick={onToggle}
            >
                <div className="w-4 h-4 flex items-center justify-center text-text-tertiary">
                    {isLoading ? (
                        <Loader2 className="w-3 h-3 animate-spin text-accent-primary" />
                    ) : (
                        (node.type === 'project' || node.type === 'epic') ? (
                            isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />
                        ) : null
                    )}
                </div>

                <div className={`p-1.5 rounded-lg bg-opacity-10 shrink-0 ${node.type === 'project' ? 'bg-blue-500 text-blue-400' :
                    node.type === 'epic' ? 'bg-purple-500 text-purple-400' :
                        'bg-emerald-500 text-emerald-400'
                    }`}>
                    {node.type === 'project' ? <Building2 className="w-3.5 h-3.5" /> :
                        node.type === 'epic' ? <ScrollText className="w-3.5 h-3.5" /> :
                            <FileText className="w-3.5 h-3.5" />}
                </div>

                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 overflow-hidden">
                        <span className={`text-[9px] font-mono leading-none tracking-wider ${isPinned ? 'text-accent-primary' : 'text-text-tertiary'}`}>
                            {node.key}
                        </span>
                        {node.status && (
                            <span className="text-[7px] px-1 py-0.5 rounded bg-white/5 text-text-tertiary uppercase font-black tracking-tighter border border-white/5">
                                {node.status}
                            </span>
                        )}
                        {node.labels?.includes('ai') && (
                            <span className="flex items-center gap-0.5 text-[8px] px-1 py-0.5 rounded bg-accent-primary/10 text-accent-primary border border-accent-primary/20 animate-pulse" title="Assistant Generated">
                                <Brain className="w-2 h-2" />
                                AI
                            </span>
                        )}
                        {isPinned && <Pin className="w-2.5 h-2.5 text-accent-primary fill-accent-primary" />}
                    </div>
                    <div className={`text-xs truncate font-medium ${isExpanded ? 'text-text-primary' : 'text-text-secondary'}`}>
                        {node.summary || node.name}
                    </div>
                </div>

                {/* Direct Actions */}
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    {node.type === 'epic' && (
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                onDecomposeEpic({ key: node.key, summary: node.summary || '' });
                            }}
                            className="p-1.5 rounded bg-accent-primary/10 text-accent-primary hover:bg-accent-primary/20 transition-colors"
                            title="Decompose Epic"
                        >
                            <Wand2 className="w-3.5 h-3.5" />
                        </button>
                    )}
                    {(node.type === 'story' || node.type === 'task' || node.type === 'issue') && (
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                onImproveStory({ key: node.key, summary: node.summary || '' });
                            }}
                            className="p-1.5 rounded bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20 transition-colors"
                            title="Improve Story"
                        >
                            <Sparkles className="w-3.5 h-3.5" />
                        </button>
                    )}
                    {onClear && (
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                onClear();
                            }}
                            className="p-1.5 rounded bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors"
                            title="Clear Context"
                        >
                            <X className="w-3.5 h-3.5" />
                        </button>
                    )}
                    <a
                        href={node.url || (jiraBaseUrl ? (node.type === 'project' ? `${jiraBaseUrl}/projects/${node.key}` : `${jiraBaseUrl}/browse/${node.key}`) : `https://jira.atlassian.net/browse/${node.key}`)}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="p-1.5 rounded bg-bg-tertiary text-text-tertiary hover:text-text-primary transition-colors"
                        title="View in Jira"
                    >
                        <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                </div>
            </div>

            {/* Tree Children */}
            <AnimatePresence>
                {isExpanded && children && (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="ml-4 border-l border-border-primary/50 overflow-hidden"
                    >
                        <div className="pl-2 pt-1 pb-1 space-y-1">
                            {children.map(child => (
                                <TreeNode
                                    key={`child-${child.key}`}
                                    node={child}
                                    isExpanded={!!expandedNodes[child.key]}
                                    children={nodeChildren[child.key]}
                                    isLoading={loadingNodes[child.key]}
                                    onToggle={() => onNodeToggle(child)}
                                    expandedNodes={expandedNodes}
                                    nodeChildren={nodeChildren}
                                    loadingNodes={loadingNodes}
                                    onNodeToggle={onNodeToggle}
                                    onDecomposeEpic={onDecomposeEpic}
                                    onImproveStory={onImproveStory}
                                    jiraBaseUrl={jiraBaseUrl}
                                />
                            ))}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
};

export const JiraBrowser = ({ onDecomposeEpic, onImproveStory, onClose, jiraBaseUrl }: JiraBrowserProps) => {
    const { selectedProject, selectedEpic, setProject, setSelectedEpic, clearContext } = useProjectContext();
    const [searchTerm, setSearchTerm] = useState('');
    const [debouncedSearch, setDebouncedSearch] = useState('');
    const [results, setResults] = useState<JiraNode[]>([]);
    const [recentSearches, setRecentSearches] = useState<JiraNode[]>([]);
    const [expandedNodes, setExpandedNodes] = useState<Record<string, boolean>>({});
    const [nodeChildren, setNodeChildren] = useState<Record<string, JiraNode[]>>({});
    const [loadingNodes, setLoadingNodes] = useState<Record<string, boolean>>({});
    const [isSearching, setIsSearching] = useState(false);

    // Initial state: Show current context or recents
    useEffect(() => {
        const saved = localStorage.getItem('recentJiraItems');
        if (saved) {
            setRecentSearches(JSON.parse(saved));
        }
    }, []);

    // Debounce search
    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedSearch(searchTerm);
        }, 500);
        return () => clearTimeout(timer);
    }, [searchTerm]);

    // Perform Universal Search
    useEffect(() => {
        if (!debouncedSearch) {
            setResults([]);
            return;
        }

        const performSearch = async () => {
            setIsSearching(true);
            try {
                const response = await fetch(`/api/v1/jira/search/universal?query=${encodeURIComponent(debouncedSearch)}`);
                if (response.ok) {
                    const data = await response.json();
                    setResults(data);
                }
            } catch (err) {
                console.error("Universal Search failed", err);
            } finally {
                setIsSearching(false);
            }
        };

        performSearch();
    }, [debouncedSearch]);

    const saveToRecents = (node: JiraNode) => {
        const updated = [node, ...recentSearches.filter(n => n.key !== node.key)].slice(0, 10);
        setRecentSearches(updated);
        localStorage.setItem('recentJiraItems', JSON.stringify(updated));
    };

    const toggleNode = async (node: JiraNode) => {
        const isExpanded = !!expandedNodes[node.key];

        // Pin logic
        if (node.type === 'project') {
            setProject(node.key);
        } else if (node.type === 'epic') {
            setSelectedEpic({ id: node.id, key: node.key, summary: node.summary || '' });
        }

        if (!isExpanded && !nodeChildren[node.key] && (node.type === 'project' || node.type === 'epic')) {
            await fetchChildren(node);
        }

        saveToRecents(node);
        setExpandedNodes(prev => ({ ...prev, [node.key]: !isExpanded }));
    };

    const fetchChildren = async (node: JiraNode) => {
        setLoadingNodes(prev => ({ ...prev, [node.key]: true }));
        try {
            let url = '';
            if (node.type === 'project') {
                url = `/api/v1/jira/projects/${node.key}/epics`;
            } else if (node.type === 'epic') {
                url = `/api/v1/jira/projects/${node.key.split('-')[0]}/epics/${node.key}/stories`;
            }

            if (url) {
                const response = await fetch(url);
                if (response.ok) {
                    const data = await response.json();
                    setNodeChildren(prev => ({
                        ...prev,
                        [node.key]: data.map((child: any) => ({
                            ...child,
                            type: node.type === 'project' ? 'epic' : 'story'
                        }))
                    }));
                }
            }
        } catch (err) {
            console.error(`Failed to fetch children for ${node.key}`, err);
        } finally {
            setLoadingNodes(prev => ({ ...prev, [node.key]: false }));
        }
    };

    const projectResults = results.filter(r => r.type === 'project');
    const epicResults = results.filter(r => r.type === 'epic');
    const storyResults = results.filter(r => r.type === 'story' || r.type === 'task' || r.type === 'issue');

    return (
        <motion.div
            initial={{ x: -320, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: -320, opacity: 0 }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="fixed top-0 bottom-0 left-0 w-85 bg-bg-secondary border-r border-border-primary shadow-2xl z-[100] flex flex-col glass"
        >
            {/* Header */}
            <div className="p-6 border-b border-border-primary flex items-center justify-between bg-bg-primary/50">
                <div>
                    <h2 className="text-lg font-bold text-text-primary tracking-tight flex items-center gap-2">
                        Universal Search
                        <Sparkles className="w-4 h-4 text-accent-primary animate-pulse" />
                    </h2>
                    <p className="text-[10px] text-text-tertiary uppercase tracking-widest mt-0.5">Enterprise Jira Suite</p>
                </div>
                <button
                    onClick={onClose}
                    className="p-2 hover:bg-bg-tertiary rounded-lg text-text-tertiary transition-colors"
                >
                    <X className="w-4 h-4" />
                </button>
            </div>

            {/* Search Input */}
            <div className="p-4 border-b border-border-primary bg-bg-primary/30">
                <div className="relative">
                    <Search className={`absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 transition-colors ${isSearching ? 'text-accent-primary animate-spin' : 'text-text-tertiary'}`} />
                    <input
                        type="text"
                        placeholder="Search Projects, Epics, or Stories..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="w-full bg-bg-tertiary/50 border border-border-primary rounded-xl pl-10 pr-4 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:ring-1 focus:ring-accent-primary outline-none transition-all"
                    />
                </div>
            </div>

            {/* Content Area */}
            <div className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar">
                {searchTerm === '' ? (
                    <>
                        {/* Current Context */}
                        {(selectedProject || selectedEpic) && (
                            <div>
                                <div className="text-[10px] text-text-tertiary font-bold uppercase tracking-widest px-2 mb-2 flex items-center justify-between group/header">
                                    <div className="flex items-center gap-1.5 text-accent-primary">
                                        <Pin className="w-3 h-3" />
                                        Active Context
                                    </div>
                                    <button
                                        onClick={clearContext}
                                        className="text-[9px] hover:text-red-400 transition-colors opacity-0 group-hover/header:opacity-100 flex items-center gap-1"
                                    >
                                        <X className="w-2.5 h-2.5" />
                                        Clear All
                                    </button>
                                </div>
                                <div className="space-y-1">
                                    {selectedProject && (
                                        <TreeNode
                                            key={`active-p-${selectedProject}`}
                                            node={{ key: selectedProject, name: "Active Project", type: 'project', id: 'active' }}
                                            isExpanded={!!expandedNodes[selectedProject]}
                                            children={nodeChildren[selectedProject]}
                                            isLoading={loadingNodes[selectedProject]}
                                            onToggle={() => toggleNode({ key: selectedProject, type: 'project', id: 'active' })}
                                            expandedNodes={expandedNodes}
                                            nodeChildren={nodeChildren}
                                            loadingNodes={loadingNodes}
                                            onNodeToggle={toggleNode}
                                            onDecomposeEpic={onDecomposeEpic}
                                            onImproveStory={onImproveStory}
                                            isPinned
                                            onClear={() => setProject(null)}
                                            jiraBaseUrl={jiraBaseUrl}
                                        />
                                    )}
                                    {selectedEpic && (
                                        <TreeNode
                                            key={`active-e-${selectedEpic.key}`}
                                            node={{ ...selectedEpic, type: 'epic' }}
                                            isExpanded={!!expandedNodes[selectedEpic.key]}
                                            children={nodeChildren[selectedEpic.key]}
                                            isLoading={loadingNodes[selectedEpic.key]}
                                            onToggle={() => toggleNode({ ...selectedEpic, type: 'epic' })}
                                            expandedNodes={expandedNodes}
                                            nodeChildren={nodeChildren}
                                            loadingNodes={loadingNodes}
                                            onNodeToggle={toggleNode}
                                            onDecomposeEpic={onDecomposeEpic}
                                            onImproveStory={onImproveStory}
                                            isPinned
                                            onClear={() => setSelectedEpic(null)}
                                            jiraBaseUrl={jiraBaseUrl}
                                        />
                                    )}
                                </div>
                            </div>
                        )}

                        {/* Recent Items */}
                        {recentSearches.length > 0 && (
                            <div>
                                <div className="text-[10px] text-text-tertiary font-bold uppercase tracking-widest px-2 mb-2 flex items-center gap-1.5">
                                    <HistoryIcon className="w-3 h-3" />
                                    Recently Accessed
                                </div>
                                <div className="space-y-1">
                                    {recentSearches.map(node => (
                                        <TreeNode
                                            key={`recent-${node.key}`}
                                            node={node}
                                            isExpanded={!!expandedNodes[node.key]}
                                            children={nodeChildren[node.key]}
                                            isLoading={loadingNodes[node.key]}
                                            onToggle={() => toggleNode(node)}
                                            expandedNodes={expandedNodes}
                                            nodeChildren={nodeChildren}
                                            loadingNodes={loadingNodes}
                                            onNodeToggle={toggleNode}
                                            onDecomposeEpic={onDecomposeEpic}
                                            onImproveStory={onImproveStory}
                                            jiraBaseUrl={jiraBaseUrl}
                                        />
                                    ))}
                                </div>
                            </div>
                        )}

                        {recentSearches.length === 0 && !selectedProject && (
                            <div className="py-20 text-center flex flex-col items-center opacity-30 px-10">
                                <Search className="w-12 h-12 mb-4 text-text-tertiary" />
                                <h3 className="text-sm font-bold text-text-primary mb-1">Type to Search</h3>
                                <p className="text-xs text-text-tertiary italic">Instantly find any issue across your entire Jira footprint.</p>
                            </div>
                        )}
                    </>
                ) : (
                    <>
                        {/* Search Results */}
                        {isSearching ? (
                            <div className="flex flex-col items-center justify-center py-20 opacity-50">
                                <Loader2 className="w-10 h-10 text-accent-primary animate-spin mb-4" />
                                <span className="text-xs text-text-tertiary tracking-widest uppercase animate-pulse">Scanning JIRA Universe</span>
                            </div>
                        ) : results.length > 0 ? (
                            <>
                                {projectResults.length > 0 && (
                                    <div>
                                        <div className="text-[10px] text-text-tertiary font-bold uppercase tracking-widest px-2 mb-2">Projects</div>
                                        {projectResults.map(p => (
                                            <TreeNode
                                                key={`search-p-${p.key}`}
                                                node={p}
                                                isExpanded={!!expandedNodes[p.key]}
                                                onToggle={() => toggleNode(p)}
                                                expandedNodes={expandedNodes}
                                                nodeChildren={nodeChildren}
                                                loadingNodes={loadingNodes}
                                                onNodeToggle={toggleNode}
                                                onDecomposeEpic={onDecomposeEpic}
                                                onImproveStory={onImproveStory}
                                                jiraBaseUrl={jiraBaseUrl}
                                            />
                                        ))}
                                    </div>
                                )}
                                {epicResults.length > 0 && (
                                    <div>
                                        <div className="text-[10px] text-text-tertiary font-bold uppercase tracking-widest px-2 mb-2">Epics</div>
                                        {epicResults.map(e => (
                                            <TreeNode
                                                key={`search-e-${e.key}`}
                                                node={e}
                                                isExpanded={!!expandedNodes[e.key]}
                                                onToggle={() => toggleNode(e)}
                                                expandedNodes={expandedNodes}
                                                nodeChildren={nodeChildren}
                                                loadingNodes={loadingNodes}
                                                onNodeToggle={toggleNode}
                                                onDecomposeEpic={onDecomposeEpic}
                                                onImproveStory={onImproveStory}
                                                jiraBaseUrl={jiraBaseUrl}
                                            />
                                        ))}
                                    </div>
                                )}
                                {storyResults.length > 0 && (
                                    <div>
                                        <div className="text-[10px] text-text-tertiary font-bold uppercase tracking-widest px-2 mb-2">Stories & Tasks</div>
                                        {storyResults.map(s => (
                                            <TreeNode
                                                key={`search-s-${s.key}`}
                                                node={s}
                                                isExpanded={!!expandedNodes[s.key]}
                                                onToggle={() => toggleNode(s)}
                                                expandedNodes={expandedNodes}
                                                nodeChildren={nodeChildren}
                                                loadingNodes={loadingNodes}
                                                onNodeToggle={toggleNode}
                                                onDecomposeEpic={onDecomposeEpic}
                                                onImproveStory={onImproveStory}
                                                jiraBaseUrl={jiraBaseUrl}
                                            />
                                        ))}
                                    </div>
                                )}
                            </>
                        ) : (
                            <div className="py-20 text-center px-10">
                                <Trophy className="w-12 h-12 mb-4 text-text-tertiary/20 mx-auto" />
                                <h3 className="text-sm font-bold text-text-primary mb-1">No matches found</h3>
                                <p className="text-xs text-text-tertiary italic">Try searching by issue key (e.g. CORE-123) or high-level keywords.</p>
                            </div>
                        )}
                    </>
                )}
            </div>

            {/* Footer Status */}
            <div className="p-4 border-t border-border-primary bg-bg-primary/50 flex items-center justify-between text-[10px] text-text-tertiary font-mono">
                <div className="flex items-center gap-1.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    CONNECTED
                </div>
                <span>Universal v1.0</span>
            </div>
        </motion.div>
    );
};
