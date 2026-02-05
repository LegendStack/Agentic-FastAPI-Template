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
        <div className="fixed bottom-0 left-0 right-0 p-6 flex flex-col items-center pointer-events-none z-50">
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
                                className="px-3 py-1.5 rounded-full bg-slate-800/80 border border-brand-blue/30 text-[10px] font-bold text-brand-blue hover:bg-brand-blue hover:text-brand-navy transition-all shadow-lg backdrop-blur-sm"
                            >
                                ✨ {rec}
                            </button>
                        ))}
                    </motion.div>
                )}
            </AnimatePresence>

            <motion.form
                onSubmit={handleSubmit}
                initial={{ y: 100 }}
                animate={{ y: 0 }}
                className="w-full max-w-4xl glass p-2 rounded-2xl shadow-[0_0_50px_rgba(100,255,218,0.15)] flex gap-2 pointer-events-auto border-brand-blue/20"
            >
                <div className="flex-1 relative">
                    <Sparkles className={`absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 ${isProcessing ? 'text-brand-blue animate-spin' : 'text-slate-500'}`} />
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        disabled={isProcessing}
                        placeholder={isProcessing ? "Oracle is refining..." : "Ask the agent to refine, add edge cases, or convert to BDD..."}
                        className="w-full bg-brand-navy/40 border-none pl-12 pr-4 py-4 rounded-xl text-white placeholder-slate-500 focus:ring-1 focus:ring-brand-blue/50 outline-none transition-all"
                    />
                </div>
                <button
                    type="submit"
                    disabled={!input.trim() || isProcessing}
                    className="p-4 bg-brand-blue text-brand-navy font-bold rounded-xl hover:bg-brand-neon transition-colors disabled:opacity-50 disabled:grayscale flex items-center justify-center group"
                >
                    <Wand2 className={`w-6 h-6 ${isProcessing ? 'animate-spin' : 'group-hover:rotate-12'} transition-transform`} />
                </button>
            </motion.form>
        </div>
    );
};
