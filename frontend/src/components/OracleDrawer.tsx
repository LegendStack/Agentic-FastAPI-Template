import { useState } from 'react';
import { Wand2, Sparkles } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface OracleDrawerProps {
    onSendMessage: (message: string) => void;
    isProcessing: boolean;
    recommendations?: string[];
}

export const OracleDrawer = ({ onSendMessage, isProcessing, recommendations = [] }: OracleDrawerProps) => {
    const [input, setInput] = useState('');

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (input.trim() && !isProcessing) {
            onSendMessage(input);
            setInput('');
        }
    };

    const handleSuggestClick = (suggestion: string) => {
        if (!isProcessing) {
            onSendMessage(suggestion);
        }
    };

    return (
        <div className="w-full p-6 flex flex-col items-center pointer-events-none mt-auto sticky bottom-0 z-30">
            <AnimatePresence>
                {recommendations.length > 0 && !isProcessing && (
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 20 }}
                        className="flex gap-2 mb-3 pointer-events-auto"
                    >
                        {recommendations.map((rec, i) => (
                            <button
                                key={i}
                                onClick={() => handleSuggestClick(rec)}
                                className="px-3 py-1.5 rounded-full bg-bg-tertiary/80 border border-accent-primary/30 text-[10px] font-bold text-accent-primary hover:bg-accent-primary hover:text-bg-primary transition-all shadow-lg backdrop-blur-sm"
                            >
                                ✨ {rec}
                            </button>
                        ))}
                    </motion.div>
                )}
            </AnimatePresence>

            <motion.form
                onSubmit={handleSubmit}
                initial={{ y: 20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                className="w-full glass p-2 rounded-2xl shadow-xl flex gap-2 pointer-events-auto border-accent-primary/20"
            >
                <div className="flex-1 relative">
                    <Sparkles className={`absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 ${isProcessing ? 'text-accent-primary animate-spin' : 'text-text-secondary'}`} />
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        disabled={isProcessing}
                        placeholder={isProcessing ? "Oracle is refining..." : "Ask the agent to refine, add edge cases, or convert to BDD..."}
                        className="w-full bg-bg-primary/40 border-none pl-12 pr-4 py-4 rounded-xl text-text-primary placeholder-text-secondary focus:ring-1 focus:ring-accent-primary/50 outline-none transition-all"
                    />
                </div>
                <button
                    type="submit"
                    disabled={!input.trim() || isProcessing}
                    className="p-4 bg-accent-primary text-slate-900 font-bold rounded-xl hover:bg-accent-secondary transition-colors disabled:opacity-50 disabled:grayscale flex items-center justify-center group shadow-lg"
                >
                    <Wand2
                        className={`w-5 h-5 ${isProcessing ? 'animate-spin' : 'group-hover:rotate-12'} transition-transform`}
                        strokeWidth={2.5}
                    />
                </button>
            </motion.form>
        </div>
    );
};
