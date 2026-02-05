import { useState } from 'react';
import { useProjectContext } from '../hooks/useProjectContext';
import { Building2, ChevronRight, Search } from 'lucide-react';
import { motion } from 'framer-motion';

const MOCK_PROJECTS = [
    { id: 'LEGEND-STACK', name: 'LegendStack Engine', key: 'LSE' },
    { id: 'AI-CORE', name: 'AI Core Infrastructure', key: 'AIC' },
    { id: 'FRONTEND-UX', name: 'Frontend UX Excellence', key: 'FUX' },
];

export const ProjectSelector = () => {
    const { setProject } = useProjectContext();
    const [searchTerm, setSearchTerm] = useState('');

    const filteredProjects = MOCK_PROJECTS.filter(p =>
        p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        p.key.toLowerCase().includes(searchTerm.toLowerCase())
    );

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-brand-navy/80 backdrop-blur-sm">
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="w-full max-w-2xl p-8 glass-card border-brand-blue/20 shadow-2xl"
            >
                <div className="flex items-center gap-3 mb-6">
                    <div className="p-3 rounded-lg bg-brand-blue/10">
                        <Building2 className="w-8 h-8 neon-text" />
                    </div>
                    <div>
                        <h1 className="text-3xl font-bold text-white tracking-tight">Active Project</h1>
                        <p className="text-slate-400">Select a JIRA project context to begin decomposition</p>
                    </div>
                </div>

                <div className="relative mb-6">
                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
                    <input
                        type="text"
                        placeholder="Search projects..."
                        className="w-full pl-12 pr-4 py-4 bg-brand-navy/50 border border-slate-700/50 rounded-xl focus:ring-2 focus:ring-brand-blue outline-none transition-all text-white"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        autoFocus
                    />
                </div>

                <div className="grid gap-3 max-h-[50vh] overflow-y-auto pr-2">
                    {filteredProjects.map((project, idx) => (
                        <motion.button
                            key={project.id}
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: idx * 0.1 }}
                            onClick={() => setProject(project.key)}
                            className="flex items-center justify-between p-5 glass hover:bg-brand-blue/5 rounded-xl border border-slate-700/50 transition-all group text-left"
                        >
                            <div className="flex flex-col items-start">
                                <span className="text-lg font-semibold text-white group-hover:neon-text transition-colors">
                                    {project.name}
                                </span>
                                <span className="text-sm text-slate-500 font-mono tracking-widest">{project.key}</span>
                            </div>
                            <ChevronRight className="w-5 h-5 text-slate-600 group-hover:text-brand-blue group-hover:translate-x-1 transition-all" />
                        </motion.button>
                    ))}
                </div>
            </motion.div>
        </div>
    );
};
