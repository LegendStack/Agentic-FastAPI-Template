import { motion } from 'framer-motion';
import { Copy, Check } from 'lucide-react';
import type { Message } from '../hooks/useBacklog';
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';

interface MessageListProps {
    messages: Message[];
}

export const MessageList = ({ messages }: MessageListProps) => {
    if (messages.length === 0) return null;

    const formatTokens = (val?: number) => {
        if (!val) return '0';
        if (val >= 1000) return `${(val / 1000).toFixed(1)}k`;
        return val.toString();
    };

    return (
        <div className="max-w-5xl mx-auto px-12 pt-8 flex flex-col gap-8">
            {messages.map((msg, idx) => (
                <motion.div
                    key={msg.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.1 }}
                    className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
                >
                    <div className={`relative px-6 py-4 rounded-2xl transition-all group ${msg.role === 'user'
                        ? 'max-w-[80%] bg-accent-primary/10 text-text-primary rounded-tr-none shadow-xl backdrop-blur-md border border-accent-primary/20'
                        : 'w-full bg-transparent text-text-primary rounded-tl-none border-b border-border-primary/30 pb-8'
                        }`}>
                        <div className="relative">
                            {msg.role === 'assistant' ? (
                                <div className="prose prose-invert max-w-none prose-p:leading-relaxed prose-p:text-text-primary/95 prose-a:text-accent-primary prose-a:no-underline hover:prose-a:underline prose-strong:text-accent-primary prose-ul:list-disc prose-ul:pl-4">
                                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                                </div>
                            ) : (
                                <p className="text-sm leading-relaxed whitespace-pre-wrap">
                                    {msg.content}
                                </p>
                            )}

                            <div className={`absolute bottom-[-24px] flex items-center gap-4 ${msg.role === 'user' ? 'right-0' : 'left-0'}`}>
                                <CopyButton content={msg.content} role={msg.role} />

                                {msg.role === 'assistant' && (msg.input_tokens || msg.output_tokens) && (
                                    <div className="text-[10px] text-text-tertiary font-mono tracking-tighter bg-bg-tertiary/30 px-2 py-0.5 rounded border border-border-primary/50">
                                        {formatTokens(msg.input_tokens)} in • {formatTokens(msg.output_tokens)} out
                                    </div>
                                )}
                            </div>
                        </div>
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

const CopyButton = ({ content, role }: { content: string, role: string }) => {
    const [copied, setCopied] = useState(false);

    const handleCopy = async () => {
        await navigator.clipboard.writeText(content);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <button
            onClick={handleCopy}
            className={`flex items-center gap-1.5 px-2 py-1 rounded transition-all text-text-tertiary hover:text-accent-primary hold ${role === 'assistant'
                ? 'opacity-100'
                : 'opacity-0 group-hover:opacity-100'
                }`}
            title="Copy to clipboard"
        >
            {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
            <span className="text-[9px] font-bold uppercase tracking-wider">{copied ? 'Copied' : 'Copy'}</span>
        </button>
    );
};
