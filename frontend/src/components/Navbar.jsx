import React from 'react';
import { useAuth } from '../context/AuthContext';
import Avatar from './Avatar';

export default function Navbar({ currentView, setCurrentView }) {
  const { user, logout } = useAuth();

  return (
    <header className="sticky top-0 z-50 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-600 via-purple-600 to-pink-500 shadow-md shadow-indigo-500/20">
            <svg
              className="h-6 w-6 text-white"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
            </svg>
          </div>
          <div>
            <span className="text-lg font-black tracking-tight bg-gradient-to-r from-white via-indigo-100 to-slate-400 bg-clip-text text-transparent">
              Quiz Conquest
            </span>
          </div>
        </div>


        <div className="flex items-center gap-3">
          {user ? (
            <div className="flex items-center gap-3">
              <button
                onClick={() => setCurrentView('profile')}
                className={`flex items-center gap-2.5 rounded-xl border px-3 py-1.5 transition ${
                  currentView === 'profile'
                    ? 'border-indigo-500/50 bg-indigo-500/10 text-white'
                    : 'border-slate-800 bg-slate-900/50 text-slate-300 hover:border-slate-700 hover:text-white'
                }`}
              >
                <Avatar avatarKey={user.profile?.avatar_key || 'knight-1'} size="sm" />
                <div className="text-left hidden sm:block">
                  <div className="text-xs font-bold text-slate-200">
                    {user.profile?.nickname || user.username}
                  </div>
                  <div className="text-[10px] text-slate-400 truncate max-w-[120px]">
                    @{user.username}
                  </div>
                </div>
              </button>

              <button
                onClick={() => logout()}
                className="rounded-xl border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-xs font-medium text-rose-300 transition hover:bg-rose-500/20 hover:border-rose-500/50"
              >
                Logout
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <button
                onClick={() => setCurrentView('login')}
                className={`rounded-xl px-3.5 py-1.5 text-xs font-semibold transition ${
                  currentView === 'login'
                    ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                    : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                }`}
              >
                Log In
              </button>
              <button
                onClick={() => setCurrentView('register')}
                className={`rounded-xl border px-3.5 py-1.5 text-xs font-semibold transition ${
                  currentView === 'register'
                    ? 'border-indigo-500 bg-indigo-500/10 text-white'
                    : 'border-slate-700 text-slate-200 hover:border-indigo-500 hover:text-white'
                }`}
              >
                Register
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
