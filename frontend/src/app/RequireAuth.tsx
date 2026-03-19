import React, { useEffect, useState } from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { me } from '../api/auth';
import { useAuth } from './auth';

export const RequireAuth: React.FC = () => {
  const { isAuthenticated, token, logout } = useAuth();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    let active = true;

    const validate = async () => {
      if (!token) {
        if (active) setChecking(false);
        return;
      }

      try {
        await me();
      } catch {
        logout();
      } finally {
        if (active) setChecking(false);
      }
    };

    validate();
    return () => {
      active = false;
    };
  }, [token, logout]);

  if (checking) {
    return <div className="p-6 text-sm text-slate-500">Validando sessao...</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
};
