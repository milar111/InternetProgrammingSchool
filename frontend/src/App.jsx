import React, { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import Navbar from './components/Navbar';
import LoginView from './components/LoginView';
import RegisterView from './components/RegisterView';
import ProfileView from './components/ProfileView';

function AppContent() {
  const { user, loading } = useAuth();
  const [currentView, setCurrentView] = useState('login');

  useEffect(() => {
    if (user) {
      setCurrentView('profile');
    } else if (currentView === 'profile') {
      setCurrentView('login');
    }
  }, [user]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-indigo-500 selection:text-white">
      <Navbar currentView={currentView} setCurrentView={setCurrentView} />

      <main className="flex-1 flex flex-col justify-center px-4 py-12 sm:px-6 lg:px-8 relative overflow-hidden">
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-indigo-600/15 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute top-1/2 right-1/4 w-80 h-80 bg-purple-600/10 rounded-full blur-3xl pointer-events-none" />


        <div className="relative z-10 w-full">
          {loading ? (
            <div className="flex flex-col items-center justify-center space-y-3">
              <div className="h-10 w-10 animate-spin rounded-full border-4 border-indigo-500 border-t-transparent" />
              <p className="text-xs font-medium text-slate-400">Loading realm session...</p>
            </div>
          ) : (
            <>
              {currentView === 'login' && (
                <LoginView
                  onSwitchToRegister={() => setCurrentView('register')}
                  onSuccess={() => setCurrentView('profile')}
                />
              )}

              {currentView === 'register' && (
                <RegisterView
                  onSwitchToLogin={() => setCurrentView('login')}
                  onSuccess={() => setCurrentView('profile')}
                />
              )}

              {currentView === 'profile' && (
                <ProfileView onRequireLogin={() => setCurrentView('login')} />
              )}
            </>
          )}
        </div>
      </main>

      <footer className="border-t border-slate-900 py-6 text-center text-xs text-slate-500">
        <p>Quiz Conquest</p>
      </footer>

    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
