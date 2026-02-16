import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Database,
  Layers,
  ChevronDown,
  CheckCircle2,
  Search,
  FileCode,
  AlertCircle,
  MessageSquare,
  Clock,
  Zap,
  Box,
  Code
} from 'lucide-react';
import { cn } from '@/lib/utils';

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
  output?: string;
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
      <div className="flex flex-col items-center justify-center py-20 text-muted-foreground bg-slate-50/50 rounded-xl border border-dashed border-slate-300">
        <AlertCircle className="w-12 h-12 mb-4 opacity-20" />
        <p className="text-lg font-semibold text-slate-900">No analysis data available</p>
        <p className="text-sm max-w-xs text-center mt-1">
          This analysis was run before data collection was implemented or is still in progress.
        </p>
        <p className="text-xs mt-6 px-3 py-1 bg-white border rounded-full shadow-sm">
          Run a new analysis to see detailed prompts.
        </p>
      </div>
    );
  }

  const toggleSection = (id: string) => {
    setExpandedSections(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const getTruncationBadge = (sent: number, total: number) => {
    const percent = Math.round((sent / total) * 100);
    let variant: "default" | "secondary" | "destructive" | "outline" = "outline";

    if (percent < 50) variant = "destructive";
    else if (percent < 90) variant = "secondary";
    else variant = "default";

    return (
      <Badge variant={variant} className="font-mono text-[10px] px-1.5 py-0">
        {percent}% sent
      </Badge>
    );
  };

  const renderCode = (content: string, language: string = 'text', maxH: string = 'max-h-96') => (
    <pre className={`p-4 bg-slate-950 text-slate-50 rounded-lg overflow-x-auto text-[11px] font-mono ${maxH} overflow-y-auto leading-relaxed border border-slate-800 shadow-inner`}>
      {content || '(Empty)'}
    </pre>
  );

  const renderMarkdown = (content: string) => (
    <div className="prose prose-sm max-w-none text-slate-800 bg-slate-50/50 p-6 rounded-xl border border-slate-200/60 shadow-sm leading-relaxed">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );

  const phases = data.phases || [];
  const currentPhase = activePhaseTab ? phases.find(p => p.phase === activePhaseTab) : phases[phases.length - 1];

  return (
    <div className="space-y-6 animate-in fade-in duration-700">
      {/* Summary Dashboard */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="bg-white/50 backdrop-blur-sm border-slate-200">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-bold text-slate-500 uppercase tracking-widest flex items-center gap-2">
              <Zap className="w-3.5 h-3.5" /> Total Chars Sent
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-black text-blue-600 tracking-tighter">
              {(data.summary?.total_chars_sent || 0).toLocaleString()}
            </p>
          </CardContent>
        </Card>

        <Card className="bg-white/50 backdrop-blur-sm border-slate-200">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-bold text-slate-500 uppercase tracking-widest flex items-center gap-2">
              <Layers className="w-3.5 h-3.5" /> Phases Completed
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-black text-purple-600 tracking-tighter">{phases.length}</p>
          </CardContent>
        </Card>

        <Card className="bg-white/50 backdrop-blur-sm border-slate-200">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-bold text-slate-500 uppercase tracking-widest flex items-center gap-2">
              <Box className="w-3.5 h-3.5" /> RAG Coverage
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-black text-emerald-600 tracking-tighter">
              {data.gathered?.rag_indexing?.files || 0} <span className="text-sm font-bold opacity-50">files</span>
            </p>
          </CardContent>
        </Card>

        <Card className="bg-white/50 backdrop-blur-sm border-slate-200">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-bold text-slate-500 uppercase tracking-widest flex items-center gap-2">
              <Search className="w-3.5 h-3.5" /> File Tree
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-black text-indigo-600 tracking-tighter">
              {(data.gathered?.file_tree?.char_count || 0) > 0 ? 'READY' : '...'}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Gathered Data Section */}
      <Card className="overflow-hidden border-slate-200 shadow-sm transition-all hover:shadow-md">
        <button
          onClick={() => toggleSection('gathered')}
          className="w-full px-6 py-4 flex items-center justify-between bg-slate-50/80 hover:bg-slate-100/80 transition-colors group"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 bg-white rounded-lg border border-slate-200 shadow-sm group-hover:scale-110 transition-transform">
              <Database className="w-5 h-5 text-indigo-500" />
            </div>
            <div className="text-left">
              <h3 className="text-sm font-bold text-slate-900 leading-none">Codebase Discovery Results</h3>
              <p className="text-[10px] text-slate-500 mt-1 uppercase font-bold tracking-wider">Raw data gathered during indexing</p>
            </div>
          </div>
          <ChevronDown className={cn("w-5 h-5 text-slate-400 transform transition-transform duration-300", expandedSections['gathered'] && "rotate-180")} />
        </button>

        {expandedSections['gathered'] && (
          <CardContent className="p-6 space-y-8 animate-in slide-in-from-top-2 duration-300">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="space-y-3">
                <div className="flex items-center justify-between px-1">
                  <h4 className="text-[11px] font-bold text-slate-700 uppercase tracking-widest flex items-center gap-2">
                    <FileCode className="w-3.5 h-3.5 text-blue-500" /> File Tree Structure
                  </h4>
                  <Badge variant="outline" className="text-[10px] font-mono text-slate-500">{data.gathered?.file_tree?.char_count.toLocaleString()} chars</Badge>
                </div>
                {renderCode(data.gathered?.file_tree?.full_content || '')}
              </div>
              <div className="space-y-3">
                <div className="flex items-center justify-between px-1">
                  <h4 className="text-[11px] font-bold text-slate-700 uppercase tracking-widest flex items-center gap-2">
                    <Box className="w-3.5 h-3.5 text-purple-500" /> Full Dependencies
                  </h4>
                  <Badge variant="outline" className="text-[10px] font-mono text-slate-500">{data.gathered?.dependencies?.char_count.toLocaleString()} chars</Badge>
                </div>
                {renderCode(data.gathered?.dependencies?.full_content || '')}
              </div>
            </div>

            <div className="space-y-3">
              <h4 className="text-[11px] font-bold text-slate-700 uppercase tracking-widest px-1">
                Config Files Handled ({data.gathered?.config_files?.files.length || 0})
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
                {data.gathered?.config_files?.files.map((f, i) => (
                  <div key={i} className="px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-[10px] font-mono text-slate-600 flex items-center justify-between hover:border-indigo-200 transition-colors">
                    <span className="truncate">{f.name}</span>
                    <span className="text-slate-400 font-medium ml-2 shrink-0">{f.char_count}c</span>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        )}
      </Card>

      {/* Phased Analysis View */}
      <div className="space-y-6">
        <div className="flex items-center gap-3 mb-2">
          <div className="p-1.5 bg-amber-100 rounded-md">
            <Clock className="w-4 h-4 text-amber-700" />
          </div>
          <h3 className="text-sm font-bold text-slate-900 uppercase tracking-widest">Phased Execution History</h3>
        </div>

        {phases.length === 0 ? (
          <div className="bg-amber-50/50 border border-amber-200/50 rounded-xl p-8 text-center">
            <AlertCircle className="w-8 h-8 text-amber-400 mx-auto mb-3" />
            <p className="text-amber-900 font-bold">Phase-by-phase data unavailable</p>
            <p className="text-amber-700 text-xs mt-1 max-w-sm mx-auto">
              This specific analysis run did not record granular phase information.
              Run a new analysis to see the full reasoning history.
            </p>
          </div>
        ) : (
          <div className="flex items-center gap-2 overflow-x-auto pb-4 scrollbar-hide px-1">
            {phases.map((p, i) => (
              <Button
                key={i}
                variant={(activePhaseTab === p.phase || (!activePhaseTab && i === phases.length - 1)) ? "default" : "outline"}
                size="sm"
                onClick={() => setActivePhaseTab(p.phase)}
                className={cn(
                  "rounded-full px-5 h-9 font-bold text-[11px] uppercase tracking-wider transition-all",
                  (activePhaseTab === p.phase || (!activePhaseTab && i === phases.length - 1))
                    ? "bg-indigo-600 text-white shadow-md shadow-indigo-100 border-transparent"
                    : "bg-white text-slate-600 hover:bg-slate-50 border-slate-200 shadow-sm"
                )}
              >
                {p.phase.replace('phase', '').replace('_', ' ').trim()}
              </Button>
            ))}
          </div>
        )}

        {currentPhase && (
          <Card className="border-slate-200 shadow-md ring-1 ring-slate-950/5 animate-in slide-in-from-bottom-4 duration-500 overflow-hidden">
            <div className="px-6 py-6 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-xl bg-white border border-slate-200 flex items-center justify-center shadow-sm">
                  <Code className="w-5 h-5 text-indigo-500" />
                </div>
                <div>
                  <h3 className="text-lg font-black text-slate-900 uppercase tracking-tighter leading-none">
                    {currentPhase.phase.replace('_', ' ')}
                  </h3>
                  <div className="flex items-center gap-2 mt-1.5">
                    <Badge variant="outline" className="text-[10px] font-mono text-slate-400 px-1 border-slate-200">{currentPhase.timestamp}</Badge>
                  </div>
                </div>
              </div>
              <div className="flex gap-2">
                {currentPhase.rag_retrieved && (
                  <Badge className="bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-50 uppercase text-[9px] font-black tracking-widest py-1 px-2.5">
                    <Zap className="w-3 h-3 mr-1 fill-blue-500 text-blue-500" /> RAG Context Used
                  </Badge>
                )}
              </div>
            </div>

            <div className="p-6 md:p-8 space-y-8">
              {/* Context Comparisons */}
              <div className="space-y-8">
                {Object.entries(currentPhase.sent_to_ai).map(([key, sentInfo]) => {
                  if (key === 'full_prompt' || typeof sentInfo === 'string') return null;

                  const gatheredInfo = currentPhase.gathered[key];
                  if (!gatheredInfo) return null;

                  return (
                    <div key={key} className="space-y-3">
                      <div className="flex items-center justify-between px-1">
                        <h4 className="text-[11px] font-black text-slate-800 uppercase tracking-widest flex items-center gap-2">
                          <span className="w-2.5 h-2.5 rounded-full bg-indigo-500 border-2 border-white shadow-sm"></span>
                          {key.replace('_', ' ')}
                        </h4>
                        {getTruncationBadge(sentInfo.char_count, gatheredInfo.char_count)}
                      </div>

                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        <div className="space-y-1.5">
                          <p className="text-[9px] uppercase font-bold text-slate-400 tracking-[0.2em] ml-1">Original Content</p>
                          {renderCode(gatheredInfo.full_content, 'text', 'max-h-64')}
                          <p className="text-[9px] text-slate-400 text-right font-mono pr-1">{gatheredInfo.char_count.toLocaleString()} characters</p>
                        </div>
                        <div className="space-y-1.5">
                          <p className="text-[9px] uppercase font-bold text-slate-400 tracking-[0.2em] ml-1">Sent to AI (Final)</p>
                          <div className="relative">
                            {renderCode(sentInfo.content, 'text', 'max-h-64')}
                            {sentInfo.char_count < gatheredInfo.char_count && (
                              <div className="absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-red-600/10 to-transparent pointer-events-none flex items-end justify-center pb-2">
                                <Badge variant="destructive" className="text-[8px] font-black scale-90 h-4 border-none shadow-lg">TRUNCATED</Badge>
                              </div>
                            )}
                          </div>
                          <p className="text-[9px] text-slate-400 text-right font-mono pr-1">{sentInfo.char_count.toLocaleString()} characters</p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Phase Outcome (Response) */}
              {currentPhase.output && (
                <div className="space-y-4 pt-8 border-t border-slate-100">
                  <div className="flex items-center gap-3 mb-1">
                    <div className="p-1.5 bg-indigo-50 rounded-lg">
                      <MessageSquare className="w-4 h-4 text-indigo-600" />
                    </div>
                    <h4 className="text-sm font-black text-slate-900 uppercase tracking-tight">Phase Analysis Outcome</h4>
                  </div>
                  {renderMarkdown(currentPhase.output)}
                </div>
              )}

              {/* Exact Prompt */}
              <div className="pt-6 border-t border-slate-100">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => toggleSection(`prompt-${currentPhase.phase}`)}
                  className="h-8 -ml-2 text-[10px] font-bold text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 transition-all uppercase tracking-widest gap-2"
                >
                  <ChevronDown className={cn("w-3.5 h-3.5 transform transition-transform duration-200", expandedSections[`prompt-${currentPhase.phase}`] && "rotate-180")} />
                  {expandedSections[`prompt-${currentPhase.phase}`] ? 'Hide' : 'Show'} Full AI Prompt History
                </Button>

                {expandedSections[`prompt-${currentPhase.phase}`] && (
                  <div className="mt-4 animate-in fade-in slide-in-from-top-2 duration-300">
                    <div className="p-1.5 bg-slate-100 rounded-t-lg border-x border-t border-slate-200 text-[9px] font-black text-slate-500 uppercase tracking-widest px-4">
                      Complete LLM Request Buffer
                    </div>
                    {renderCode(typeof currentPhase.sent_to_ai.full_prompt === 'string' ? currentPhase.sent_to_ai.full_prompt : '')}
                  </div>
                )}
              </div>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
};

