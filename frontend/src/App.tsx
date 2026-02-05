import { useState } from 'react';
import { PublicClientApplication } from '@azure/msal-browser';
import { MsalProvider, AuthenticatedTemplate, UnauthenticatedTemplate, useMsal } from '@azure/msal-react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { msalConfig, loginRequest } from './authConfig';
import { ThemeProvider } from './contexts/ThemeProvider';
import { ThemeToggle } from './components/ThemeToggle';
import { ProjectProvider, useProjectContext } from './hooks/useProjectContext';
import { ProjectSelector } from './components/ProjectSelector';
import { OracleDrawer } from './components/OracleDrawer';
import { ConversationHistory } from './components/ConversationHistory';
import { MessageList } from './components/MessageList';
import { ArtifactBoard } from './components/ArtifactBoard';
import { useBacklog } from './hooks/useBacklog';
import { Layers, LogOut, User, LayoutDashboard, Sparkles, ChevronLeft, BarChart3 } from 'lucide-react';
import { ValueDashboard } from './components/ValueDashboard';
import { motion } from 'framer-motion';
import { Panel, Group as PanelGroup, Separator as PanelResizeHandle, usePanelRef } from 'react-resizable-panels';

const msalInstance = new PublicClientApplication(msalConfig);
const queryClient = new QueryClient();

const Dashboard = () => {
  const { instance, accounts } = useMsal();
  const { selectedProject, setProject } = useProjectContext();
  const artifactPanelRef = usePanelRef();
  const [isArtifactCollapsed, setIsArtifactCollapsed] = useState(false);
  const [isValueDashboardOpen, setIsValueDashboardOpen] = useState(false);
  const {
    stories,
    setStories,
    messages,
    versions,
    activeVersionId,
    loadVersion,
    isProcessing,
    sendMessage,
    updateStoryLocally,
    currentThreadId,
    loadThread,
    recommendations,
    reset,
    jiraBaseUrl
  } = useBacklog();

  const handleSelectThread = async (threadId: string) => {
    const data = await loadThread(threadId);
    if (data?.metadata?.project_key) {
      setProject(data.metadata.project_key);
    }
  };

  const handleRefine = (message: string) => {
    sendMessage({ message, localStories: stories });
  };

  const handleNewConversation = () => {
    const url = new URL(window.location.href);
    url.searchParams.delete('thread');
    window.history.pushState({}, '', url);
    reset();
  };

  const deleteStory = (id: string) => {
    setStories(prev => prev.filter(s => s.id !== id));
  };

  return (
    <div className="flex h-screen bg-bg-primary overflow-hidden transition-colors duration-300">
      {/* Sidebar */}
      <aside className="w-72 border-r border-border-primary flex flex-col glass z-10 shrink-0">
        <div className="p-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-brand-blue bg-opacity-20">
              <Layers className="w-6 h-6 neon-text" />
            </div>
            <span className="font-bold text-xl text-text-primary tracking-tighter">BACKLOG.AI</span>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setIsValueDashboardOpen(true)}
              className="p-2 hover:bg-bg-tertiary rounded-lg text-text-secondary hover:text-emerald-400 transition-all"
              title="ROI Metrics"
            >
              <BarChart3 className="w-5 h-5" />
            </button>
            <ThemeToggle />
          </div>
        </div>

        <div className="px-4 mt-4">
          <button
            onClick={() => setProject(null)}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all text-text-secondary hover:text-accent-primary hover:bg-accent-primary/10 border border-border-primary hover:border-accent-primary/30"
          >
            <LayoutDashboard className="w-5 h-5" />
            <div className="flex-1 flex items-center justify-between">
              <span className="text-sm font-semibold">Change Project</span>
              {selectedProject && (
                <span className="text-[10px] text-accent-primary font-mono">{selectedProject}</span>
              )}
            </div>
          </button>
        </div>

        <div className="flex-1 overflow-hidden flex flex-col border-t border-border-primary mt-4">
          <ConversationHistory
            onSelectThread={handleSelectThread}
            onNewConversation={handleNewConversation}
            currentThreadId={currentThreadId}
          />
        </div>

        <div className="p-4 border-t border-border-primary flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 overflow-hidden min-w-0">
            <div className="w-8 h-8 rounded-full bg-bg-tertiary flex items-center justify-center text-xs text-text-primary shrink-0 border border-border-primary/50">
              <User className="w-4 h-4" />
            </div>
            <span className="text-sm font-bold text-text-primary truncate">
              {accounts[0]?.name ? accounts[0].name.split(' ')[0] : (accounts[0]?.username?.split('@')[0] || 'User')}
            </span>
          </div>
          <button
            onClick={() => instance.logoutRedirect()}
            className="p-2 hover:bg-bg-tertiary rounded-lg text-text-secondary hover:text-red-400 transition-all shrink-0"
            title="Sign Out"
          >
            <LogOut className="w-5 h-5" />
          </button>
        </div>
      </aside>

      {/* Main Content: Resizable Split View */}
      <div className="flex-1 flex overflow-hidden">
        <PanelGroup orientation="horizontal">
          <Panel defaultSize={40} minSize={25}>
            <main className="h-full flex flex-col border-r border-border-primary bg-bg-secondary/20 relative">
              <header className="px-8 py-6 flex items-center justify-between border-b border-border-primary shrink-0">
                <h2 className="text-xl font-bold text-text-primary flex items-center gap-2">
                  Refinement
                  <Sparkles className="w-4 h-4 text-accent-primary" />
                  {selectedProject && (
                    <span className="ml-2 px-2 py-0.5 rounded-md bg-accent-primary/10 border border-accent-primary/30 text-[10px] uppercase tracking-tighter text-accent-primary font-mono align-middle">
                      {jiraBaseUrl ? (
                        <a
                          href={`${jiraBaseUrl}/projects/${selectedProject}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="hover:underline"
                        >
                          {selectedProject}
                        </a>
                      ) : selectedProject}
                    </span>
                  )}
                </h2>
                <button
                  onClick={handleNewConversation}
                  className="text-[10px] font-bold text-text-secondary hover:text-text-primary transition-colors"
                >
                  Reset
                </button>
              </header>

              <div className="flex-1 overflow-y-auto no-scrollbar scroll-smooth">
                <MessageList messages={messages} />
                {isProcessing && (
                  <div className="px-12 py-4 flex gap-4">
                    <div className="w-8 h-8 rounded-xl bg-bg-tertiary flex items-center justify-center shrink-0 border border-border-primary">
                      <Sparkles className="w-4 h-4 text-accent-primary animate-spin" />
                    </div>
                    <div className="bg-bg-tertiary/50 px-6 py-4 rounded-2xl border border-border-primary">
                      <div className="flex gap-1">
                        <div className="w-1.5 h-1.5 bg-accent-primary rounded-full animate-bounce [animation-delay:-0.3s]" />
                        <div className="w-1.5 h-1.5 bg-accent-primary rounded-full animate-bounce [animation-delay:-0.15s]" />
                        <div className="w-1.5 h-1.5 bg-accent-primary rounded-full animate-bounce" />
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <OracleDrawer
                onSendMessage={handleRefine}
                isProcessing={isProcessing}
                recommendations={recommendations}
              />
            </main>
          </Panel>

          <PanelResizeHandle className="w-1 bg-border-primary hover:bg-accent-primary/50 transition-colors cursor-col-resize flex items-center justify-center group relative">
            <div className="w-px h-8 bg-text-tertiary group-hover:bg-accent-primary/50" />
            <div className="absolute -inset-x-2 h-full cursor-col-resize z-50" />
          </PanelResizeHandle>

          {isArtifactCollapsed && (
            <button
              onClick={() => artifactPanelRef.current?.expand()}
              className="fixed right-0 top-1/2 -translate-y-1/2 p-3 bg-brand-blue text-brand-navy rounded-l-2xl shadow-[0_0_30px_rgba(100,255,218,0.3)] z-50 hover:bg-brand-neon transition-all hover:pr-5 group border border-brand-blue/50"
              title="Expand Backlog"
            >
              <ChevronLeft className="w-6 h-6 group-hover:scale-110 transition-transform" />
            </button>
          )}

          <Panel
            defaultSize={60}
            minSize={20}
            collapsible
            panelRef={artifactPanelRef}
            onResize={(size) => {
              if (size.asPercentage === 0) setIsArtifactCollapsed(true);
              else if (isArtifactCollapsed) setIsArtifactCollapsed(false);
            }}
          >
            <div className="h-full overflow-hidden">
              <ArtifactBoard
                stories={stories}
                versions={versions}
                activeVersionId={activeVersionId}
                projectName={selectedProject}
                jiraBaseUrl={jiraBaseUrl}
                onLoadVersion={loadVersion}
                onUpdateStory={updateStoryLocally}
                onDeleteStory={deleteStory}
                onCollapse={() => artifactPanelRef.current?.collapse()}
              />
            </div>
          </Panel>
        </PanelGroup>
      </div>

      {isValueDashboardOpen && <ValueDashboard onClose={() => setIsValueDashboardOpen(false)} />}
    </div>
  );
};

const AuthWrapper = () => {
  const { instance } = useMsal();
  const { selectedProject } = useProjectContext();
  const bypassAuth = import.meta.env.VITE_BYPASS_AUTH === 'true';

  if (bypassAuth) {
    return (
      <>
        <Dashboard />
        {!selectedProject && <ProjectSelector />}
      </>
    );
  }

  return (
    <>
      <AuthenticatedTemplate>
        <Dashboard />
        {!selectedProject && <ProjectSelector />}
      </AuthenticatedTemplate>
      <UnauthenticatedTemplate>
        <div className="min-h-screen flex flex-col items-center justify-center bg-bg-primary p-6 pt-20 transition-colors duration-300">
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="text-center"
          >
            <Layers className="w-20 h-20 text-accent-primary mx-auto mb-6" />
            <h1 className="text-4xl font-black text-text-primary mb-2 tracking-tighter">BACKLOG.AI</h1>
            <p className="text-text-secondary mb-10 max-w-xs mx-auto">Enterprise AI Story Decomposition protected by Microsoft Entra ID.</p>
            <button
              onClick={() => instance.loginRedirect(loginRequest)}
              className="px-10 py-4 bg-text-primary text-bg-primary font-black rounded-2xl hover:bg-accent-primary hover:text-white transition-all transform hover:scale-105 active:scale-95 shadow-2xl"
            >
              Sign In with Microsoft
            </button>
          </motion.div>
        </div>
      </UnauthenticatedTemplate>
    </>
  );
};

function App() {
  return (
    <MsalProvider instance={msalInstance}>
      <QueryClientProvider client={queryClient}>
        <ProjectProvider>
          <ThemeProvider>
            <AuthWrapper />
          </ThemeProvider>
        </ProjectProvider>
      </QueryClientProvider>
    </MsalProvider>
  );
}

export default App;
