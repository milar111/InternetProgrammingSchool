import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import AvatarSelector from './AvatarSelector';

export default function RegisterView({ onSwitchToLogin, onSuccess }) {
  const { register, login } = useAuth();
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    nickname: '',
    password: '',
    password_confirm: '',
    avatar_key: 'knight-1',
  });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);

  function handleChange(e) {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) {
      setErrors((prev) => {
        const next = { ...prev };
        delete next[name];
        return next;
      });
    }
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setErrors({});
    setLoading(true);

    try {
      await register({
        username: formData.username,
        email: formData.email,
        nickname: formData.nickname,
        password: formData.password,
        password_confirm: formData.password_confirm,
      });

      await login(formData.username, formData.password);

      if (onSuccess) onSuccess();
    } catch (err) {
      if (err.errors) {
        setErrors(err.errors);
      } else {
        setErrors({ non_field_errors: ['Registration failed. Please check your data.'] });
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-lg">
      <div className="overflow-hidden rounded-3xl border border-slate-800 bg-slate-900/70 p-6 sm:p-8 shadow-2xl backdrop-blur-xl">
        <div className="mb-6 text-center">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-purple-600/10 text-purple-400 border border-purple-500/20 mb-3">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M18 9v3m0 0v3m0-3h3m-3 0h-3m-2-5a4 4 0 11-8 0 4 4 0 018 0zM3 20a6 6 0 0112 0v1H3v-1z" />
            </svg>
          </div>
          <h2 className="text-2xl font-black tracking-tight text-white">Join the Conquest</h2>
          <p className="mt-1 text-sm text-slate-400">Create your knight profile and start competing</p>
        </div>

        {errors.non_field_errors && (
          <div className="mb-5 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300">
            {errors.non_field_errors.map((msg, i) => (
              <p key={i}>{msg}</p>
            ))}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                Username
              </label>
              <input
                type="text"
                name="username"
                value={formData.username}
                onChange={handleChange}
                placeholder="player_one"
                required
                className={`w-full rounded-xl border bg-slate-950/60 px-4 py-2.5 text-sm text-white placeholder-slate-500 transition focus:outline-none focus:ring-2 ${
                  errors.username
                    ? 'border-rose-500 focus:ring-rose-500/40'
                    : 'border-slate-800 focus:border-indigo-500 focus:ring-indigo-500/30'
                }`}
              />
              {errors.username && (
                <p className="mt-1 text-xs text-rose-400">{errors.username[0]}</p>
              )}
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                Email
              </label>
              <input
                type="email"
                name="email"
                value={formData.email}
                onChange={handleChange}
                placeholder="knight@realm.com"
                required
                className={`w-full rounded-xl border bg-slate-950/60 px-4 py-2.5 text-sm text-white placeholder-slate-500 transition focus:outline-none focus:ring-2 ${
                  errors.email
                    ? 'border-rose-500 focus:ring-rose-500/40'
                    : 'border-slate-800 focus:border-indigo-500 focus:ring-indigo-500/30'
                }`}
              />
              {errors.email && (
                <p className="mt-1 text-xs text-rose-400">{errors.email[0]}</p>
              )}
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
              In-Game Nickname
            </label>
            <input
              type="text"
              name="nickname"
              value={formData.nickname}
              onChange={handleChange}
              placeholder="MountainKnight"
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
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                Password
              </label>
              <input
                type="password"
                name="password"
                value={formData.password}
                onChange={handleChange}
                placeholder="••••••••••••"
                required
                className={`w-full rounded-xl border bg-slate-950/60 px-4 py-2.5 text-sm text-white placeholder-slate-500 transition focus:outline-none focus:ring-2 ${
                  errors.password
                    ? 'border-rose-500 focus:ring-rose-500/40'
                    : 'border-slate-800 focus:border-indigo-500 focus:ring-indigo-500/30'
                }`}
              />
              {errors.password && (
                <p className="mt-1 text-xs text-rose-400">{errors.password[0]}</p>
              )}
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                Confirm Password
              </label>
              <input
                type="password"
                name="password_confirm"
                value={formData.password_confirm}
                onChange={handleChange}
                placeholder="••••••••••••"
                required
                className={`w-full rounded-xl border bg-slate-950/60 px-4 py-2.5 text-sm text-white placeholder-slate-500 transition focus:outline-none focus:ring-2 ${
                  errors.password_confirm
                    ? 'border-rose-500 focus:ring-rose-500/40'
                    : 'border-slate-800 focus:border-indigo-500 focus:ring-indigo-500/30'
                }`}
              />
              {errors.password_confirm && (
                <p className="mt-1 text-xs text-rose-400">{errors.password_confirm[0]}</p>
              )}
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-xl bg-gradient-to-r from-purple-600 via-indigo-600 to-pink-600 px-4 py-3 text-sm font-bold text-white shadow-lg shadow-indigo-600/30 transition hover:from-purple-500 hover:to-pink-500 disabled:opacity-50"
          >
            {loading ? 'Creating Champion...' : 'Register Profile'}
          </button>
        </form>

        <div className="mt-6 text-center text-xs text-slate-400">
          Already have an account?{' '}
          <button
            type="button"
            onClick={onSwitchToLogin}
            className="font-semibold text-indigo-400 hover:text-indigo-300 underline"
          >
            Log in here
          </button>
        </div>
      </div>
    </div>
  );
}
