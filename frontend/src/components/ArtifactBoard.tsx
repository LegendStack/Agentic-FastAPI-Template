import { StoryCard } from './StoryCard';
import type { UserStory, ArtifactVersion } from '../hooks/useBacklog';
import { History, Check, Clock, LayoutDashboard, ChevronDown } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useState } from 'react';

interface ArtifactBoardProps {
    stories: UserStory[];
    versions: ArtifactVersion[];
    activeVersionId: string | null;
    projectName?: string | null;
    jiraBaseUrl?: string | null;
    onLoadVersion: (id: string) => void;
    onUpdateStory: (story: UserStory) => void;
    onDeleteStory: (id: string) => void;
    onCollapse?: () => void;
    saveToJira?: () => void;
    isSavingToJira?: boolean;
    isLocked?: boolean;
    targetIssueType?: string;
}

export const ArtifactBoard = ({
    stories,
    versions,
    activeVersionId,
    projectName,
    jiraBaseUrl,
    onLoadVersion,
    onUpdateStory,
    onDeleteStory,
    onCollapse,
    saveToJira,
    isSavingToJira,
    isLocked = false,
    targetIssueType = 'Story'
}: ArtifactBoardProps) => {
    const pluralize = (type: string) => {
        if (type === 'Story') return 'Stories';
        if (type === 'Sub-task') return 'Sub-tasks';
        return `${type}s`;
    };

    const displayType = pluralize(targetIssueType);
    const [isVersionOpen, setIsVersionOpen] = useState(false);
    return (
        <div className="flex flex-col h-full bg-bg-primary/30 border-l border-border-primary">
            {/* Artifact Header with Version Picker */}
            <div className="p-6 border-b border-border-primary flex items-center justify-between glass sticky top-0 z-20">
                <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-accent-primary/10 text-accent-primary border border-accent-primary/20">
                        <History className="w-5 h-5" />
                    </div>
                    <div>
                        <h3 className="font-bold text-text-primary leading-none flex items-center gap-2">
                            {(() => {
                                const type = targetIssueType?.toLowerCase();
                                if (type === 'epic') return "Initiative Portfolio";
                                if (type === 'story') return "Delivery Backlog";
                                if (type === 'task') return "Engineering Plan";
                                if (type === 'sub-task') return "Execution Details";
                                if (type === 'requirement') return "System Spec";
                                return "Backlog Manifest";
                            })()}
                            {projectName && (
                                <span className="ml-1 px-2 py-0.5 rounded-md bg-accent-primary/10 border border-accent-primary/30 text-[8px] uppercase tracking-tighter text-accent-primary font-mono align-middle">
                                    {jiraBaseUrl ? (
                                        <a
                                            href={`${jiraBaseUrl}/projects/${projectName}`}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="hover:underline flex items-center gap-1"
                                        >
                                            {projectName}
                                        </a>
                                    ) : projectName}
                                </span>
                            )}
                        </h3>
                        <p className="text-[10px] text-text-tertiary mt-1 uppercase tracking-widest font-semibold">
                            {stories.length} {displayType} Generated
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-4">
                    {onCollapse && (
                        <button
                            onClick={onCollapse}
                            className="p-2 rounded-lg hover:bg-bg-secondary text-text-secondary hover:text-text-primary transition-all border border-transparent hover:border-border-primary"
                            title="Collapse panel"
                        >
                            <LayoutDashboard className="w-5 h-5" />
                        </button>
                    )}

                    <div className="h-8 w-px bg-border-primary mx-2" />

                    {/* Prominent Version Picker Dropdown */}
                    <div className="relative">
                        <button
                            onClick={() => setIsVersionOpen(!isVersionOpen)}
                            className="flex items-center gap-2 px-4 py-2 bg-bg-tertiary hover:bg-bg-secondary rounded-xl border border-border-primary text-[11px] font-bold text-text-secondary hover:text-text-primary transition-all shadow-lg min-w-[140px]"
                        >
                            <Clock className="w-4 h-4 text-accent-primary" strokeWidth={2.5} />
                            <span className="flex-1 text-left truncate">
                                {activeVersionId ? `Version ${versions.length - versions.findIndex(v => v.checkpoint_id === activeVersionId)}` : "Latest Version"}
                            </span>
                            <ChevronDown className={`w-4 h-4 transition-transform duration-300 ${isVersionOpen ? 'rotate-180' : ''}`} />
                        </button>

                        <AnimatePresence>
                            {isVersionOpen && (
                                <motion.div
                                    initial={{ opacity: 0, y: 10, scale: 0.95 }}
                                    animate={{ opacity: 1, y: 0, scale: 1 }}
                                    exit={{ opacity: 0, y: 10, scale: 0.95 }}
                                    className="absolute right-0 mt-2 w-64 glass border border-border-primary rounded-2xl shadow-2xl z-50 overflow-hidden"
                                >
                                    <div className="p-2 flex flex-col gap-1 max-h-[300px] overflow-y-auto no-scrollbar">
                                        <button
                                            onClick={() => {
                                                onLoadVersion('');
                                                setIsVersionOpen(false);
                                            }}
                                            className={`w-full px-4 py-3 rounded-xl text-left text-[11px] font-bold transition-all flex items-center justify-between ${!activeVersionId
                                                ? 'bg-accent-primary/10 text-accent-primary border border-accent-primary/20'
                                                : 'text-text-secondary hover:bg-bg-tertiary hover:text-text-primary'
                                                }`}
                                        >
                                            <div className="flex flex-col">
                                                <span>Latest Working Version</span>
                                                <span className="text-[9px] opacity-60 font-medium">Most recent refinement</span>
                                            </div>
                                            {!activeVersionId && <Check className="w-4 h-4" />}
                                        </button>

                                        {versions.map((ver, idx) => (
                                            <button
                                                key={ver.checkpoint_id}
                                                onClick={() => {
                                                    onLoadVersion(ver.checkpoint_id);
                                                    setIsVersionOpen(false);
                                                }}
                                                className={`w-full px-4 py-3 rounded-xl text-left text-[11px] font-bold transition-all flex items-center justify-between ${activeVersionId === ver.checkpoint_id
                                                    ? 'bg-accent-primary/10 text-accent-primary border border-accent-primary/20'
                                                    : 'text-text-secondary hover:bg-bg-tertiary hover:text-text-primary'
                                                    }`}
                                            >
                                                <div className="flex flex-col">
                                                    <span>Version {versions.length - idx}</span>
                                                    <span className="text-[9px] opacity-60 font-medium truncate w-40">
                                                        {ver.summary || "Refinement step"}
                                                    </span>
                                                </div>
                                                {activeVersionId === ver.checkpoint_id && <Check className="w-4 h-4" />}
                                            </button>
                                        ))}
                                    </div>
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>
                </div>
            </div>

            {/* Stories Grid */}
            <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">
                <AnimatePresence mode="popLayout">
                    {stories.length > 0 ? (
                        <motion.div
                            key={activeVersionId || 'latest'}
                            initial={{ opacity: 0, x: 20 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -20 }}
                            transition={{ duration: 0.3 }}
                            className="grid grid-cols-1 gap-4"
                        >
                            {stories.map((story) => (
                                <StoryCard
                                    key={story.id}
                                    story={story}
                                    onUpdate={onUpdateStory}
                                    onDelete={onDeleteStory}
                                    isLocked={isLocked}
                                />
                            ))}
                        </motion.div>
                    ) : (
                        <div className="flex flex-col items-center justify-center h-full text-center opacity-50">
                            <Clock className="w-12 h-12 text-text-tertiary mb-4 animate-pulse" />
                            <p className="text-text-secondary font-medium">No {displayType.toLowerCase()} in this version</p>
                        </div>
                    )}
                </AnimatePresence>
            </div>

            {/* Jira Save Footer - Phase 43 */}
            {stories.length > 0 && (
                <div className="p-4 border-t border-border-primary bg-bg-secondary/20 glass backdrop-blur-xl sticky bottom-0 z-20">
                    <div className="flex items-center justify-between gap-4">
                        <div className="flex flex-col">
                            <span className="text-[10px] text-text-tertiary uppercase tracking-widest font-bold">Jira Sync</span>
                            <span className="text-xs text-text-secondary">
                                {stories.filter(s => s.jira_key).length} of {stories.length} {displayType.toLowerCase()} linked
                            </span>
                        </div>

                        <button
                            onClick={saveToJira}
                            disabled={isSavingToJira || stories.every(s => s.jira_key) || isLocked}
                            className={`flex items-center gap-2 px-6 py-2.5 rounded-xl font-bold text-[11px] transition-all active:scale-95 cursor-pointer disabled:cursor-not-allowed ${stories.every(s => s.jira_key) || isLocked
                                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                : 'bg-teal-600 dark:bg-cyan-400 text-white dark:text-slate-900 hover:bg-teal-700 dark:hover:bg-cyan-300 shadow-[0_0_25px_rgba(13,148,136,0.25)] dark:shadow-[0_0_25px_rgba(100,255,218,0.25)] hover:shadow-teal-500/40 dark:hover:shadow-cyan-400/40 disabled:opacity-50'
                                }`}
                        >
                            {isSavingToJira ? (
                                <>
                                    <div className="w-3 h-3 border-2 border-slate-900/30 border-t-slate-900 rounded-full animate-spin" />
                                    Synchronizing...
                                </>
                            ) : stories.every(s => s.jira_key) ? (
                                <>
                                    <Check className="w-4 h-4" strokeWidth={2.5} />
                                    All {displayType} Synced
                                </>
                            ) : (
                                <>
                                    <LayoutDashboard className="w-4 h-4" strokeWidth={2.5} />
                                    {(() => {
                                        const count = stories.filter(s => !s.jira_key).length;
                                        const type = targetIssueType?.toLowerCase();
                                        if (type === 'epic') return `Publish ${count} Epics to JIRA`;
                                        if (type === 'story') return `Sync ${count} Stories to JIRA`;
                                        if (type === 'task') return `Export ${count} Tasks to JIRA`;
                                        if (type === 'sub-task') return `Push ${count} Details to JIRA`;
                                        if (type === 'requirement') return `Scale ${count} Specs to JIRA`;
                                        return `Sync ${count} ${displayType} to JIRA`;
                                    })()}
                                </>
                            )}
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};
