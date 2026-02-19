import React, { createContext, useContext, useMemo, useState } from 'react';

interface AuthState {
  token: string | null;
}

interface AuthContextValue {
  token: string | null;
  isAuthenticated: boolean;
  setToken: (token: string | null) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, setState] = useState<AuthState>({
    token: localStorage.getItem('asm_token'),
  });

  const setToken = (token: string | null) => {
    if (token) {
      localStorage.setItem('asm_token', token);
    } else {
      localStorage.removeItem('asm_token');
    }
    setState({ token });
  };

  const value = useMemo(
    () => ({
      token: state.token,
      isAuthenticated: Boolean(state.token),
      setToken,
      logout: () => setToken(null),
    }),
    [state.token]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return ctx;
};
