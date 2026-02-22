import React, { useState } from 'react';

export default function App() {
  const [file, setFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleDragOver = (e) => { e.preventDefault(); setIsDragging(true); };
  const handleDragLeave = (e) => { e.preventDefault(); setIsDragging(false); };
  const handleDrop = (e) => {
    e.preventDefault(); setIsDragging(false);
    if (e.dataTransfer.files?.[0]) setFile(e.dataTransfer.files[0]);
  };
  const handleFileChange = (e) => {
    if (e.target.files?.[0]) setFile(e.target.files[0]);
  };

  const analyzeFile = async () => {
    if (!file) return;
    setIsLoading(true); setResult(null); setError(null);
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await fetch('http://localhost:8000/api/analyze', { method: 'POST', body: formData });
      if (!res.ok) throw new Error(`Error del servidor: ${res.status}`);
      const data = await res.json();
      if (data.status === 'success') setResult(data.report);
      else setError(data.error || 'Error desconocido en el análisis.');
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  const getReportText = (r) => {
    if (!r) return '';
    if (typeof r === 'string') return r;
    return r.raw || r.output || JSON.stringify(r, null, 2);
  };

  return (
    <div style={{ minHeight: '100vh', backgroundColor: 'var(--color-bg-abyss)', color: 'var(--color-text-primary)', fontFamily: 'Inter, system-ui, sans-serif', position: 'relative', overflowX: 'hidden', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>

      {/* Background Blobs */}
      <div className="bg-blob" style={{ width: '600px', height: '600px', background: 'var(--color-accent-600)', top: '-150px', left: '-200px', animationDelay: '0s' }} />
      <div className="bg-blob" style={{ width: '500px', height: '500px', background: '#7C3AED', top: '-100px', right: '-150px', animationDelay: '-3s' }} />
      <div className="bg-blob" style={{ width: '400px', height: '400px', background: 'var(--color-data-500)', bottom: '0', left: '30%', animationDelay: '-6s' }} />

      {/* ── NAVBAR ── */}
      <header style={{ width: '100%', borderBottom: '1px solid rgba(255,255,255,0.05)', backgroundColor: 'rgba(6,10,18,0.7)', backdropFilter: 'blur(24px)', WebkitBackdropFilter: 'blur(24px)', position: 'sticky', top: 0, zIndex: 50 }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '0 24px', height: '72px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '44px', height: '44px', borderRadius: '12px',
              background: 'linear-gradient(135deg, var(--color-accent-600), #7C3AED)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              boxShadow: '0 0 20px rgba(99,102,241,0.4)'
            }}>
              <svg viewBox="0 0 24 24" fill="white" width="22" height="22">
                <path fillRule="evenodd" d="M12 1.5a5.25 5.25 0 00-5.25 5.25v3a3 3 0 00-3 3v6.75a3 3 0 003 3h10.5a3 3 0 003-3v-6.75a3 3 0 00-3-3v-3c0-2.9-2.35-5.25-5.25-5.25zm3.75 8.25v-3a3.75 3.75 0 10-7.5 0v3h7.5z" clipRule="evenodd" />
              </svg>
            </div>
            <span style={{ fontSize: '1.4rem', fontWeight: 800, letterSpacing: '-0.02em' }}>
              Salud<span className="text-gradient-accent">Guard</span>
            </span>
          </div>
          <div className="badge-live">
            <span className="dot" />
            AI Engine Activo
          </div>
        </div>
      </header>

      {/* ── MAIN ── */}
      <main style={{ position: 'relative', zIndex: 10, width: '100%', maxWidth: '880px', padding: '64px 24px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>

        {/* Hero */}
        <div className="animate-fade-up" style={{ textAlign: 'center', marginBottom: '64px' }}>
          <div style={{ display: 'inline-block', padding: '4px 16px', borderRadius: '999px', border: '1px solid rgba(99,102,241,0.25)', background: 'rgba(99,102,241,0.08)', color: 'var(--color-accent-300)', fontSize: '0.8rem', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '24px' }}>
            Sistema de Auditoría Forense
          </div>
          <h1 className="text-gradient-primary" style={{ fontSize: 'clamp(2.5rem, 6vw, 4.5rem)', fontWeight: 900, letterSpacing: '-0.04em', lineHeight: 1.05, margin: '0 0 20px 0' }}>
            Validador Forense<br />
            <span className="text-gradient-accent">de Incapacidades</span>
          </h1>
          <p style={{ fontSize: '1.1rem', color: 'var(--color-text-secondary)', maxWidth: '600px', margin: '0 auto', lineHeight: 1.7, fontWeight: 300 }}>
            Plataforma multi-agente <strong style={{ color: 'var(--color-text-primary)', fontWeight: 600 }}>CrewAI</strong> para detección avanzada de fraude en certificados médicos del <strong style={{ color: 'var(--color-text-primary)', fontWeight: 600 }}>SGSSS colombiano</strong>.
          </p>
        </div>

        {/* Feature chips */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', justifyContent: 'center', marginBottom: '40px' }}>
          {['Validación CIE-10', 'Análisis Forense PDF', 'RETHUS / ADRES', 'Detección Fraude IA', 'Informe Estructurado'].map(f => (
            <span key={f} style={{ padding: '6px 16px', borderRadius: '999px', background: 'var(--color-bg-elevated)', border: '1px solid rgba(255,255,255,0.07)', color: 'var(--color-text-secondary)', fontSize: '0.8rem', fontWeight: 500, letterSpacing: '0.03em' }}>
              ◈ {f}
            </span>
          ))}
        </div>

        {/* ── UPLOAD PANEL ── */}
        <div className="glass animate-fade-up" style={{ width: '100%', borderRadius: '24px', padding: '8px', marginBottom: '24px' }}>
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`drop-zone ${isDragging ? 'drop-zone-active' : ''} ${file ? 'drop-zone-filled' : ''}`}
            style={{ position: 'relative', minHeight: '260px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '32px', textAlign: 'center' }}
          >
            <input type="file" accept=".pdf,image/*" onChange={handleFileChange} disabled={isLoading}
              style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', opacity: 0, cursor: 'pointer', zIndex: 20 }} />

            {!file ? (
              <div style={{ pointerEvents: 'none', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                <div style={{
                  width: '80px', height: '80px', borderRadius: '20px', marginBottom: '20px',
                  background: 'var(--color-bg-elevated)', border: '1px solid rgba(255,255,255,0.08)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  boxShadow: isDragging ? '0 0 30px rgba(99,102,241,0.3)' : 'none',
                  transition: 'all 0.25s'
                }}>
                  <svg viewBox="0 0 24 24" fill="none" stroke="var(--color-accent-400)" strokeWidth={1.5} width="36" height="36">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m3.75 9v6m3-3H9m1.5-12H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                  </svg>
                </div>
                <h3 style={{ fontSize: '1.3rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '8px' }}>
                  {isDragging ? 'Suelta el documento aquí' : 'Arrastra tu certificado médico'}
                </h3>
                <p style={{ color: 'var(--color-text-secondary)', fontSize: '0.9rem' }}>PDF, JPG o PNG — Máx. 20MB</p>
              </div>
            ) : (
              <div style={{ pointerEvents: 'none', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                <div style={{ width: '80px', height: '80px', borderRadius: '20px', marginBottom: '20px', background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center' }} className="glow-success">
                  <svg viewBox="0 0 24 24" fill="var(--color-success-500)" width="40" height="40">
                    <path fillRule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm13.36-1.814a.75.75 0 10-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z" clipRule="evenodd" />
                  </svg>
                </div>
                <h3 style={{ fontSize: '1.3rem', fontWeight: 700, color: 'white', marginBottom: '8px', maxWidth: '400px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{file.name}</h3>
                <span style={{ fontSize: '0.8rem', color: 'var(--color-success-500)', background: 'rgba(16,185,129,0.1)', padding: '4px 12px', borderRadius: '999px', border: '1px solid rgba(16,185,129,0.2)' }}>
                  Documento listo para auditoría
                </span>
              </div>
            )}
          </div>
        </div>

        {/* ── ACTION BUTTON ── */}
        <div style={{ width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px', marginBottom: '40px' }}>
          <button onClick={analyzeFile} disabled={!file || isLoading} className="btn-primary"
            style={{ padding: '16px 48px', fontSize: '1rem', width: '100%', maxWidth: '400px', border: 'none', cursor: file && !isLoading ? 'pointer' : 'not-allowed' }}>
            {isLoading ? (
              <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '12px' }}>
                <svg style={{ animation: 'spin 1s linear infinite', width: '20px', height: '20px' }} viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="10" stroke="rgba(255,255,255,0.3)" strokeWidth="3" />
                  <path d="M12 2a10 10 0 0 1 10 10" stroke="white" strokeWidth="3" strokeLinecap="round" />
                </svg>
                <span>Agentes IA Analizando...</span>
              </span>
            ) : (
              <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
                Iniciar Auditoría Forense
                <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18" style={{ opacity: 0.8 }}>
                  <path fillRule="evenodd" d="M12.97 3.97a.75.75 0 011.06 0l7.5 7.5a.75.75 0 010 1.06l-7.5 7.5a.75.75 0 11-1.06-1.06l6.22-6.22H3a.75.75 0 010-1.5h16.19l-6.22-6.22a.75.75 0 010-1.06z" clipRule="evenodd" />
                </svg>
              </span>
            )}
          </button>

          {isLoading && (
            <div style={{ textAlign: 'center', color: 'var(--color-text-secondary)', fontSize: '0.85rem', maxWidth: '380px', lineHeight: 1.6 }}>
              <span style={{ color: 'var(--color-accent-400)', fontWeight: 600 }}>5 agentes especializados</span> están verificando el documento en paralelo. El proceso tarda entre <strong style={{ color: 'var(--color-text-primary)' }}>30 y 90 segundos</strong>.
            </div>
          )}

          {file && !isLoading && (
            <button onClick={() => { setFile(null); setResult(null); setError(null); }}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)', fontSize: '0.85rem', textDecoration: 'underline' }}>
              Cancelar y elegir otro archivo
            </button>
          )}
        </div>

        {/* ── ERROR STATE ── */}
        {error && (
          <div className="glass animate-fade-up" style={{ width: '100%', borderRadius: '16px', padding: '20px 24px', marginBottom: '32px', background: 'rgba(127,0,0,0.15)', borderColor: 'rgba(239,68,68,0.25)', display: 'flex', gap: '16px', alignItems: 'flex-start' }}>
            <div style={{ padding: '8px', background: 'rgba(239,68,68,0.1)', borderRadius: '10px', flexShrink: 0 }}>
              <svg viewBox="0 0 24 24" fill="var(--color-danger-500)" width="24" height="24">
                <path fillRule="evenodd" d="M9.401 3.003c1.155-2 4.043-2 5.197 0l7.355 12.748c1.154 2-.29 4.5-2.599 4.5H4.645c-2.309 0-3.752-2.5-2.598-4.5L9.4 3.003zM12 8.25a.75.75 0 01.75.75v3.75a.75.75 0 01-1.5 0V9a.75.75 0 01.75-.75zm0 8.25a.75.75 0 100-1.5.75.75 0 000 1.5z" clipRule="evenodd" />
              </svg>
            </div>
            <div>
              <p style={{ fontWeight: 700, color: '#FCA5A5', marginBottom: '4px' }}>Error en el análisis</p>
              <p style={{ color: 'var(--color-text-secondary)', fontSize: '0.9rem' }}>{error}</p>
            </div>
          </div>
        )}

        {/* ── RESULT REPORT ── */}
        {result && (
          <div className="animate-fade-up" style={{ width: '100%' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '24px' }}>
              <div style={{ width: '3px', height: '36px', background: 'linear-gradient(180deg, var(--color-accent-500), #7C3AED)', borderRadius: '999px' }} />
              <h2 style={{ fontSize: '1.6rem', fontWeight: 800, letterSpacing: '-0.03em' }}>
                Veredicto <span className="text-gradient-accent">Forense</span>
              </h2>
            </div>
            <div className="report-panel glass" style={{ padding: '40px 40px' }}>
              <div style={{ position: 'absolute', top: '-80px', right: '-80px', width: '300px', height: '300px', background: 'var(--color-accent-500)', borderRadius: '50%', filter: 'blur(120px)', opacity: 0.06, pointerEvents: 'none' }} />
              <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: "'JetBrains Mono', 'Fira Code', 'Consolas', monospace", fontSize: '0.9rem', lineHeight: 1.8, color: 'var(--color-text-secondary)', position: 'relative', zIndex: 1 }}>
                {getReportText(result)}
              </pre>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer style={{ width: '100%', borderTop: '1px solid rgba(255,255,255,0.04)', padding: '24px', textAlign: 'center', color: 'var(--color-text-muted)', fontSize: '0.78rem', zIndex: 10, position: 'relative' }}>
        SaludGuard AI · Análisis forense de incapacidades médicas Colombia (SGSSS) · Protegido por Ley 1581/2012
      </footer>

      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');
      `}</style>
    </div>
  );
}
