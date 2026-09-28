import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';

export default function LoginView({ onSwitchToRegister, onSuccess }) {
  const { login } = useAuth();
  const [formData, setFormData] = useState({
    username: '',
    password: '',
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
      await login(formData.username, formData.password);
      if (onSuccess) onSuccess();
    } catch (err) {
      if (err.errors) {
        setErrors(err.errors);
      } else {
        setErrors({ non_field_errors: ['An unexpected error occurred. Please try again.'] });
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-md">
      <div className="overflow-hidden rounded-3xl border border-slate-800 bg-slate-900/70 p-6 sm:p-8 shadow-2xl backdrop-blur-xl">
        <div className="mb-6 text-center">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-600/10 text-indigo-400 border border-indigo-500/20 mb-3">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1" />
            </svg>
          </div>
          <h2 className="text-2xl font-black tracking-tight text-white">Welcome Back</h2>
          <p className="mt-1 text-sm text-slate-400">Enter your credentials to enter the arena</p>
        </div>

        {errors.non_field_errors && (
          <div className="mb-5 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300">
            {errors.non_field_errors.map((msg, i) => (
              <p key={i}>{msg}</p>
            ))}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
              Username
            </label>
            <input
              type="text"
              name="username"
              value={formData.username}
              onChange={handleChange}
              placeholder="e.g. player_one"
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

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 px-4 py-3 text-sm font-bold text-white shadow-lg shadow-indigo-600/30 transition hover:from-indigo-500 hover:to-purple-500 disabled:opacity-50"
          >
            {loading ? 'Logging in...' : 'Enter Realm'}
          </button>
        </form>

        <div className="mt-6 text-center text-xs text-slate-400">
          Don't have an account?{' '}
          <button
            type="button"
            onClick={onSwitchToRegister}
            className="font-semibold text-indigo-400 hover:text-indigo-300 underline"
          >
            Register new player
          </button>
        </div>
      </div>
    </div>
  );
}
