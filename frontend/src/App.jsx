import React, { useState } from 'react';

export default function App() {
  const [file, setFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const analyzeFile = async () => {
    if (!file) return;
    setIsLoading(true);
    setResult(null);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('http://localhost:8000/api/analyze', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Error al conectar con la IA de auditoría.');
      }

      const data = await response.json();
      if (data.status === 'success') {
        setResult(data.report);
      } else {
        setError(data.error || 'Ocurrió un error desconocido.');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-dark-900 text-slate-200 font-sans relative overflow-hidden flex flex-col items-center">

      {/* Background Cinematic Blobs */}
      <div className="absolute top-0 -left-4 w-96 h-96 bg-accent-500 rounded-full mix-blend-multiply filter blur-[128px] opacity-20 animate-blob"></div>
      <div className="absolute top-0 -right-4 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply filter blur-[128px] opacity-20 animate-blob animation-delay-2000"></div>
      <div className="absolute -bottom-8 left-20 w-96 h-96 bg-blue-500 rounded-full mix-blend-multiply filter blur-[128px] opacity-20 animate-blob animation-delay-4000"></div>

      {/* Navbar Minimalista */}
      <header className="w-full border-b border-white/5 bg-dark-900/40 backdrop-blur-2xl sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="relative flex items-center justify-center w-10 h-10 rounded-xl bg-gradient-to-br from-accent-500 to-purple-600 shadow-[0_0_25px_rgba(99,102,241,0.4)]">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-6 h-6 text-white">
                <path fillRule="evenodd" d="M12 1.5a5.25 5.25 0 00-5.25 5.25v3a3 3 0 00-3 3v6.75a3 3 0 003 3h10.5a3 3 0 003-3v-6.75a3 3 0 00-3-3v-3c0-2.9-2.35-5.25-5.25-5.25zm3.75 8.25v-3a3.75 3.75 0 10-7.5 0v3h7.5z" clipRule="evenodd" />
              </svg>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-white">
              Salud<span className="text-transparent bg-clip-text bg-gradient-to-r from-accent-400 to-purple-400">Guard</span>
            </h1>
          </div>
          <div className="hidden sm:flex px-4 py-1.5 rounded-full border border-accent-500/30 bg-accent-500/10 text-accent-300 text-sm font-medium tracking-wide">
            <span className="relative flex h-2 w-2 mr-2 mt-1.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-accent-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-accent-500"></span>
            </span>
            AI Engine Active
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="relative z-10 flex-grow w-full max-w-5xl px-6 py-16 md:py-24 animate-fade-in-up flex flex-col items-center">

        <div className="text-center max-w-3xl mb-16">
          <h2 className="text-5xl md:text-7xl font-extrabold text-transparent bg-clip-text bg-gradient-to-b from-white to-slate-400 mb-6 tracking-tight">
            Validador Forense
          </h2>
          <p className="text-lg md:text-xl text-slate-400 font-light leading-relaxed">
            Plataforma impulsada por múltiples agentes <strong className="text-slate-200 font-semibold">CrewAI</strong> para la prevención de fraude en incapacidades del Sistema General de Seguridad Social en Salud.
          </p>
        </div>

        {/* Upload Dashboard */}
        <div className={`
          w-full max-w-3xl glass-panel rounded-3xl p-2 transition-all duration-500 
          ${isDragging ? 'scale-[1.02] shadow-[0_0_50px_rgba(99,102,241,0.3)]' : ''}
          ${file && !isLoading ? 'border-green-500/50 shadow-[0_0_30px_rgba(34,197,94,0.15)]' : ''}
          ${isLoading ? 'animate-pulse-slow' : ''}
        `}>
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`
              relative w-full h-80 rounded-[1.3rem] border-2 border-dashed flex flex-col items-center justify-center transition-all duration-300
              ${isDragging ? 'border-accent-400 bg-accent-500/10' : 'border-white/10 hover:border-white/20 hover:bg-white/5'}
              ${file ? 'border-green-500/30 bg-green-500/5' : ''}
            `}
          >
            <input
              type="file"
              accept=".pdf,image/*"
              onChange={handleFileChange}
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-20"
              disabled={isLoading}
            />

            {!file ? (
              <div className="z-10 flex flex-col items-center text-center px-4 pointer-events-none">
                <div className="w-20 h-20 mb-6 rounded-full bg-dark-800 border border-white/10 flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1} stroke="currentColor" className="w-10 h-10 text-slate-400">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m3.75 9v6m3-3H9m1.5-12H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                  </svg>
                </div>
                <h3 className="text-2xl font-bold text-slate-200 mb-2">Arrastra el documento aquí</h3>
                <p className="text-slate-500 font-medium">Soporta formatos PDF, JPG o PNG</p>
              </div>
            ) : (
              <div className="z-10 flex flex-col items-center text-center px-4 pointer-events-none">
                <div className="w-24 h-24 mb-6 rounded-full bg-green-500/10 border border-green-500/30 flex items-center justify-center backdrop-blur-sm">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-12 h-12 text-green-400">
                    <path fillRule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm13.36-1.814a.75.75 0 10-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z" clipRule="evenodd" />
                  </svg>
                </div>
                <h3 className="text-3xl font-bold text-white mb-2">{file.name}</h3>
                <p className="text-sm px-4 py-1.5 rounded-full bg-dark-800 text-slate-400 border border-white/5 mt-2">
                  Lista para auditoría
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Action Button Section */}
        <div className="mt-12 w-full max-w-3xl flex flex-col items-center">
          <button
            onClick={analyzeFile}
            disabled={!file || isLoading}
            className={`
                group relative px-10 py-4 w-full sm:w-auto rounded-full font-bold text-lg text-white transition-all 
                ${!file ? 'bg-dark-800 text-slate-500 border border-white/5 cursor-not-allowed' :
                'bg-accent-600 hover:bg-accent-500 hover:scale-105 active:scale-95 animate-glow-border'}
              `}
          >
            {isLoading ? (
              <span className="flex items-center justify-center gap-3">
                <svg className="animate-spin -ml-1 mr-3 h-6 w-6 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Tripulantes IA Analizando...
              </span>
            ) : (
              <span className="flex items-center justify-center gap-2">
                Iniciar Interrogatorio Forense
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5 opacity-70 group-hover:translate-x-1 transition-transform">
                  <path fillRule="evenodd" d="M12.97 3.97a.75.75 0 011.06 0l7.5 7.5a.75.75 0 010 1.06l-7.5 7.5a.75.75 0 11-1.06-1.06l6.22-6.22H3a.75.75 0 010-1.5h16.19l-6.22-6.22a.75.75 0 010-1.06z" clipRule="evenodd" />
                </svg>
              </span>
            )}
          </button>

          {file && !isLoading && (
            <button
              onClick={() => setFile(null)}
              className="mt-6 text-slate-500 hover:text-slate-300 transition-colors text-sm font-medium hover:underline"
            >
              Cancelar o elegir otro documento
            </button>
          )}
        </div>

        {/* Error State */}
        {error && (
          <div className="mt-12 w-full max-w-3xl glass-panel bg-red-950/30 border-red-500/30 rounded-2xl p-6 flex items-start gap-4">
            <div className="p-3 bg-red-500/10 rounded-xl">
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-8 h-8 text-red-500">
                <path fillRule="evenodd" d="M9.401 3.003c1.155-2 4.043-2 5.197 0l7.355 12.748c1.154 2-.29 4.5-2.599 4.5H4.645c-2.309 0-3.752-2.5-2.598-4.5L9.4 3.003zM12 8.25a.75.75 0 01.75.75v3.75a.75.75 0 01-1.5 0V9a.75.75 0 01.75-.75zm0 8.25a.75.75 0 100-1.5.75.75 0 000 1.5z" clipRule="evenodd" />
              </svg>
            </div>
            <div>
              <h4 className="text-xl font-bold text-red-400 mb-1">Análisis fallido</h4>
              <p className="text-slate-300">{error}</p>
            </div>
          </div>
        )}

        {/* Result Report */}
        {result && (
          <div className="mt-16 w-full animate-fade-in-up">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
              <div className="flex items-center gap-4">
                <div className="w-2 h-10 bg-accent-500 rounded-full glow"></div>
                <h3 className="text-3xl font-black text-white tracking-tight">Veredicto Forense</h3>
              </div>
            </div>

            <div className="glass-panel bg-dark-900/80 rounded-3xl p-8 md:p-12 shadow-2xl relative overflow-hidden">
              {/* Decorative glow inside report */}
              <div className="absolute -top-40 -right-40 w-96 h-96 bg-accent-500/10 rounded-full blur-[100px] pointer-events-none"></div>

              <pre className="relative z-10 whitespace-pre-wrap font-sans text-lg text-slate-300 leading-relaxed font-light">
                {typeof result === 'object' ? (result.raw || result.output || JSON.stringify(result, null, 2)) : result}
              </pre>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
