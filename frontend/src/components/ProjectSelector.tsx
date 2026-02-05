import { useState, useEffect } from 'react';
import { useProjectContext } from '../hooks/useProjectContext';
import { Building2, ChevronRight, Search, Loader2 } from 'lucide-react';
import { motion } from 'framer-motion';

export const ProjectSelector = () => {
    const { setProject } = useProjectContext();
    const [searchTerm, setSearchTerm] = useState('');
    const [projects, setProjects] = useState<any[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchProjects = async () => {
            try {
                setIsLoading(true);
                const response = await fetch('/api/v1/jira/projects');
                if (!response.ok) throw new Error('Failed to fetch projects');
                const data = await response.json();
                setProjects(data);
                setError(null);
            } catch (err: any) {
                console.error('Error fetching JIRA projects:', err);
                setError(err.message);
            } finally {
                setIsLoading(false);
            }
        };

        fetchProjects();
    }, []);

    const filteredProjects = projects.filter(p =>
        p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        p.key.toLowerCase().includes(searchTerm.toLowerCase())
    );

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/60 backdrop-blur-sm">
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="w-full max-w-2xl p-8 glass-card border-border-primary shadow-2xl"
            >
                <div className="flex items-center gap-3 mb-6">
                    <div className="p-3 rounded-lg bg-accent-primary/10">
                        <Building2 className="w-8 h-8 text-accent-primary" />
                    </div>
                    <div>
                        <h1 className="text-3xl font-bold text-text-primary tracking-tight">Active Project</h1>
                        <p className="text-text-secondary">Select a JIRA project context to begin decomposition</p>
                    </div>
                </div>

                <div className="relative mb-6">
                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-text-tertiary" />
                    <input
                        type="text"
                        placeholder="Search projects..."
                        className="w-full pl-12 pr-4 py-4 bg-bg-secondary/50 border border-border-primary rounded-xl focus:ring-2 focus:ring-accent-primary outline-none transition-all text-text-primary placeholder:text-text-tertiary"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        autoFocus
                    />
                </div>

                <div className="grid gap-3 max-h-[50vh] overflow-y-auto pr-2">
                    {isLoading ? (
                        <div className="flex flex-col items-center justify-center py-10">
                            <Loader2 className="w-10 h-10 text-brand-blue animate-spin mb-4" />
                            <p className="text-slate-500">Connecting to JIRA...</p>
                        </div>
                    ) : error ? (
                        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-center text-red-400">
                            <p className="font-bold mb-1">Connection Error</p>
                            <p className="text-xs">{error}</p>
                            <button
                                onClick={() => window.location.reload()}
                                className="mt-4 px-4 py-2 bg-red-500/20 hover:bg-red-500/30 rounded-lg transition-all text-[10px] uppercase tracking-widest"
                            >
                                Retry Connection
                            </button>
                        </div>
                    ) : filteredProjects.length > 0 ? (
                        filteredProjects.map((project, idx) => (
                            <motion.button
                                key={project.id}
                                initial={{ opacity: 0, x: -10 }}
                                animate={{ opacity: 1, x: 0 }}
                                transition={{ delay: idx * 0.1 }}
                                onClick={() => setProject(project.key)}
                                className="flex items-center justify-between p-5 glass hover:bg-accent-primary/5 rounded-xl border border-border-primary transition-all group text-left"
                            >
                                <div className="flex items-center gap-4">
                                    {project.avatar && (
                                        <img src={project.avatar} alt="" className="w-10 h-10 rounded-lg" />
                                    )}
                                    <div className="flex flex-col items-start">
                                        <span className="text-lg font-semibold text-text-primary group-hover:text-accent-primary transition-colors">
                                            {project.name}
                                        </span>
                                        <span className="text-sm text-text-tertiary font-mono tracking-widest">{project.key}</span>
                                    </div>
                                </div>
                                <ChevronRight className="w-5 h-5 text-text-tertiary group-hover:text-accent-primary group-hover:translate-x-1 transition-all" />
                            </motion.button>
                        ))
                    ) : (
                        <div className="py-10 text-center">
                            <p className="text-slate-500 italic">No projects found matching "{searchTerm}"</p>
                        </div>
                    )}
                </div>
            </motion.div>
        </div>
    );
};
