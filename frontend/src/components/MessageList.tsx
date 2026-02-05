import { motion } from 'framer-motion';
import { User, Sparkles } from 'lucide-react';
import type { Message } from '../hooks/useBacklog';

interface MessageListProps {
    messages: Message[];
}

export const MessageList = ({ messages }: MessageListProps) => {
    if (messages.length === 0) return null;

    return (
        <div className="max-w-4xl mx-auto px-12 pt-8 flex flex-col gap-6">
            {messages.map((msg, idx) => (
                <motion.div
                    key={msg.id}
                    initial={{ opacity: 0, x: msg.role === 'user' ? 20 : -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: idx * 0.1 }}
                    className={`flex gap-4 ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}
                >
                    <div className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 shadow-lg ${msg.role === 'user' ? 'bg-accent-primary/20 text-accent-primary' : 'bg-bg-tertiary text-text-secondary border border-border-primary'
                        }`}>
                        {msg.role === 'user' ? <User className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}
                    </div>

                    <div className={`relative max-w-[80%] px-6 py-4 rounded-2xl transition-all shadow-xl backdrop-blur-md ${msg.role === 'user'
                        ? 'bg-accent-primary/10 text-text-primary rounded-tr-none'
                        : 'bg-bg-tertiary/50 text-text-primary border border-border-primary rounded-tl-none'
                        }`}>
                        <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>

                        {/* Decorative tail - Only for assistant */}
                        {msg.role !== 'user' && (
                            <div className="absolute top-0 w-4 h-4 -left-1 bg-bg-tertiary/50 border-l border-t border-border-primary -rotate-45 -z-10" style={{ clipPath: 'polygon(0 0, 100% 0, 100% 100%)' }} />
                        )}
                    </div>
                </motion.div>
            ))}

            {/* Divider */}
            <div className="flex items-center gap-4 my-4 opacity-20">
                <div className="h-px flex-1 bg-border-primary" />
                <span className="text-[10px] uppercase tracking-widest text-text-secondary font-bold">Generated Stories</span>
                <div className="h-px flex-1 bg-border-primary" />
            </div>
        </div>
    );
};
