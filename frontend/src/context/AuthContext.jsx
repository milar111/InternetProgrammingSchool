import React, { createContext, useContext, useEffect, useState } from 'react';
import { authApi } from '../api/auth';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkAuth();
  }, []);

  async function checkAuth() {
    try {
      setLoading(true);
      const data = await authApi.getMe();
      setUser(data);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }

  async function login(username, password) {
    const data = await authApi.login({ username, password });
    setUser(data);
    return data;
  }

  async function register(payload) {
    const data = await authApi.register(payload);
    return data;
  }

  async function logout() {
    try {
      await authApi.logout();
    } finally {
      setUser(null);
    }
  }

  async function updateProfile(payload) {
    const data = await authApi.updateProfile(payload);
    setUser(data);
    return data;
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        login,
        register,
        logout,
        updateProfile,
        refreshUser: checkAuth,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
