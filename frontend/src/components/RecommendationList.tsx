import { motion } from 'framer-motion';
import { Sparkles, ArrowRight } from 'lucide-react';

interface RecommendationListProps {
    recommendations: string[];
    onSelect: (recommendation: string) => void;
    disabled?: boolean;
}

export const RecommendationList = ({ recommendations, onSelect, disabled }: RecommendationListProps) => {
    if (!recommendations.length) return null;

    return (
        <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            className="flex flex-wrap gap-2 mb-4 w-full max-w-3xl justify-center pointer-events-auto"
        >
            {recommendations.map((rec, i) => (
                <button
                    key={i}
                    onClick={() => onSelect(rec)}
                    disabled={disabled}
                    className="group flex items-center gap-2 px-4 py-2 rounded-xl bg-bg-tertiary/90 border border-accent-primary/20 text-xs font-medium text-text-secondary hover:text-accent-primary hover:bg-bg-secondary hover:border-accent-primary/50 transition-all shadow-sm backdrop-blur-md"
                >
                    <Sparkles className="w-3 h-3 text-accent-primary group-hover:scale-110 transition-transform" />
                    <span>{rec}</span>
                    <ArrowRight className="w-3 h-3 opacity-0 -ml-2 group-hover:opacity-100 group-hover:ml-0 transition-all text-accent-primary" />
                </button>
            ))}
        </motion.div>
    );
};
