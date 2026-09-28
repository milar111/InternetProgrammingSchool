import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import Avatar from './Avatar';
import AvatarSelector from './AvatarSelector';

export default function ProfileView({ onRequireLogin }) {
  const { user, updateProfile, loading } = useAuth();
  const [nickname, setNickname] = useState('');
  const [avatarKey, setAvatarKey] = useState('knight-1');
  const [errors, setErrors] = useState({});
  const [successMsg, setSuccessMsg] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (user?.profile) {
      setNickname(user.profile.nickname || '');
      setAvatarKey(user.profile.avatar_key || 'knight-1');
    }
  }, [user]);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-indigo-500 border-t-transparent" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="mx-auto max-w-md text-center p-8 rounded-3xl border border-slate-800 bg-slate-900/60 backdrop-blur-xl">
        <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-400 mb-3">
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
        </div>
        <h3 className="text-lg font-bold text-white">Authentication Required</h3>
        <p className="mt-1 text-sm text-slate-400">Please log in to view and customize your knight profile.</p>
        <button
          onClick={onRequireLogin}
          className="mt-4 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-indigo-600/30 hover:bg-indigo-500 transition"
        >
          Go to Login
        </button>
      </div>
    );
  }

  async function handleSave(e) {
    e.preventDefault();
    setErrors({});
    setSuccessMsg('');
    setSaving(true);

    try {
      await updateProfile({
        nickname,
        avatar_key: avatarKey,
      });
      setSuccessMsg('Profile updated successfully!');
      setTimeout(() => setSuccessMsg(''), 4000);
    } catch (err) {
      if (err.errors) {
        setErrors(err.errors);
      } else {
        setErrors({ non_field_errors: ['Could not update profile.'] });
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-2xl">
      <div className="overflow-hidden rounded-3xl border border-slate-800 bg-slate-900/70 p-6 sm:p-10 shadow-2xl backdrop-blur-xl">
        <div className="flex flex-col sm:flex-row items-center gap-6 pb-8 border-b border-slate-800">
          <Avatar avatarKey={avatarKey} size="xl" className="shadow-2xl" />
          <div className="text-center sm:text-left space-y-1">
            <div className="flex items-center justify-center sm:justify-start gap-2">
              <h2 className="text-2xl font-black tracking-tight text-white">
                {user.profile?.nickname || user.username}
              </h2>
              <span className="rounded-full bg-indigo-500/10 border border-indigo-500/30 px-2 py-0.5 text-[10px] font-semibold text-indigo-300">
                Player #{user.id}
              </span>
            </div>
            <p className="text-sm text-slate-400 font-mono">@{user.username}</p>
            <p className="text-xs text-slate-500">{user.email}</p>
          </div>
        </div>

        {successMsg && (
          <div className="mt-6 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-emerald-300 flex items-center gap-2">
            <svg className="w-4 h-4 shrink-0 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
            </svg>
            <span>{successMsg}</span>
          </div>
        )}

        {errors.non_field_errors && (
          <div className="mt-6 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300">
            {errors.non_field_errors.map((msg, i) => (
              <p key={i}>{msg}</p>
            ))}
          </div>
        )}

        <form onSubmit={handleSave} className="mt-6 space-y-6">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
              Edit In-Game Nickname
            </label>
            <input
              type="text"
              value={nickname}
              onChange={(e) => {
                setNickname(e.target.value);
                if (errors.nickname) setErrors((prev) => ({ ...prev, nickname: null }));
              }}
              placeholder="Your champion title"
              maxLength={30}
              required
              className={`w-full rounded-xl border bg-slate-950/60 px-4 py-2.5 text-sm text-white placeholder-slate-500 transition focus:outline-none focus:ring-2 ${
                errors.nickname
                  ? 'border-rose-500 focus:ring-rose-500/40'
                  : 'border-slate-800 focus:border-indigo-500 focus:ring-indigo-500/30'
              }`}
            />
            {errors.nickname && (
              <p className="mt-1 text-xs text-rose-400">{errors.nickname[0]}</p>
            )}
            <p className="mt-1 text-[11px] text-slate-500">
              Unique display title across all Quiz Conquest tournaments.
            </p>
          </div>

          <AvatarSelector
            selectedKey={avatarKey}
            onSelect={(key) => setAvatarKey(key)}
          />

          <div className="rounded-2xl border border-slate-800/80 bg-slate-950/40 p-4">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
              Account Credentials (Read-only)
            </h4>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3">
                <span className="text-slate-500 block text-[10px] uppercase font-semibold">User ID</span>
                <span className="font-mono text-slate-200">{user.id}</span>
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3">
                <span className="text-slate-500 block text-[10px] uppercase font-semibold">Username</span>
                <span className="font-mono text-slate-200">{user.username}</span>
              </div>
              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-3 sm:col-span-2">
                <span className="text-slate-500 block text-[10px] uppercase font-semibold">Email</span>
                <span className="font-mono text-slate-200">{user.email}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="submit"
              disabled={saving}
              className="rounded-xl bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 px-6 py-2.5 text-xs font-bold text-white shadow-lg shadow-indigo-600/30 transition hover:from-indigo-500 hover:to-pink-500 disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Save Profile Changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
