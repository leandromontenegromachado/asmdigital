import React, { useState } from 'react';
import { Terminal, Eye, EyeOff, Lock, Mail } from 'lucide-react';

const LoginPage: React.FC = () => {
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);

  const togglePasswordVisibility = () => {
    setShowPassword(!showPassword);
  };

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    console.log('Login attempt:', { email, password, rememberMe });
    // Add authentication logic here
  };

  return (
    <div className="flex min-h-screen w-full flex-row bg-background-main text-slate-900">
      
      {/* Left Column - Branding (Hidden on mobile) */}
      <div className="hidden lg:flex w-1/2 relative bg-[#EFF6FF] overflow-hidden flex-col justify-between p-12">
        {/* Abstract Background Blobs */}
        <div className="absolute inset-0 z-0 bg-gradient-to-br from-blue-50 via-white to-blue-100"></div>
        <div className="absolute top-0 right-0 -mr-20 -mt-20 w-96 h-96 rounded-full bg-blue-200/20 blur-3xl"></div>
        <div className="absolute bottom-0 left-0 -ml-20 -mb-20 w-80 h-80 rounded-full bg-blue-300/20 blur-3xl"></div>

        {/* Header/Logo Area */}
        <div className="relative z-20">
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-white border border-blue-100 text-primary shadow-sm">
              <Terminal size={24} strokeWidth={2.5} />
            </div>
            <span className="text-2xl font-bold tracking-tight text-slate-800">ASM Digital</span>
          </div>
        </div>

        {/* Quote Area */}
        <div className="relative z-20 max-w-lg mb-12">
          <blockquote className="text-3xl font-medium leading-tight text-slate-800 mb-6">
            "Inteligência Artificial para sua infraestrutura. Simplifique a gestão de dados e relatórios complexos."
          </blockquote>
          <div className="flex items-center gap-3">
            <div className="h-1 w-12 bg-primary rounded-full"></div>
            <p className="text-slate-500 font-medium text-sm">Plataforma Corporativa v2.4</p>
          </div>
        </div>
      </div>

      {/* Right Column - Login Form */}
      <div className="flex flex-1 flex-col justify-center items-center px-6 py-12 lg:px-24 bg-white relative shadow-xl lg:shadow-none">
        
        {/* Mobile Header (Visible only on small screens) */}
        <div className="lg:hidden absolute top-8 left-6 flex items-center gap-2">
          <div className="flex items-center justify-center w-8 h-8 rounded bg-primary/10 text-primary">
            <Terminal size={20} />
          </div>
          <span className="text-xl font-bold text-slate-900">ASM Digital</span>
        </div>

        <div className="w-full max-w-[440px] flex flex-col gap-8">
          
          {/* Form Header */}
          <div className="flex flex-col gap-2">
            <h1 className="text-slate-900 text-4xl font-black leading-tight tracking-tight">
              Bem-vindo de volta
            </h1>
            <p className="text-slate-500 text-base font-normal">
              Acesse sua plataforma de automação e relatórios.
            </p>
          </div>

          {/* Form */}
          <form className="flex flex-col gap-5" onSubmit={handleLogin}>
            
            {/* Email Field */}
            <div className="flex flex-col gap-2">
              <label htmlFor="email" className="text-slate-800 text-sm font-semibold">
                Email Corporativo
              </label>
              <div className="relative">
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 bg-white px-4 py-3.5 text-slate-900 placeholder-slate-400 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all shadow-sm"
                  placeholder="nome@empresa.com"
                  required
                />
              </div>
            </div>

            {/* Password Field */}
            <div className="flex flex-col gap-2">
              <label htmlFor="password" className="text-slate-800 text-sm font-semibold">
                Senha
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 bg-white px-4 py-3.5 pr-12 text-slate-900 placeholder-slate-400 focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all shadow-sm"
                  placeholder="Digite sua senha"
                  required
                />
                <button
                  type="button"
                  onClick={togglePasswordVisibility}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors p-1"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff size={20} /> : <Eye size={20} />}
                </button>
              </div>
            </div>

            {/* Remember Me & Forgot Password */}
            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 cursor-pointer group">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-primary focus:ring-primary/20 cursor-pointer"
                />
                <span className="text-slate-600 text-sm font-medium group-hover:text-slate-800 transition-colors">
                  Lembrar de mim
                </span>
              </label>
              <a href="#" className="text-sm font-semibold text-primary hover:text-primary-hover hover:underline transition-colors">
                Esqueceu a senha?
              </a>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              className="flex w-full cursor-pointer items-center justify-center rounded-lg bg-primary py-3.5 text-white text-base font-bold tracking-wide hover:bg-primary-hover active:scale-[0.98] transition-all shadow-md hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary"
            >
              Entrar
            </button>

            {/* Helper Links */}
            <div className="pt-2 text-center">
              <p className="text-slate-500 text-sm">
                Não tem acesso?{' '}
                <a href="#" className="text-primary font-semibold hover:underline">
                  Solicitar acesso corporativo
                </a>
              </p>
            </div>
          </form>
        </div>

        {/* Footer */}
        <div className="absolute bottom-6 w-full text-center px-6">
          <p className="text-slate-400 text-xs">
            © 2024 ASM Digital. Todos os direitos reservados.
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;