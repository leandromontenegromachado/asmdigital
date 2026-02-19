import React from 'react';

const Header: React.FC = () => {
  return (
    <header className="flex items-center justify-between whitespace-nowrap border-b border-solid border-slate-200 dark:border-[#233c48] px-6 py-4 bg-white dark:bg-[#111c22] sticky top-0 z-50">
      <div className="flex items-center gap-8">
        <div className="flex items-center gap-3 text-slate-900 dark:text-white cursor-pointer">
          <div className="size-8 text-primary">
            <svg fill="currentColor" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg">
              <path clipRule="evenodd" d="M12.0799 24L4 19.2479L9.95537 8.75216L18.04 13.4961L18.0446 4H29.9554L29.96 13.4961L38.0446 8.75216L44 19.2479L35.92 24L44 28.7521L38.0446 39.2479L29.96 34.5039L29.9554 44H18.0446L18.04 34.5039L9.95537 39.2479L4 28.7521L12.0799 24Z" fillRule="evenodd"></path>
            </svg>
          </div>
          <h2 className="text-xl font-bold leading-tight">IT Automation</h2>
        </div>
        <nav className="hidden md:flex items-center gap-8">
          <a className="text-slate-500 hover:text-primary dark:text-[#92b7c9] dark:hover:text-white text-sm font-medium transition-colors" href="#">Dashboard</a>
          <a className="text-slate-500 hover:text-primary dark:text-[#92b7c9] dark:hover:text-white text-sm font-medium transition-colors" href="#">Relatórios</a>
          <a className="text-slate-500 hover:text-primary dark:text-[#92b7c9] dark:hover:text-white text-sm font-medium transition-colors" href="#">Alertas</a>
          <a className="text-primary dark:text-white text-sm font-bold transition-colors" href="#">Configurações</a>
        </nav>
      </div>
      
      <div className="flex items-center gap-4">
        <div className="hidden sm:flex relative">
          <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400 dark:text-[#92b7c9]">
            <span className="material-symbols-outlined !text-[20px]">search</span>
          </span>
          <input 
            className="w-full sm:w-64 rounded-lg border border-slate-200 dark:border-none bg-slate-50 dark:bg-[#233c48] py-2 pl-10 pr-4 text-sm text-slate-900 dark:text-white focus:border-primary focus:ring-1 focus:ring-primary dark:focus:ring-primary placeholder:text-slate-400 dark:placeholder:text-[#92b7c9] transition-all" 
            placeholder="Buscar..." 
            type="text"
          />
        </div>
        
        <button className="relative rounded-full bg-slate-100 dark:bg-[#233c48] p-2 text-slate-500 dark:text-[#92b7c9] hover:bg-slate-200 dark:hover:bg-[#2c4b5a] transition-colors">
          <span className="material-symbols-outlined">notifications</span>
          <span className="absolute top-2 right-2 size-2 rounded-full bg-red-500 ring-2 ring-white dark:ring-[#111c22]"></span>
        </button>
        
        <div 
          className="size-9 bg-center bg-no-repeat bg-cover rounded-full ring-2 ring-slate-100 dark:ring-[#233c48] cursor-pointer hover:ring-primary transition-all" 
          style={{backgroundImage: 'url("https://lh3.googleusercontent.com/aida-public/AB6AXuAYk1BWKqMuBG1AOGnR8i_bP3wAj_i9_NFJVqMTxHJSzqi0JaHWgruXd1FPXHqUCWYE1Fk3CmaTUEIwFhRan_cWtibH9PTGlUDeuIvjkAt2MleHGnd3e2L0vcgeCyiLzbIEL3MNfBczxWrfgy3ES5UKqBV9-FJ28fzb4jipOb8qcT3QnRbF93orMXYRKEo5dGMjYPQbPCSUavB0qq-mLCI7ykNWJqM_U97EE99JBLeUwMrs9Jky7LGp02OK3ns3LCU73-C5xHs5wrc")'}}
        ></div>
      </div>
    </header>
  );
};

export default Header;
