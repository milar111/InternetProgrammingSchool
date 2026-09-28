import React from 'react';
import Avatar, { getAvatarDetails } from './Avatar';

const AVATAR_KEYS = ['knight-1', 'knight-2', 'knight-3', 'knight-4'];

export default function AvatarSelector({ selectedKey, onSelect }) {
  return (
    <div className="space-y-2">
      <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400">
        Choose Knight Avatar
      </label>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {AVATAR_KEYS.map((key) => {
          const isSelected = selectedKey === key;
          const details = getAvatarDetails(key);
          return (
            <button
              type="button"
              key={key}
              onClick={() => onSelect(key)}
              className={`group flex flex-col items-center gap-2 rounded-xl p-3 transition-all duration-200 border text-center ${
                isSelected
                  ? 'border-indigo-500 bg-indigo-500/10 ring-2 ring-indigo-500/40 shadow-lg shadow-indigo-500/20'
                  : 'border-slate-800 bg-slate-900/60 hover:border-slate-700 hover:bg-slate-800/60'
              }`}
            >
              <Avatar avatarKey={key} size="md" />
              <div className="text-left w-full text-center">
                <p className="text-xs font-semibold text-slate-200 group-hover:text-white">
                  {details.name}
                </p>
                <p className="text-[10px] text-slate-400 truncate">
                  {key}
                </p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
