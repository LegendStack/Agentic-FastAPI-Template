import { motion } from 'framer-motion';
import {
    Trash2,
    Zap,
    Hash,
    ArrowRightLeft,
    CheckCircle2
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import type { UserStory } from '../hooks/useBacklog';

interface StoryCardProps {
    story: UserStory;
    onUpdate: (story: UserStory) => void;
    onDelete: (id: string) => void;
}

export const StoryCard = ({ story, onUpdate, onDelete }: StoryCardProps) => {
    return (
        <motion.div
            layout
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className="glass-card p-6 border-brand-blue/5 flex flex-col gap-4 relative overflow-hidden group mb-4"
        >
            {/* Refinement Indicator */}
            <div className="absolute top-0 right-12 p-3 opacity-0 group-hover:opacity-100 transition-opacity">
                <ArrowRightLeft className="w-4 h-4 text-brand-blue/40" />
            </div>

            <div className="absolute top-0 right-0 p-3 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                    onClick={() => onDelete(story.id)}
                    className="p-2 text-slate-500 hover:text-red-400 transition-colors"
                >
                    <Trash2 className="w-4 h-4" />
                </button>
            </div>

            <div className="flex items-start gap-4">
                <div className="mt-1 p-2 rounded-lg bg-brand-blue/5 text-brand-blue">
                    <Hash className="w-5 h-5" />
                </div>
                <div className="flex-1">
                    <div className="flex items-baseline gap-2 mb-1">
                        <span className="text-xs font-mono text-brand-blue uppercase tracking-tighter">{story.id}</span>
                        <input
                            value={story.title}
                            onChange={(e) => onUpdate({ ...story, title: e.target.value })}
                            className="w-full bg-transparent border-none text-xl font-bold text-white focus:ring-0 p-0 hover:bg-slate-800/20 rounded transition-colors"
                        />
                    </div>
                    <textarea
                        value={story.description}
                        onChange={(e) => onUpdate({ ...story, description: e.target.value })}
                        className="w-full bg-transparent border-none text-slate-300 focus:ring-0 p-0 resize-none hover:bg-slate-800/20 rounded transition-colors min-h-[60px]"
                    />
                </div>
            </div>

            {/* Acceptance Criteria with Markdown Support */}
            <div className="space-y-2">
                <h4 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest flex items-center gap-2">
                    <CheckCircle2 className="w-3 h-3" /> Acceptance Criteria
                </h4>
                <div className="text-sm text-slate-400 pl-5 prose prose-invert max-w-none">
                    {story.acceptance_criteria.length > 0 ? (
                        <div className="space-y-1">
                            {story.acceptance_criteria.map((ac, idx) => (
                                <div key={idx} className="flex flex-col gap-1 py-1 group/ac">
                                    <div className="flex gap-2">
                                        <span className="text-brand-blue font-bold">•</span>
                                        <div className="flex-1 text-slate-300 font-medium">
                                            <ReactMarkdown>
                                                {typeof ac === 'string' ? ac : ac.description}
                                            </ReactMarkdown>
                                        </div>
                                    </div>

                                    {/* BDD Given/When/Then Block */}
                                    {typeof ac !== 'string' && ac.given && ac.when && ac.then && (
                                        <div className="ml-5 mt-1 p-3 rounded-lg bg-slate-800/40 border border-slate-700/50 flex flex-col gap-1.5 text-[11px]">
                                            <div className="flex gap-2">
                                                <span className="text-brand-blue/60 font-mono w-10 shrink-0 uppercase tracking-tighter">Given</span>
                                                <span className="text-slate-400">{ac.given}</span>
                                            </div>
                                            <div className="flex gap-2">
                                                <span className="text-brand-blue/60 font-mono w-10 shrink-0 uppercase tracking-tighter">When</span>
                                                <span className="text-slate-400">{ac.when}</span>
                                            </div>
                                            <div className="flex gap-2">
                                                <span className="text-brand-blue/60 font-mono w-10 shrink-0 uppercase tracking-tighter">Then</span>
                                                <span className="text-slate-200 font-medium">{ac.then}</span>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    ) : (
                        <p className="italic text-slate-600">No criteria defined yet...</p>
                    )}
                </div>
            </div>

            <div className="flex flex-wrap gap-2 pt-2">
                {story.acceptance_criteria.length > 0 && (
                    <div className="flex items-center gap-1 px-3 py-1 rounded-full bg-brand-navy/80 border border-slate-700 text-[10px] text-slate-400">
                        <Zap className="w-3 h-3 text-yellow-400" />
                        {story.acceptance_criteria.length} Criteria
                    </div>
                )}
                {story.estimated_complexity && (
                    <div className="px-3 py-1 rounded-full bg-brand-blue/10 border border-brand-blue/30 text-[10px] text-brand-blue font-bold">
                        SIZE: {story.estimated_complexity}
                    </div>
                )}
                {story.tags.map(tag => (
                    <div key={tag} className="px-3 py-1 rounded-full bg-slate-800/50 border border-slate-700 text-[10px] text-slate-500">
                        {tag}
                    </div>
                ))}
            </div>
        </motion.div>
    );
};
