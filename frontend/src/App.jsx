import React, { useState } from 'react';

const AVAILABLE_STACK = [
  'python', 'fastapi', 'react', 'javascript', 'typescript', 
  'docker', 'kubernetes', 'aws', 'postgresql', 'mongodb', 'redis', 'django', 'nextjs', 'tailwind'
];

export default function App() {
  const [githubUrl, setGithubUrl] = useState('');
  const [groqKey, setGroqKey] = useState('');
  const [inputReadme, setInputReadme] = useState('# Project Title\nBasic project description...');
  const [outputReadme, setOutputReadme] = useState('');
  const [selectedStack, setSelectedStack] = useState(['python', 'fastapi', 'react']);
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(false);
  const [viewMode, setViewMode] = useState('split');
  const [activeTab, setActiveTab] = useState('url');

  const toggleStack = (tech) => {
    setSelectedStack(prev => 
      prev.includes(tech) ? prev.filter(t => t !== tech) : [...prev, tech]
    );
  };

  const processReadme = async () => {
    setLoading(true);
    try {
      const payload = activeTab === 'url' 
        ? { github_url: githubUrl, tech_stack: selectedStack, groq_api_key: groqKey }
        : { readme_content: inputReadme, tech_stack: selectedStack, groq_api_key: groqKey };

      const res = await fetch('http://localhost:8000/api/process-readme', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      
      const data = await res.json();
      if (data.beautified_readme) {
        setOutputReadme(data.beautified_readme);
        if (data.original_readme) setInputReadme(data.original_readme);
        if (data.detected_stack) setSelectedStack(data.detected_stack);
        setMetrics(data);
      }
    } catch (e) {
      alert('Error enhancing README. Ensure backend server is running.');
    }
    setLoading(false);
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(outputReadme);
    alert('Copied Beautified Markdown!');
  };

  const downloadFile = () => {
    const blob = new Blob([outputReadme], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'README.md';
    a.click();
  };

  return (
    <div style={{ padding: '24px', fontFamily: 'Inter, system-ui, sans-serif', background: '#f5f5f7', minHeight: '100vh', color: '#1d1d1f' }}>
      <header style={{ marginBottom: '24px', borderBottom: '1px solid #e5e5e7', paddingBottom: '16px' }}>
        <h1 style={{ fontSize: '28px', fontWeight: '700', margin: '0 0 8px 0' }}>FixReadme Studio (Groq API Powered)</h1>
        <p style={{ color: '#86868b', margin: 0 }}>Extract, score, and transform GitHub or local project documentation using Groq API.</p>
      </header>

      <div style={{ background: '#ffffff', padding: '20px', borderRadius: '12px', boxShadow: '0 2px 8px rgba(0,0,0,0.04)', marginBottom: '20px' }}>
        <div style={{ marginBottom: '16px' }}>
          <label style={{ fontSize: '13px', fontWeight: '600', color: '#86868b', display: 'block', marginBottom: '6px' }}>GROQ API KEY (Optional if set in backend .env):</label>
          <input 
            type="password" 
            placeholder="gsk_..."
            value={groqKey}
            onChange={(e) => setGroqKey(e.target.value)}
            style={{ width: '100%', padding: '10px 12px', borderRadius: '8px', border: '1px solid #d2d2d7', fontSize: '14px', boxSizing: 'border-box' }}
          />
        </div>

        <div style={{ display: 'flex', gap: '12px', marginBottom: '16px' }}>
          <button 
            onClick={() => setActiveTab('url')}
            style={{ padding: '8px 16px', borderRadius: '6px', border: 'none', background: activeTab === 'url' ? '#0071e3' : '#e8e8ed', color: activeTab === 'url' ? '#fff' : '#1d1d1f', cursor: 'pointer', fontWeight: '600' }}
          >
            Import from GitHub URL
          </button>
          <button 
            onClick={() => setActiveTab('manual')}
            style={{ padding: '8px 16px', borderRadius: '6px', border: 'none', background: activeTab === 'manual' ? '#0071e3' : '#e8e8ed', color: activeTab === 'manual' ? '#fff' : '#1d1d1f', cursor: 'pointer', fontWeight: '600' }}
          >
            Paste Raw Markdown
          </button>
        </div>

        {activeTab === 'url' ? (
          <input 
            type="text" 
            placeholder="https://github.com/college-hack24-nov26/hack-impact-zero"
            value={githubUrl}
            onChange={(e) => setGithubUrl(e.target.value)}
            style={{ width: '100%', padding: '12px', borderRadius: '8px', border: '1px solid #d2d2d7', fontSize: '15px', boxSizing: 'border-box' }}
          />
        ) : (
          <span style={{ fontSize: '14px', color: '#86868b' }}>Paste your raw README markdown content in the left editor pane below.</span>
        )}

        <div style={{ marginTop: '16px' }}>
          <label style={{ fontSize: '13px', fontWeight: '600', color: '#86868b', display: 'block', marginBottom: '8px' }}>TECH STACK BADGE SELECTOR:</label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {AVAILABLE_STACK.map(tech => (
              <span 
                key={tech} 
                onClick={() => toggleStack(tech)}
                style={{ 
                  padding: '4px 12px', borderRadius: '16px', fontSize: '12px', fontWeight: '600', cursor: 'pointer',
                  background: selectedStack.includes(tech) ? '#0071e3' : '#f2f2f7',
                  color: selectedStack.includes(tech) ? '#ffffff' : '#1d1d1f',
                  border: '1px solid #d2d2d7'
                }}
              >
                {tech}
              </span>
            ))}
          </div>
        </div>

        <button 
          onClick={processReadme} 
          disabled={loading}
          style={{ marginTop: '20px', width: '100%', padding: '12px', background: '#0071e3', color: '#ffffff', border: 'none', borderRadius: '8px', fontSize: '16px', fontWeight: '600', cursor: 'pointer' }}
        >
          {loading ? 'Processing via Groq API...' : 'Analyze & Transform README'}
        </button>
      </div>

      {metrics && (
        <div style={{ background: '#ffffff', padding: '16px 20px', borderRadius: '12px', marginBottom: '20px', border: '1px solid #e5e5e7', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <span style={{ fontSize: '14px', color: '#86868b' }}>Documentation Quality Score:</span>
            <div style={{ fontSize: '22px', fontWeight: '700', marginTop: '4px' }}>
              {metrics.original_score}/100 ➔ <span style={{ color: '#34c759' }}>{metrics.improved_score}/100</span>
            </div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <span style={{ fontSize: '13px', color: '#86868b' }}>Injected Enhancements:</span>
            <div style={{ fontSize: '13px', fontWeight: '600', color: '#0071e3', marginTop: '4px' }}>
              {metrics.missing_features ? metrics.missing_features.join(', ') : 'Badges, Flowchart, Shields'}
            </div>
          </div>
        </div>
      )}

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button onClick={() => setViewMode('split')} style={{ padding: '6px 12px', borderRadius: '6px', border: '1px solid #d2d2d7', background: viewMode === 'split' ? '#e8e8ed' : '#fff' }}>Split View</button>
          <button onClick={() => setViewMode('code')} style={{ padding: '6px 12px', borderRadius: '6px', border: '1px solid #d2d2d7', background: viewMode === 'code' ? '#e8e8ed' : '#fff' }}>Code Only</button>
          <button onClick={() => setViewMode('preview')} style={{ padding: '6px 12px', borderRadius: '6px', border: '1px solid #d2d2d7', background: viewMode === 'preview' ? '#e8e8ed' : '#fff' }}>Preview Only</button>
        </div>

        {outputReadme && (
          <div style={{ display: 'flex', gap: '8px' }}>
            <button onClick={copyToClipboard} style={{ padding: '8px 16px', background: '#34c759', color: '#fff', border: 'none', borderRadius: '6px', fontWeight: '600', cursor: 'pointer' }}>Copy Markdown</button>
            <button onClick={downloadFile} style={{ padding: '8px 16px', background: '#1d1d1f', color: '#fff', border: 'none', borderRadius: '6px', fontWeight: '600', cursor: 'pointer' }}>Download .md</button>
          </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: '20px' }}>
        {(viewMode === 'split' || viewMode === 'code') && (
          <div style={{ width: viewMode === 'split' ? '50%' : '100%' }}>
            <label style={{ fontSize: '12px', fontWeight: '600', color: '#86868b', display: 'block', marginBottom: '6px' }}>ORIGINAL RAW MARKDOWN</label>
            <textarea
              style={{ width: '100%', height: '560px', fontFamily: 'monospace', padding: '16px', borderRadius: '8px', border: '1px solid #d2d2d7', background: '#ffffff', boxSizing: 'border-box' }}
              value={inputReadme}
              onChange={(e) => setInputReadme(e.target.value)}
            />
          </div>
        )}
        
        {(viewMode === 'split' || viewMode === 'preview') && (
          <div style={{ width: viewMode === 'split' ? '50%' : '100%' }}>
            <label style={{ fontSize: '12px', fontWeight: '600', color: '#86868b', display: 'block', marginBottom: '6px' }}>BEAUTIFIED ENHANCED MARKDOWN</label>
            <textarea
              style={{ width: '100%', height: '560px', fontFamily: 'monospace', padding: '16px', borderRadius: '8px', border: '1px solid #1d1d1f', background: '#1d1d1f', color: '#f5f5f7', boxSizing: 'border-box' }}
              readOnly
              value={outputReadme || 'Enhanced README content will render here after processing...'}
            />
          </div>
        )}
      </div>
    </div>
  );
}
