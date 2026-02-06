import { useState, useEffect } from 'react';
import { useProjectContext } from '../hooks/useProjectContext';
import { Building2, ChevronRight, Search, Loader2, ScrollText, ArrowLeft, Check } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface ProjectSelectorProps {
    onClose?: () => void;
}

export const ProjectSelector = ({ onClose }: ProjectSelectorProps) => {
    const { selectedProject, setProject, selectedEpic, setSelectedEpic } = useProjectContext();
    const [step, setStep] = useState<'project' | 'epic'>(selectedProject ? 'epic' : 'project');
    const [searchTerm, setSearchTerm] = useState('');
    const [projects, setProjects] = useState<any[]>([]);
    const [epics, setEpics] = useState<any[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isLoadingEpics, setIsLoadingEpics] = useState(false);
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

    const fetchEpics = async (projectKey: string) => {
        try {
            setIsLoadingEpics(true);
            const response = await fetch(`/api/v1/jira/projects/${projectKey}/epics`);
            if (!response.ok) throw new Error('Failed to fetch epics');
            const data = await response.json();
            setEpics(data);
        } catch (err: any) {
            console.error('Error fetching JIRA epics:', err);
            setEpics([]);
        } finally {
            setIsLoadingEpics(false);
        }
    };

    useEffect(() => {
        if (step === 'epic' && selectedProject) {
            fetchEpics(selectedProject);
        }
    }, [step, selectedProject]);

    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape' && selectedProject && onClose) {
                onClose();
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [selectedProject, onClose]);

    const handleBackdropClick = () => {
        if (selectedProject && onClose) {
            onClose();
        }
    };

    const handleProjectSelect = (key: string) => {
        setProject(key);
        setSearchTerm('');
        setStep('epic');
    };

    const handleEpicSelect = (epic: any) => {
        setSelectedEpic(epic);
        if (onClose) onClose();
    };

    const filteredProjects = projects.filter(p =>
        p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        p.key.toLowerCase().includes(searchTerm.toLowerCase())
    );

    const filteredEpics = epics.filter(e =>
        e.summary.toLowerCase().includes(searchTerm.toLowerCase()) ||
        e.key.toLowerCase().includes(searchTerm.toLowerCase())
    );

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/60 backdrop-blur-sm"
            onClick={handleBackdropClick}
        >
            <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="w-full max-w-2xl p-8 glass-card border-border-primary shadow-2xl overflow-hidden"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="flex items-center justify-between mb-8">
                    <div className="flex items-center gap-4">
                        <div className="p-3 rounded-xl bg-accent-primary/10">
                            {step === 'project' ?
                                <Building2 className="w-8 h-8 text-accent-primary" /> :
                                <ScrollText className="w-8 h-8 text-accent-primary" />
                            }
                        </div>
                        <div>
                            <h1 className="text-3xl font-bold text-text-primary tracking-tight">
                                {step === 'project' ? 'Active Project' : 'Select Epic'}
                            </h1>
                            <p className="text-text-secondary text-sm">
                                {step === 'project'
                                    ? 'Select a JIRA project context to begin decomposition'
                                    : `Browsing Epics for ${selectedProject}`
                                }
                            </p>
                        </div>
                    </div>
                    {step === 'epic' && (
                        <button
                            onClick={() => setStep('project')}
                            className="p-2 hover:bg-white/5 rounded-lg transition-colors text-text-tertiary hover:text-text-primary flex items-center gap-2 text-xs font-semibold uppercase tracking-wider"
                        >
                            <ArrowLeft className="w-4 h-4" />
                            Back
                        </button>
                    )}
                </div>

                <div className="relative mb-6">
                    <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-text-tertiary" />
                    <input
                        type="text"
                        placeholder={step === 'project' ? "Search projects..." : "Search epics..."}
                        className="w-full pl-12 pr-4 py-4 bg-bg-secondary/50 border border-border-primary rounded-xl focus:ring-2 focus:ring-accent-primary outline-none transition-all text-text-primary placeholder:text-text-tertiary"
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        autoFocus
                    />
                </div>

                <AnimatePresence mode="wait">
                    <motion.div
                        key={step}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                        className="grid gap-3 max-h-[45vh] overflow-y-auto pr-2 custom-scrollbar"
                    >
                        {step === 'project' ? (
                            isLoading ? (
                                <div className="flex flex-col items-center justify-center py-10">
                                    <Loader2 className="w-10 h-10 text-accent-primary animate-spin mb-4" />
                                    <p className="text-text-tertiary">Connecting to JIRA...</p>
                                </div>
                            ) : error ? (
                                <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-center text-red-400">
                                    <p className="font-bold mb-1">Connection Error</p>
                                    <p className="text-xs">{error}</p>
                                    <button
                                        onClick={() => window.location.reload()}
                                        className="mt-4 px-4 py-2 bg-red-500/20 hover:bg-red-500/30 rounded-lg transition-all text-xs font-bold uppercase tracking-widest"
                                    >
                                        Retry Connection
                                    </button>
                                </div>
                            ) : filteredProjects.length > 0 ? (
                                filteredProjects.map((project) => (
                                    <button
                                        key={project.id}
                                        onClick={() => handleProjectSelect(project.key)}
                                        className={`flex items-center justify-between p-5 rounded-xl border transition-all group text-left ${selectedProject === project.key
                                            ? 'bg-accent-primary/10 border-accent-primary/30 ring-1 ring-accent-primary/20'
                                            : 'glass border-border-primary hover:bg-accent-primary/5 hover:border-accent-primary/20'
                                            }`}
                                    >
                                        <div className="flex items-center gap-4">
                                            {project.avatar ? (
                                                <img src={project.avatar} alt="" className="w-10 h-10 rounded-lg shadow-sm" />
                                            ) : (
                                                <div className="w-10 h-10 rounded-lg bg-bg-tertiary flex items-center justify-center">
                                                    <Building2 className="w-5 h-5 text-text-tertiary" />
                                                </div>
                                            )}
                                            <div className="flex flex-col items-start leading-tight">
                                                <span className={`text-lg font-bold transition-colors ${selectedProject === project.key ? 'text-accent-primary' : 'text-text-primary'
                                                    }`}>
                                                    {project.name}
                                                </span>
                                                <span className="text-xs text-text-tertiary font-mono uppercase tracking-widest">{project.key}</span>
                                            </div>
                                        </div>
                                        {selectedProject === project.key ? (
                                            <Check className="w-5 h-5 text-accent-primary" />
                                        ) : (
                                            <ChevronRight className="w-5 h-5 text-text-tertiary group-hover:text-accent-primary group-hover:translate-x-1 transition-all" />
                                        )}
                                    </button>
                                ))
                            ) : (
                                <div className="py-10 text-center">
                                    <p className="text-text-tertiary italic">No projects found matching "{searchTerm}"</p>
                                </div>
                            )
                        ) : (
                            // EPICS STEP
                            isLoadingEpics ? (
                                <div className="flex flex-col items-center justify-center py-10">
                                    <Loader2 className="w-10 h-10 text-accent-primary animate-spin mb-4" />
                                    <p className="text-text-tertiary">Fetching Epics...</p>
                                </div>
                            ) : epics.length === 0 ? (
                                <div className="py-10 text-center flex flex-col items-center">
                                    <ScrollText className="w-12 h-12 text-text-tertiary/20 mb-4" />
                                    <p className="text-text-tertiary mb-6">No Epics found in this project.</p>
                                    <button
                                        onClick={() => handleEpicSelect(null)}
                                        className="px-6 py-3 bg-accent-primary/10 hover:bg-accent-primary/20 text-accent-primary rounded-xl font-bold transition-all border border-accent-primary/30"
                                    >
                                        Continue without Epic
                                    </button>
                                </div>
                            ) : (
                                <>
                                    <button
                                        onClick={() => handleEpicSelect(null)}
                                        className="mb-4 flex items-center justify-center p-4 rounded-xl border border-dashed border-text-tertiary/30 hover:border-accent-primary/50 hover:bg-accent-primary/5 text-text-tertiary hover:text-accent-primary transition-all font-semibold italic text-sm"
                                    >
                                        -- No Epic (Stand-alone Stories) --
                                    </button>
                                    {filteredEpics.length > 0 ? filteredEpics.map((epic) => (
                                        <button
                                            key={epic.id}
                                            onClick={() => handleEpicSelect(epic)}
                                            className={`flex items-center justify-between p-4 rounded-xl border transition-all group text-left ${selectedEpic?.key === epic.key
                                                ? 'bg-accent-primary/10 border-accent-primary/30 ring-1 ring-accent-primary/20'
                                                : 'glass border-border-primary hover:bg-accent-primary/5 hover:border-accent-primary/20'
                                                }`}
                                        >
                                            <div className="flex flex-col items-start leading-tight pr-4">
                                                <span className={`text-md font-bold transition-colors line-clamp-1 ${selectedEpic?.key === epic.key ? 'text-accent-primary' : 'text-text-primary'
                                                    }`}>
                                                    {epic.summary}
                                                </span>
                                                <div className="flex items-center gap-2 mt-1">
                                                    <span className="text-[10px] text-text-tertiary font-mono uppercase tracking-widest">{epic.key}</span>
                                                    <span className={`text-[9px] px-1.5 py-0.5 rounded-md bg-white/5 text-text-tertiary uppercase font-bold`}>
                                                        {epic.status}
                                                    </span>
                                                </div>
                                            </div>
                                            {selectedEpic?.key === epic.key ? (
                                                <Check className="w-5 h-5 text-accent-primary flex-shrink-0" />
                                            ) : (
                                                <ChevronRight className="w-5 h-5 text-text-tertiary group-hover:text-accent-primary group-hover:translate-x-1 transition-all flex-shrink-0" />
                                            )}
                                        </button>
                                    )) : (
                                        <div className="py-10 text-center">
                                            <p className="text-text-tertiary italic">No epics match search.</p>
                                        </div>
                                    )}
                                </>
                            )
                        )}
                    </motion.div>
                </AnimatePresence>

                {step === 'epic' && !isLoadingEpics && epics.length > 0 && (
                    <div className="mt-8 pt-6 border-t border-border-primary flex justify-end">
                        <button
                            onClick={() => handleEpicSelect(null)}
                            className="text-text-tertiary hover:text-text-primary text-xs font-bold uppercase tracking-widest transition-colors"
                        >
                            Skip Epic Selection
                        </button>
                    </div>
                )}
            </motion.div>
        </div>
    );
};
