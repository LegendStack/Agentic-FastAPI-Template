import { createContext, useContext, useState, type ReactNode } from 'react';

interface ProjectContextType {
    selectedProject: string | null;
    setProject: (id: string | null) => void;
    selectedEpic: { id: string, key: string, summary: string } | null;
    setSelectedEpic: (epic: { id: string, key: string, summary: string } | null) => void;
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined);

export const ProjectProvider = ({ children }: { children: ReactNode }) => {
    const [selectedProject, setProjectState] = useState<string | null>(() => {
        return localStorage.getItem('selectedProject') || null;
    });

    const [selectedEpic, setSelectedEpicState] = useState<{ id: string, key: string, summary: string } | null>(() => {
        const saved = localStorage.getItem('selectedEpic');
        return saved ? JSON.parse(saved) : null;
    });

    const setProject = (id: string | null) => {
        setProjectState(id);
        if (id) {
            localStorage.setItem('selectedProject', id);
        } else {
            localStorage.removeItem('selectedProject');
            setSelectedEpic(null); // Clear epic if project changes
        }
    };

    const setSelectedEpic = (epic: { id: string, key: string, summary: string } | null) => {
        setSelectedEpicState(epic);
        if (epic) {
            localStorage.setItem('selectedEpic', JSON.stringify(epic));
        } else {
            localStorage.removeItem('selectedEpic');
        }
    };

    return (
        <ProjectContext.Provider value={{ selectedProject, setProject, selectedEpic, setSelectedEpic }}>
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
