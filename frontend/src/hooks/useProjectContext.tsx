import { createContext, useContext, useState, type ReactNode } from 'react';

interface ProjectContextType {
    selectedProject: string | null;
    setProject: (id: string | null) => void;
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined);

export const ProjectProvider = ({ children }: { children: ReactNode }) => {
    const [selectedProject, setProjectState] = useState<string | null>(() => {
        return localStorage.getItem('selectedProject') || null;
    });

    const setProject = (id: string | null) => {
        setProjectState(id);
        if (id) {
            localStorage.setItem('selectedProject', id);
        } else {
            localStorage.removeItem('selectedProject');
        }
    };

    return (
        <ProjectContext.Provider value={{ selectedProject, setProject }}>
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
