import Search from './Search.jsx'

/**
 * App — root layout with floating pill navbar.
 */
export default function App() {
  return (
    <div className="min-h-screen bg-black text-white flex flex-col">

      {/* Floating pill navbar */}
      <header className="fixed top-4 left-0 right-0 z-50 flex justify-center px-4">
        <nav className="liquid-glass rounded-full px-6 py-2.5 flex items-center gap-6">
          <span
            className="gradient-heading text-lg leading-none select-none"
          >
            Cryo
          </span>
          <div className="w-px h-4 bg-white/10" />
          <span className="text-xs text-white/40 font-light tracking-wide">
            pre-2022 · human web
          </span>
          <div className="w-px h-4 bg-white/10" />
          <a
            href="https://github.com/premxai/cryo"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-white/30 hover:text-white/60 transition-colors font-light tracking-wide"
          >
            GitHub
          </a>
        </nav>
      </header>

      {/* Main content */}
      <main className="flex-1 flex flex-col items-center pt-24 px-4">
        <Search />
      </main>

      {/* Footer */}
      <footer className="py-6 text-center">
        <span className="text-xs text-white/15 font-light tracking-widest">
          frozen at 2021 · authentic human content only
        </span>
      </footer>

    </div>
  )
}
