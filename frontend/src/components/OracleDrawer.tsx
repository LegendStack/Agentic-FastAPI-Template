import { useState, useRef, useEffect } from 'react';
import { Wand2, Sparkles, UploadCloud } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { toast } from 'sonner';
import { RecommendationList } from './RecommendationList';

interface OracleDrawerProps {
    onSendMessage: (message: string) => void;
    isProcessing: boolean;
    recommendations?: string[];
    onImport?: (file: File) => Promise<any>;
    isImporting?: boolean;
    prefillMessage?: string | null;
    onClearPrefill?: () => void;
    isLocked?: boolean;
    isMinimized?: boolean;
}

export const OracleDrawer = ({
    onSendMessage,
    isProcessing,
    recommendations = [],
    onImport,
    isImporting = false,
    prefillMessage,
    onClearPrefill,
    isLocked = false,
    isMinimized = false
}: OracleDrawerProps) => {
    const [input, setInput] = useState('');
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Effect to handle prefill message from parent
    useEffect(() => {
        if (prefillMessage) {
            setInput(prefillMessage);
            // Optionally notify parent we consumed it
            if (onClearPrefill) onClearPrefill();
        }
    }, [prefillMessage, onClearPrefill]);

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (input.trim() && !isProcessing && !isImporting && !isLocked) {
            onSendMessage(input);
            setInput('');
        }
    };

    const handleSuggestClick = (suggestion: string) => {
        if (!isProcessing && !isImporting) {
            onSendMessage(suggestion);
        }
    };

    const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files?.[0] && onImport) {
            try {
                const result = await onImport(e.target.files[0]);
                if (result.epic_description) {
                    // Append or replace? Let's replace for now or append if empty
                    setInput(prev => prev ? prev + "\n\n" + result.epic_description : result.epic_description);
                }
            } catch (err) {
                console.error("Import failed", err);
                toast.error('Import failed', { description: 'Could not parse the selected file.' });
            }
            // Reset input
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    };

    return (
        <div className="w-full p-6 flex flex-col items-center pointer-events-none mt-auto sticky bottom-0 z-30">
            <AnimatePresence>
                {recommendations.length > 0 && !isProcessing && !isImporting && (
                    <RecommendationList
                        recommendations={recommendations}
                        onSelect={handleSuggestClick}
                        disabled={isProcessing || isImporting}
                    />
                )}
            </AnimatePresence>

            <motion.form
                onSubmit={handleSubmit}
                initial={{ y: 20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                className="w-full max-w-3xl mx-auto glass p-3 rounded-3xl shadow-2xl flex flex-col gap-3 pointer-events-auto border-accent-primary/20"
            >
                <div className="flex gap-3 items-end">
                    <div className="flex-1 relative">
                        <Sparkles className={`absolute left-4 top-5 w-5 h-5 ${isProcessing || isImporting ? 'text-accent-primary animate-spin' : 'text-text-secondary'}`} />
                        <textarea
                            rows={3}
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter' && !e.shiftKey) {
                                    e.preventDefault();
                                    handleSubmit(e as any);
                                }
                            }}
                            disabled={isProcessing || isImporting || isLocked}
                            placeholder={
                                isLocked
                                    ? "This conversation is locked (Exported to JIRA)"
                                    : isProcessing
                                        ? "Oracle is refining..."
                                        : isImporting
                                            ? "Parsing document..."
                                            : "Ask the agent to refine, add edge cases, or convert to BDD..."
                            }
                            className="w-full bg-bg-primary/40 border-none pl-12 pr-4 py-4 rounded-2xl text-text-primary placeholder-text-secondary focus:ring-1 focus:ring-accent-primary/40 outline-none transition-all disabled:opacity-70 resize-none custom-scrollbar min-h-[120px]"
                        />
                    </div>

                    <div className="flex flex-col gap-2">
                        {onImport && (
                            <>
                                <input
                                    type="file"
                                    ref={fileInputRef}
                                    className="hidden"
                                    accept=".pdf,.docx,.txt"
                                    onChange={handleFileSelect}
                                />
                                <button
                                    type="button"
                                    onClick={() => fileInputRef.current?.click()}
                                    disabled={isProcessing || isImporting || isLocked}
                                    className="p-3 bg-bg-tertiary text-text-secondary rounded-xl hover:bg-bg-secondary hover:text-text-primary transition-colors disabled:opacity-50 flex items-center justify-center shrink-0 border border-border-primary"
                                    title={isLocked ? "Locked" : "Upload Spec (PDF/Docx)"}
                                >
                                    <UploadCloud className={`w-5 h-5 ${isImporting ? 'animate-bounce' : ''}`} />
                                </button>
                            </>
                        )}

                        <button
                            type="submit"
                            disabled={!input.trim() || isProcessing || isImporting || isLocked}
                            className="p-3 bg-teal-600 dark:bg-cyan-400 text-white dark:text-slate-900 font-bold rounded-xl hover:bg-teal-700 dark:hover:bg-cyan-300 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center group shadow-[0_0_20px_rgba(13,148,136,0.2)] dark:shadow-[0_0_20px_rgba(100,255,218,0.2)] hover:shadow-teal-500/40 dark:hover:shadow-cyan-400/40 shrink-0 flex-1 active:scale-95"
                        >
                            <Wand2
                                className={`w-5 h-5 ${isProcessing ? 'animate-spin' : 'group-hover:rotate-12'} transition-transform`}
                                strokeWidth={2.5}
                            />
                        </button>
                    </div>
                </div>
                {!isMinimized && !isLocked && (
                    <div className="px-4 pb-1 flex justify-between items-center text-[10px] text-text-tertiary font-medium uppercase tracking-widest">
                        <div className="flex gap-4">
                            <span><b>Enter</b> to send</span>
                            <span><b>Shift + Enter</b> for new line</span>
                        </div>
                        {input.length > 0 && <span>{input.length} characters</span>}
                    </div>
                )}
            </motion.form>
        </div>
    );
};
