import React from 'react';

const AVATAR_CONFIGS = {
  'knight-1': {
    name: 'Azure Knight',
    bg: 'from-blue-600 to-indigo-800',
    accent: '#60a5fa',
    border: 'border-blue-400',
    title: 'Guardian of the Azure Realm',
  },
  'knight-2': {
    name: 'Crimson Knight',
    bg: 'from-rose-600 to-red-800',
    accent: '#f87171',
    border: 'border-rose-400',
    title: 'Champion of the Red Citadel',
  },
  'knight-3': {
    name: 'Emerald Knight',
    bg: 'from-emerald-600 to-teal-800',
    accent: '#34d399',
    border: 'border-emerald-400',
    title: 'Sentinel of the Verdant Forest',
  },
  'knight-4': {
    name: 'Golden Knight',
    bg: 'from-amber-500 to-yellow-700',
    accent: '#fbbf24',
    border: 'border-amber-400',
    title: 'High Conqueror of Goldcrest',
  },
};

export function getAvatarDetails(key) {
  return AVATAR_CONFIGS[key] || AVATAR_CONFIGS['knight-1'];
}

export default function Avatar({ avatarKey = 'knight-1', size = 'md', className = '' }) {
  const config = getAvatarDetails(avatarKey);

  const sizeClasses = {
    sm: 'w-8 h-8 text-xs',
    md: 'w-12 h-12 text-sm',
    lg: 'w-20 h-20 text-base',
    xl: 'w-28 h-28 text-lg',
  }[size] || 'w-12 h-12 text-sm';

  return (
    <div
      className={`relative inline-flex items-center justify-center rounded-2xl bg-gradient-to-br ${config.bg} p-1 shadow-lg ring-2 ring-white/10 ${sizeClasses} ${className}`}
      title={config.name}
    >
      <svg
        className="w-full h-full text-white drop-shadow-md"
        viewBox="0 0 24 24"
        fill="currentColor"
      >
        <path d="M12 2L4 5v6.09c0 5.05 3.41 9.76 8 10.91 4.59-1.15 8-5.86 8-10.91V5l-8-3zm0 2.18l6 2.25v4.66c0 4.1-2.67 7.9-6 9-3.33-1.1-6-4.9-6-9V6.43l6-2.25zM11 7v3H8v2h3v5h2v-5h3v-2h-3V7h-2z" />
      </svg>
      <span className="absolute -bottom-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-slate-900 border border-white/20 text-[9px] font-bold text-slate-200">
        {avatarKey.replace('knight-', '')}
      </span>
    </div>
  );
}
