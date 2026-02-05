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
    onLoadVersion: (id: string) => void;
    onUpdateStory: (story: UserStory) => void;
    onDeleteStory: (id: string) => void;
    onCollapse?: () => void;
}

export const ArtifactBoard = ({
    stories,
    versions,
    activeVersionId,
    projectName,
    onLoadVersion,
    onUpdateStory,
    onDeleteStory,
    onCollapse
}: ArtifactBoardProps) => {
    const [isVersionOpen, setIsVersionOpen] = useState(false);
    return (
        <div className="flex flex-col h-full bg-brand-navy/30 border-l border-slate-700/50">
            {/* Artifact Header with Version Picker */}
            <div className="p-6 border-b border-slate-700/30 flex items-center justify-between glass sticky top-0 z-20">
                <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-brand-blue/10 text-brand-blue border border-brand-blue/20">
                        <History className="w-5 h-5" />
                    </div>
                    <div>
                        <h3 className="font-bold text-white leading-none flex items-center gap-2">
                            Backlog Artifact
                            {projectName && (
                                <span className="px-2 py-0.5 rounded-md bg-brand-blue/10 border border-brand-blue/30 text-[8px] uppercase tracking-tighter text-brand-blue">
                                    {projectName}
                                </span>
                            )}
                        </h3>
                        <p className="text-[10px] text-slate-500 mt-1 uppercase tracking-widest font-semibold">
                            {stories.length} Stories Generated
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-4">
                    {onCollapse && (
                        <button
                            onClick={onCollapse}
                            className="p-2 rounded-lg hover:bg-slate-700/50 text-slate-400 hover:text-white transition-all border border-transparent hover:border-slate-700/50"
                            title="Collapse panel"
                        >
                            <LayoutDashboard className="w-5 h-5" />
                        </button>
                    )}

                    <div className="h-8 w-px bg-slate-700/30 mx-2" />

                    {/* Prominent Version Picker Dropdown */}
                    <div className="relative">
                        <button
                            onClick={() => setIsVersionOpen(!isVersionOpen)}
                            className="flex items-center gap-2 px-4 py-2 bg-slate-800/80 hover:bg-slate-700 rounded-xl border border-slate-700/50 text-[11px] font-bold text-slate-300 hover:text-white transition-all shadow-lg min-w-[140px]"
                        >
                            <Clock className="w-3.5 h-3.5 text-brand-blue" />
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
                                    className="absolute right-0 mt-2 w-64 glass border border-slate-700/50 rounded-2xl shadow-2xl z-50 overflow-hidden"
                                >
                                    <div className="p-2 flex flex-col gap-1 max-h-[300px] overflow-y-auto no-scrollbar">
                                        <button
                                            onClick={() => {
                                                onLoadVersion('');
                                                setIsVersionOpen(false);
                                            }}
                                            className={`w-full px-4 py-3 rounded-xl text-left text-[11px] font-bold transition-all flex items-center justify-between ${!activeVersionId
                                                ? 'bg-brand-blue/10 text-brand-blue border border-brand-blue/20'
                                                : 'text-slate-400 hover:bg-slate-700/50 hover:text-white'
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
                                                    ? 'bg-brand-blue/10 text-brand-blue border border-brand-blue/20'
                                                    : 'text-slate-400 hover:bg-slate-700/50 hover:text-white'
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
                                />
                            ))}
                        </motion.div>
                    ) : (
                        <div className="flex flex-col items-center justify-center h-full text-center opacity-50">
                            <Clock className="w-12 h-12 text-slate-700 mb-4 animate-pulse" />
                            <p className="text-slate-500 font-medium">No stories in this version</p>
                        </div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
};
