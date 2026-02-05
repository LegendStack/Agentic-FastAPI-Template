import { motion } from 'framer-motion';
import {
    Trash2,
    Zap,
    Hash,
    CheckCircle2,
    Copy,
    Check,
    TrendingUp,
    ShieldAlert,
    ExternalLink
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import type { UserStory } from '../hooks/useBacklog';
import { useState } from 'react';

interface StoryCardProps {
    story: UserStory;
    onUpdate: (story: UserStory) => void;
    onDelete: (id: string) => void;
}

export const StoryCard = ({ story, onUpdate, onDelete }: StoryCardProps) => {
    const [copied, setCopied] = useState(false);

    const handleCopy = async () => {
        const text = `**${story.id}: ${story.title}**\n\n${story.description}\n\n**Acceptance Criteria:**\n${story.acceptance_criteria.map(ac => typeof ac === 'string' ? `- ${ac}` : `- ${ac.description}`).join('\n')}`;
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <motion.div
            layout
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className="glass-card p-6 border-accent-primary/5 flex flex-col gap-4 relative overflow-hidden group mb-4"
        >

            <div className="flex items-start gap-3">
                <div className="mt-1 p-1.5 rounded-md bg-accent-primary/10 text-accent-primary">
                    <Hash className="w-3.5 h-3.5" />
                </div>
                <div className="flex-1">
                    <div className="flex items-baseline gap-2 mb-1">
                        <span className="text-xs font-mono text-accent-primary uppercase tracking-tighter whitespace-nowrap shrink-0">{story.id}</span>
                        {story.jira_key && (
                            <a
                                href={story.jira_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-accent-primary/10 border border-accent-primary/20 text-[10px] text-accent-primary hover:bg-accent-primary/20 transition-all ml-1"
                                onClick={(e) => e.stopPropagation()}
                            >
                                <ExternalLink className="w-2.5 h-2.5" />
                                {story.jira_key}
                            </a>
                        )}
                        <textarea
                            value={story.title}
                            onChange={(e) => onUpdate({ ...story, title: e.target.value })}
                            className="w-full bg-transparent border-none text-base font-bold text-text-primary focus:ring-0 p-0 hover:bg-bg-tertiary/20 rounded transition-colors resize-none overflow-hidden h-auto"
                            rows={1}
                            style={{ height: 'auto', minHeight: '28px' }}
                            onInput={(e) => {
                                const target = e.target as HTMLTextAreaElement;
                                target.style.height = 'auto';
                                target.style.height = `${target.scrollHeight}px`;
                            }}
                        />
                    </div>
                    <textarea
                        value={story.description}
                        onChange={(e) => onUpdate({ ...story, description: e.target.value })}
                        className="w-full bg-transparent border-none text-text-secondary focus:ring-0 p-0 resize-none hover:bg-bg-tertiary/20 rounded transition-colors min-h-[60px] overflow-hidden"
                        rows={3}
                        style={{ height: 'auto', minHeight: '60px' }}
                        onInput={(e) => {
                            const target = e.target as HTMLTextAreaElement;
                            target.style.height = 'auto';
                            target.style.height = `${target.scrollHeight}px`;
                        }}
                    />
                </div>
            </div>

            {story.is_duplicate && (
                <div className="mb-2 p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg flex items-start gap-3">
                    <ShieldAlert className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
                    <div className="text-[11px] text-amber-200/80 italic">
                        {story.duplicate_reason || "Potential overlap with an existing story in the backlog."}
                    </div>
                </div>
            )}

            {/* Acceptance Criteria with Markdown Support */}
            <div className="space-y-2">
                <h4 className="text-[10px] font-bold text-text-secondary uppercase tracking-widest flex items-center gap-2">
                    <CheckCircle2 className="w-3 h-3" /> Acceptance Criteria
                </h4>
                <div className="text-sm text-text-secondary pl-5 prose prose-invert max-w-none">
                    {story.acceptance_criteria.length > 0 ? (
                        <div className="space-y-1">
                            {story.acceptance_criteria.map((ac, idx) => (
                                <div key={idx} className="flex flex-col gap-1 py-1 group/ac">
                                    <div className="flex gap-2">
                                        <span className="text-accent-primary font-bold">•</span>
                                        <div className="flex-1 text-text-primary font-medium">
                                            <ReactMarkdown>
                                                {typeof ac === 'string' ? ac : ac.description}
                                            </ReactMarkdown>
                                        </div>
                                    </div>

                                    {/* BDD Given/When/Then Block */}
                                    {typeof ac !== 'string' && ac.given && ac.when && ac.then && (
                                        <div className="ml-5 mt-1 p-3 rounded-lg bg-bg-tertiary/40 border border-border-primary flex flex-col gap-1.5 text-[11px]">
                                            <div className="flex gap-2">
                                                <span className="text-accent-primary/60 font-mono w-10 shrink-0 uppercase tracking-tighter">Given</span>
                                                <span className="text-text-secondary">{ac.given}</span>
                                            </div>
                                            <div className="flex gap-2">
                                                <span className="text-accent-primary/60 font-mono w-10 shrink-0 uppercase tracking-tighter">When</span>
                                                <span className="text-text-secondary">{ac.when}</span>
                                            </div>
                                            <div className="flex gap-2">
                                                <span className="text-accent-primary/60 font-mono w-10 shrink-0 uppercase tracking-tighter">Then</span>
                                                <span className="text-text-primary font-medium">{ac.then}</span>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    ) : (
                        <p className="italic text-text-tertiary">No criteria defined yet...</p>
                    )}
                </div>
            </div>

            <div className="flex items-center justify-between pt-4 mt-2 border-t border-border-primary/20">
                <div className="flex flex-wrap gap-2">
                    {story.acceptance_criteria.length > 0 && (
                        <div className="flex items-center gap-1 px-3 py-1 rounded-full bg-bg-primary/80 border border-border-primary text-[10px] text-text-secondary">
                            <Zap className="w-3 h-3 text-yellow-400" />
                            {story.acceptance_criteria.length} Criteria
                        </div>
                    )}
                    {story.estimated_complexity && (
                        <div className="px-3 py-1 rounded-full bg-accent-primary/10 border border-accent-primary/30 text-[10px] text-accent-primary font-bold">
                            SIZE: {story.estimated_complexity}
                        </div>
                    )}
                    {story.business_value_score && story.effort_score && (
                        <div className={`px-3 py-1 rounded-full border text-[10px] font-bold flex items-center gap-1.5 ${(story.business_value_score / story.effort_score) >= 1.5
                            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                            : (story.business_value_score / story.effort_score) >= 0.8
                                ? 'bg-yellow-500/10 border-yellow-500/30 text-yellow-400'
                                : 'bg-red-500/10 border-red-500/30 text-red-400'
                            }`}>
                            <TrendingUp className="w-3 h-3" />
                            ROI: {Math.round((story.business_value_score / story.effort_score) * 10) / 10}
                        </div>
                    )}
                    {story.business_value_score && (
                        <div className="px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/30 text-[10px] text-blue-400 font-medium">
                            VALUE: {story.business_value_score}
                        </div>
                    )}
                    {story.tags.map(tag => (
                        <div key={tag} className="px-3 py-1 rounded-full bg-bg-tertiary/50 border border-border-primary text-[10px] text-text-secondary">
                            {tag}
                        </div>
                    ))}
                </div>

                <div className="flex items-center gap-1 opacity-100 transition-opacity">
                    <button
                        onClick={handleCopy}
                        className="p-2 rounded-lg hover:bg-bg-tertiary text-text-tertiary hover:text-accent-primary transition-colors"
                        title="Copy story"
                    >
                        {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                    </button>
                    <button
                        onClick={() => onDelete(story.id)}
                        className="p-2 rounded-lg hover:bg-bg-tertiary text-text-tertiary hover:text-red-400 transition-colors"
                        title="Delete story"
                    >
                        <Trash2 className="w-4 h-4" />
                    </button>
                </div>
            </div>
        </motion.div>
    );
};
