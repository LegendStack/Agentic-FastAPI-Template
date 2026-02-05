import { PublicClientApplication } from '@azure/msal-browser';
import { MsalProvider, AuthenticatedTemplate, UnauthenticatedTemplate, useMsal } from '@azure/msal-react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { msalConfig, loginRequest } from './authConfig';
import { ProjectProvider, useProjectContext } from './hooks/useProjectContext';
import { ProjectSelector } from './components/ProjectSelector';
import { StoryCard } from './components/StoryCard';
import { OracleDrawer } from './components/OracleDrawer';
import { ConversationHistory } from './components/ConversationHistory';
import { useBacklog } from './hooks/useBacklog';
import { Layers, LogOut, User, LayoutDashboard, Sparkles } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const msalInstance = new PublicClientApplication(msalConfig);
const queryClient = new QueryClient();

const Dashboard = () => {
  const { instance, accounts } = useMsal();
  const { selectedProject, setProject } = useProjectContext();
  const {
    stories,
    setStories,
    isProcessing,
    sendMessage,
    updateStoryLocally,
    currentThreadId,
    loadThread,
    recommendations,
    reset
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
    // Manually clear URL to prevent useEffect from reloading old thread
    const url = new URL(window.location.href);
    url.searchParams.delete('thread');
    window.history.pushState({}, '', url);

    // Reset internal state
    reset();
  };

  const deleteStory = (id: string) => {
    setStories(prev => prev.filter(s => s.id !== id));
  };

  return (
    <div className="flex h-screen bg-brand-navy overflow-hidden">
      {/* Sidebar */}
      <aside className="w-72 border-r border-slate-700/50 flex flex-col glass z-10">
        <div className="p-6 flex items-center gap-3">
          <div className="p-2 rounded-lg bg-brand-blue bg-opacity-20">
            <Layers className="w-6 h-6 neon-text" />
          </div>
          <span className="font-bold text-xl text-white tracking-tighter">BACKLOG.AI</span>
        </div>


        <div className="flex-1 overflow-hidden flex flex-col border-t border-slate-700/30 mt-4">
          <ConversationHistory
            onSelectThread={handleSelectThread}
            onNewConversation={handleNewConversation}
            currentThreadId={currentThreadId}
          />
        </div>

        <div className="px-4 mb-4 mt-auto pt-4 border-t border-slate-700/30">
          <button
            onClick={() => setProject(null)}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all text-slate-400 hover:text-brand-blue hover:bg-brand-blue/10 border border-slate-700/50 hover:border-brand-blue/30"
          >
            <LayoutDashboard className="w-5 h-5" />
            <span className="text-sm font-semibold">Change Project</span>
          </button>
        </div>

        <div className="p-4 border-t border-slate-700/50 m-4 rounded-2xl glass">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center text-xs text-white">
              <User className="w-4 h-4" />
            </div>
            <div className="flex-1 overflow-hidden">
              <p className="text-xs font-bold text-white truncate">{accounts[0]?.name || 'User'}</p>
              <p className="text-[10px] text-slate-500 truncate">{accounts[0]?.username}</p>
            </div>
          </div>
          <button
            onClick={() => instance.logoutRedirect()}
            className="w-full mt-2 py-2 flex items-center justify-center gap-2 text-[10px] text-slate-500 hover:text-red-400 transition-colors"
          >
            <LogOut className="w-3 h-3" /> Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto pb-32">
        <header className="sticky top-0 z-20 glass px-12 py-6 flex items-center justify-between border-b border-slate-700/30">
          <div>
            <h2 className="text-2xl font-bold text-white flex items-center gap-3">
              Backlog Board
              <span className="px-3 py-1 rounded-full bg-brand-blue/10 border border-brand-blue/30 text-[10px] uppercase tracking-widest text-brand-blue">
                JIRA: {selectedProject}
              </span>
            </h2>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={handleNewConversation}
              className="px-6 py-2 border border-slate-700 text-slate-300 font-bold rounded-lg hover:bg-slate-800 transition-all"
            >
              Reset
            </button>
          </div>
        </header>

        <div className="max-w-6xl mx-auto px-12 py-8">
          <AnimatePresence mode="popLayout">
            {stories.length > 0 ? (
              <div className="grid grid-cols-1 gap-4">
                {stories.map(story => (
                  <StoryCard
                    key={story.id}
                    story={story}
                    onUpdate={updateStoryLocally}
                    onDelete={deleteStory}
                  />
                ))}
              </div>
            ) : (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex flex-col items-center justify-center mt-20 text-center"
              >
                <div className="w-20 h-20 rounded-3xl bg-slate-800/50 border border-slate-700 flex items-center justify-center mb-6 animate-pulse-slow">
                  <Sparkles className="w-10 h-10 text-brand-blue" />
                </div>
                <h3 className="text-xl font-bold text-white mb-2">No Stories Yet</h3>
                <p className="text-slate-500 max-w-sm">
                  Start by providing an epic description in the Oracle below, or click "Start New Epic" to see the agent in action.
                </p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <OracleDrawer
          onSendMessage={handleRefine}
          isProcessing={isProcessing}
          recommendations={recommendations}
        />
      </main>
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
        <div className="min-h-screen flex flex-col items-center justify-center bg-brand-navy p-6 pt-20">
          <motion.div
            initial={{ scale: 0.9, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            className="text-center"
          >
            <Layers className="w-20 h-20 neon-text mx-auto mb-6" />
            <h1 className="text-4xl font-black text-white mb-2 tracking-tighter">BACKLOG.AI</h1>
            <p className="text-slate-500 mb-10 max-w-xs mx-auto">Enterprise AI Story Decomposition protected by Microsoft Entra ID.</p>
            <button
              onClick={() => instance.loginRedirect(loginRequest)}
              className="px-10 py-4 bg-white text-brand-navy font-black rounded-2xl hover:bg-brand-blue hover:text-brand-navy transition-all transform hover:scale-105 active:scale-95 shadow-[0_0_30px_rgba(255,255,255,0.1)]"
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
          <AuthWrapper />
        </ProjectProvider>
      </QueryClientProvider>
    </MsalProvider>
  );
}

export default App;
