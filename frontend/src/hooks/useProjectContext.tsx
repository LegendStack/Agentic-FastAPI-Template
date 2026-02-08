import { createContext, useContext, useState, type ReactNode } from 'react';

interface EpicInfo {
    id: string;
    key: string;
    summary: string;
}

interface ProjectContextType {
    selectedProject: string | null;
    setProject: (id: string | null) => void;
    selectedEpic: EpicInfo | null;
    setSelectedEpic: (epic: EpicInfo | null) => void;
    clearContext: () => void;
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined);

export const ProjectProvider = ({ children }: { children: ReactNode }) => {
    const [selectedProject, setProjectState] = useState<string | null>(() => {
        return localStorage.getItem('selectedProject') || null;
    });

    const [selectedEpic, setSelectedEpicState] = useState<EpicInfo | null>(() => {
        const saved = localStorage.getItem('selectedEpic');
        try {
            return saved ? JSON.parse(saved) : null;
        } catch {
            return null;
        }
    });

    const setProject = (id: string | null) => {
        setProjectState(id);
        if (id) {
            localStorage.setItem('selectedProject', id);
            // If the current epic belongs to a different project, clear it
            if (selectedEpic && !selectedEpic.key.startsWith(id + '-')) {
                setSelectedEpic(null);
            }
        } else {
            localStorage.removeItem('selectedProject');
            setSelectedEpic(null); // If no project is selected, no epic should be selected either
        }
    };

    const setSelectedEpic = (epic: EpicInfo | null) => {
        setSelectedEpicState(epic);
        if (epic) {
            localStorage.setItem('selectedEpic', JSON.stringify(epic));
            // If we select an epic, ensure its project is also selected
            const projectKey = epic.key.split('-')[0];
            if (projectKey && projectKey !== selectedProject) {
                setProject(projectKey);
            }
        } else {
            localStorage.removeItem('selectedEpic');
        }
    };

    const clearContext = () => {
        setProject(null);
        setSelectedEpic(null);
        localStorage.removeItem('selectedProject');
        localStorage.removeItem('selectedEpic');
    };

    return (
        <ProjectContext.Provider value={{
            selectedProject,
            setProject,
            selectedEpic,
            setSelectedEpic,
            clearContext
        }}>
            {children}
        </ProjectContext.Provider>
    );
};

export const useProjectContext = () => {
    const context = useContext(ProjectContext);
    if (context === undefined) {
        throw new Error('useProjectContext must be used within a ProjectProvider');
    }
    return context;
};
