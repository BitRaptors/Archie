import React, { useState } from 'react';

interface ContentInfo {
  content: string;
  char_count: number;
  truncated_from?: number;
}

interface PhaseInfo {
  phase: string;
  timestamp: string;
  gathered: Record<string, { full_content: string; char_count: number }>;
  sent_to_ai: Record<string, ContentInfo | string>;
  rag_retrieved?: { content: string; char_count: number; chunks?: number; files?: number };
}

interface DebugData {
  gathered: {
    file_tree?: { full_content: string; char_count: number };
    dependencies?: { full_content: string; char_count: number };
    config_files?: { files: Array<{ name: string; content: string; char_count: number }>; total_chars: number };
    code_samples?: { files: Array<{ name: string; content: string; char_count: number }>; total_chars: number };
    rag_indexing?: Record<string, any>;
  };
  phases: PhaseInfo[];
  summary: Record<string, any>;
}

interface DebugViewProps {
  data: DebugData | null;
}

export const DebugView: React.FC<DebugViewProps> = ({ data }) => {
  const [activePhaseTab, setActivePhaseTab] = useState<string | null>(null);
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({});

  if (!data) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-gray-500">
        <svg className="w-12 h-12 mb-4 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <p className="text-lg font-medium">No analysis data available</p>
        <p className="text-sm">This analysis was run before data collection was implemented,</p>
        <p className="text-sm">or the analysis is still in progress.</p>
        <p className="text-xs mt-4 text-gray-400">Run a new analysis to see detailed prompts and gathered data.</p>
      </div>
    );
  }

  const toggleSection = (id: string) => {
    setExpandedSections(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const getTruncationBadge = (sent: number, total: number) => {
    const percent = Math.round((sent / total) * 100);
    let color = 'bg-green-100 text-green-800';
    if (percent < 50) color = 'bg-red-100 text-red-800';
    else if (percent < 90) color = 'bg-yellow-100 text-yellow-800';
    
    return (
      <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${color}`}>
        {percent}% sent
      </span>
    );
  };

  const renderCode = (content: string, language: string = 'text') => (
    <pre className="p-4 bg-gray-900 text-gray-100 rounded-lg overflow-x-auto text-xs font-mono max-h-96 overflow-y-auto">
      {content || '(Empty)'}
    </pre>
  );

  const phases = data.phases || [];
  const currentPhase = activePhaseTab ? phases.find(p => p.phase === activePhaseTab) : phases[phases.length - 1];

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      {/* Summary Dashboard */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
          <p className="text-sm text-gray-500 font-medium uppercase tracking-wider">Total Chars Sent</p>
          <p className="text-2xl font-bold text-blue-600">{(data.summary?.total_chars_sent || 0).toLocaleString()}</p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
          <p className="text-sm text-gray-500 font-medium uppercase tracking-wider">Phases Completed</p>
          <p className="text-2xl font-bold text-purple-600">{phases.length}</p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
          <p className="text-sm text-gray-500 font-medium uppercase tracking-wider">RAG Coverage</p>
          <p className="text-2xl font-bold text-green-600">
            {data.gathered?.rag_indexing?.files || 0} files
          </p>
        </div>
        <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
          <p className="text-sm text-gray-500 font-medium uppercase tracking-wider">Total Items Found</p>
          <p className="text-2xl font-bold text-indigo-600">
            {data.gathered?.file_tree?.char_count > 0 ? '✓ Extracted' : '...'}
          </p>
        </div>
      </div>

      {/* Gathered Data Section */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
        <button 
          onClick={() => toggleSection('gathered')}
          className="w-full px-6 py-4 flex items-center justify-between bg-gray-50 hover:bg-gray-100 transition-colors"
        >
          <h3 className="text-lg font-bold text-gray-800 flex items-center">
            <svg className="w-5 h-5 mr-2 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
            Data Gathered from Codebase
          </h3>
          <svg className={`w-5 h-5 transform transition-transform ${expandedSections['gathered'] ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
        
        {expandedSections['gathered'] && (
          <div className="p-6 space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="space-y-2">
                <h4 className="text-sm font-semibold text-gray-700">File Tree Structure (Full)</h4>
                {renderCode(data.gathered?.file_tree?.full_content || '')}
                <p className="text-xs text-gray-500">{data.gathered?.file_tree?.char_count.toLocaleString()} characters</p>
              </div>
              <div className="space-y-2">
                <h4 className="text-sm font-semibold text-gray-700">Dependencies (Full)</h4>
                {renderCode(data.gathered?.dependencies?.full_content || '')}
                <p className="text-xs text-gray-500">{data.gathered?.dependencies?.char_count.toLocaleString()} characters</p>
              </div>
            </div>
            
            <div className="space-y-2">
              <h4 className="text-sm font-semibold text-gray-700">Config Files Found ({data.gathered?.config_files?.files.length || 0})</h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                {data.gathered?.config_files?.files.map((f, i) => (
                  <div key={i} className="px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-xs font-mono truncate">
                    {f.name} <span className="text-gray-400">({f.char_count} chars)</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Phased Analysis View */}
      <div className="space-y-4">
        {phases.length === 0 ? (
          <div className="bg-amber-50 border border-amber-200 rounded-xl p-6 text-center">
            <p className="text-amber-800 font-medium">Phase-by-phase analysis data not available</p>
            <p className="text-amber-600 text-sm mt-1">
              This analysis may have been run before detailed prompt capture was implemented.
            </p>
          </div>
        ) : (
          <div className="flex items-center space-x-2 overflow-x-auto pb-2 scrollbar-hide">
            {phases.map((p, i) => (
              <button
                key={i}
                onClick={() => setActivePhaseTab(p.phase)}
                className={`px-4 py-2 rounded-full text-sm font-semibold whitespace-nowrap transition-all ${
                  (activePhaseTab === p.phase || (!activePhaseTab && i === phases.length - 1))
                    ? 'bg-indigo-600 text-white shadow-md shadow-indigo-200'
                    : 'bg-white text-gray-600 hover:bg-gray-100 border border-gray-200'
                }`}
              >
                {p.phase.replace('phase', 'Phase ').replace('_', ': ')}
              </button>
            ))}
          </div>
        )}

        {currentPhase && (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden animate-in slide-in-from-bottom-2 duration-300">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between bg-white">
              <div>
                <h3 className="text-lg font-bold text-gray-800 uppercase tracking-tight">
                  {currentPhase.phase.replace('_', ' ')}
                </h3>
                <p className="text-xs text-gray-400 font-mono">{currentPhase.timestamp}</p>
              </div>
              <div className="flex space-x-2">
                {currentPhase.rag_retrieved && (
                  <span className="px-2 py-0.5 bg-blue-100 text-blue-800 rounded-full text-xs font-semibold flex items-center">
                    <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                      <path d="M9 9a2 2 0 114 0 2 2 0 01-4 0z" />
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-13a4 4 0 00-3.446 6.032l-2.261 2.26a1 1 0 101.414 1.415l2.261-2.261A4 4 0 1011 5z" clipRule="evenodd" />
                    </svg>
                    RAG Used
                  </span>
                )}
              </div>
            </div>

            <div className="p-6 space-y-8">
              {/* Comparisons */}
              <div className="space-y-6">
                {Object.entries(currentPhase.sent_to_ai).map(([key, sentInfo]) => {
                  if (key === 'full_prompt' || typeof sentInfo === 'string') return null;
                  
                  const gatheredInfo = currentPhase.gathered[key];
                  if (!gatheredInfo) return null;

                  return (
                    <div key={key} className="space-y-2">
                      <div className="flex items-center justify-between">
                        <h4 className="text-sm font-bold text-gray-700 capitalize flex items-center">
                          <span className="w-2 h-2 rounded-full bg-indigo-400 mr-2"></span>
                          {key.replace('_', ' ')}
                        </h4>
                        {getTruncationBadge(sentInfo.char_count, gatheredInfo.char_count)}
                      </div>
                      
                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        <div className="space-y-1">
                          <p className="text-[10px] uppercase font-bold text-gray-400 tracking-widest">Gathered (Full)</p>
                          {renderCode(gatheredInfo.full_content)}
                          <p className="text-[10px] text-gray-400 text-right">{gatheredInfo.char_count.toLocaleString()} chars</p>
                        </div>
                        <div className="space-y-1">
                          <p className="text-[10px] uppercase font-bold text-gray-400 tracking-widest">Sent to AI (Exact)</p>
                          <div className="relative">
                            {renderCode(sentInfo.content)}
                            {sentInfo.char_count < gatheredInfo.char_count && (
                              <div className="absolute bottom-0 left-0 right-0 h-12 bg-gradient-to-t from-red-900/40 to-transparent flex items-end justify-center pb-2 pointer-events-none">
                                <span className="text-[10px] font-bold text-red-200 bg-red-900/80 px-2 py-0.5 rounded backdrop-blur-sm">TRUNCATED</span>
                              </div>
                            )}
                          </div>
                          <p className="text-[10px] text-gray-400 text-right">{sentInfo.char_count.toLocaleString()} chars</p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Exact Prompt */}
              <div className="space-y-2 pt-4 border-t border-gray-100">
                <button 
                  onClick={() => toggleSection(`prompt-${currentPhase.phase}`)}
                  className="flex items-center text-sm font-bold text-gray-700 hover:text-indigo-600 transition-colors"
                >
                  <svg className={`w-4 h-4 mr-1 transition-transform ${expandedSections[`prompt-${currentPhase.phase}`] ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                  VIEW EXACT PROMPT SENT TO AI
                </button>
                {expandedSections[`prompt-${currentPhase.phase}`] && (
                  <div className="mt-2 animate-in fade-in slide-in-from-top-1 duration-200">
                    {renderCode(typeof currentPhase.sent_to_ai.full_prompt === 'string' ? currentPhase.sent_to_ai.full_prompt : '')}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

