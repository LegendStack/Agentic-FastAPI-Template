import api from '../api/client';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { DollarSign, BarChart3, Clock, X } from 'lucide-react';

interface TokenUsage {
    total_input_tokens: number;
    total_output_tokens: number;
    total_conversations: number;
    total_messages: number;
    estimated_cost: number;
}

interface ValueDashboardProps {
    onClose: () => void;
}

export const ValueDashboard = ({ onClose }: ValueDashboardProps) => {
    const { data: metrics, isLoading } = useQuery<TokenUsage>({
        queryKey: ['tokenUsage'],
        queryFn: async () => {
            const response = await api.get('/admin/metrics/token-usage');
            return response.data;
        },
        refetchInterval: 30000,
    });

    const MANUAL_COST_PER_EPIC = 150.00; // Estimated cost for a human to decompose an epic
    const TIME_SAVED_PER_EPIC_HOURS = 2.5; // Estimated hours saved per epic

    const totalSavings = metrics ? (metrics.total_conversations * MANUAL_COST_PER_EPIC) - metrics.estimated_cost : 0;
    const hoursSaved = metrics ? metrics.total_conversations * TIME_SAVED_PER_EPIC_HOURS : 0;
    const roi = metrics?.estimated_cost ? (totalSavings / metrics.estimated_cost) * 100 : 0;

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
        >
            <div className="bg-bg-primary border border-border-primary w-full max-w-4xl max-h-[90vh] rounded-3xl overflow-hidden flex flex-col shadow-2xl">
                <div className="p-6 border-b border-border-primary flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="p-2 rounded-xl bg-accent-primary/10">
                            <BarChart3 className="w-6 h-6 text-accent-primary" />
                        </div>
                        <div>
                            <h2 className="text-2xl font-bold text-text-primary">Value Realization</h2>
                            <p className="text-sm text-text-secondary">Return on Investment Overview</p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-bg-tertiary rounded-full text-text-secondary transition-colors"
                    >
                        <X className="w-6 h-6" />
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto p-6">
                    {isLoading ? (
                        <div className="h-64 flex items-center justify-center text-text-secondary animate-pulse">
                            Loading metrics...
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                            {/* Card 1: Total Cost */}
                            <div className="p-6 rounded-2xl bg-bg-secondary border border-border-primary">
                                <div className="flex items-center justify-between mb-4">
                                    <span className="text-text-secondary text-sm font-medium">AI Cost</span>
                                    <DollarSign className="w-5 h-5 text-red-400" />
                                </div>
                                <div className="text-3xl font-bold text-text-primary mb-1">
                                    ${metrics?.estimated_cost.toFixed(4)}
                                </div>
                                <div className="text-xs text-text-tertiary">
                                    {metrics?.total_input_tokens.toLocaleString()} in / {metrics?.total_output_tokens.toLocaleString()} out
                                </div>
                            </div>

                            {/* Card 2: Estimated Savings */}
                            <div className="p-6 rounded-2xl bg-bg-secondary border border-border-primary ring-1 ring-accent-primary/20">
                                <div className="flex items-center justify-between mb-4">
                                    <span className="text-text-secondary text-sm font-medium">Est. Savings</span>
                                    <DollarSign className="w-5 h-5 text-emerald-400" />
                                </div>
                                <div className="text-3xl font-bold text-emerald-400 mb-1">
                                    ${totalSavings.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                </div>
                                <div className="text-xs text-emerald-400/70">
                                    Based on ${MANUAL_COST_PER_EPIC}/epic manual cost
                                </div>
                            </div>

                            {/* Card 3: Time Saved */}
                            <div className="p-6 rounded-2xl bg-bg-secondary border border-border-primary">
                                <div className="flex items-center justify-between mb-4">
                                    <span className="text-text-secondary text-sm font-medium">Time Saved</span>
                                    <Clock className="w-5 h-5 text-blue-400" />
                                </div>
                                <div className="text-3xl font-bold text-text-primary mb-1">
                                    {hoursSaved.toFixed(1)}h
                                </div>
                                <div className="text-xs text-text-tertiary">
                                    Across {metrics?.total_conversations} conversations
                                </div>
                            </div>

                            {/* Large Card: ROI Summary */}
                            <div className="md:col-span-3 p-8 rounded-3xl bg-gradient-to-br from-accent-primary/10 to-transparent border border-accent-primary/20 mt-4">
                                <h3 className="text-lg font-bold text-text-primary mb-2">ROI Impact</h3>
                                <div className="flex items-baseline gap-2">
                                    <span className="text-5xl font-black text-accent-primary">
                                        {roi > 0 ? roi.toLocaleString(undefined, { maximumFractionDigits: 0 }) : 0}%
                                    </span>
                                    <span className="text-text-secondary">Return on Investment</span>
                                </div>
                                <p className="mt-4 text-sm text-text-secondary max-w-xl">
                                    By automating story decomposition, you are saving approximately <strong>${(MANUAL_COST_PER_EPIC - (metrics?.estimated_cost || 0) / (metrics?.total_conversations || 1)).toFixed(2)}</strong> per epic compared to manual analysis.
                                </p>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </motion.div>
    );
};
