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
import { theme } from '@/lib/theme';
import { MermaidDiagram } from '@/components/MermaidDiagram';

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
      <div className={cn("flex flex-col items-center justify-center py-20 text-muted-foreground rounded-xl", theme.surface.emptyState)}>
        <AlertCircle className="w-12 h-12 mb-4 opacity-20" />
        <p className="text-lg font-semibold text-foreground">No analysis data available</p>
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
    <pre className={cn("p-4 rounded-lg overflow-x-auto text-[11px] font-mono overflow-y-auto leading-relaxed", theme.console.bg, theme.console.text, maxH)}>
      {content || '(Empty)'}
    </pre>
  );

  const renderMarkdown = (content: string) => (
    <div className={cn("prose prose-sm max-w-none text-foreground/90 p-6 rounded-xl leading-relaxed", theme.surface.markdown)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ className, children, ...props }: any) {
            if (className === 'language-mermaid') {
              return <MermaidDiagram chart={String(children).trim()} />
            }
            return <code className={className} {...props}>{children}</code>
          },
          pre({ children, node, ...props }: any) {
            const child = node?.children?.[0] as any
            if (child?.tagName === 'code' && child?.properties?.className?.[0] === 'language-mermaid') {
              return <>{children}</>
            }
            return <pre {...props}>{children}</pre>
          }
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );

  const phases = data.phases || [];
  const currentPhase = activePhaseTab ? phases.find(p => p.phase === activePhaseTab) : phases[phases.length - 1];

  return (
    <div className="space-y-6 animate-in fade-in duration-700">
      {/* Summary Dashboard */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className={cn("bg-white/50 backdrop-blur-sm", theme.surface.cardBorder)}>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-bold text-muted-foreground uppercase tracking-widest flex items-center gap-2">
              <Zap className="w-3.5 h-3.5" /> Total Chars Sent
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className={cn("text-3xl font-black tracking-tighter", theme.brand.statTeal)}>
              {(data.summary?.total_chars_sent || 0).toLocaleString()}
            </p>
          </CardContent>
        </Card>

        <Card className={cn("bg-white/50 backdrop-blur-sm", theme.surface.cardBorder)}>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-bold text-muted-foreground uppercase tracking-widest flex items-center gap-2">
              <Layers className="w-3.5 h-3.5" /> Phases Completed
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className={cn("text-3xl font-black tracking-tighter", theme.brand.statPurple)}>{phases.length}</p>
          </CardContent>
        </Card>

        <Card className={cn("bg-white/50 backdrop-blur-sm", theme.surface.cardBorder)}>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-bold text-muted-foreground uppercase tracking-widest flex items-center gap-2">
              <Box className="w-3.5 h-3.5" /> RAG Coverage
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className={cn("text-3xl font-black tracking-tighter", theme.brand.statEmerald)}>
              {data.gathered?.rag_indexing?.files || 0} <span className="text-sm font-bold opacity-50">files</span>
            </p>
          </CardContent>
        </Card>

        <Card className={cn("bg-white/50 backdrop-blur-sm", theme.surface.cardBorder)}>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-bold text-muted-foreground uppercase tracking-widest flex items-center gap-2">
              <Search className="w-3.5 h-3.5" /> File Tree
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className={cn("text-3xl font-black tracking-tighter", theme.brand.statTangerine)}>
              {(data.gathered?.file_tree?.char_count || 0) > 0 ? 'READY' : '...'}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Gathered Data Section */}
      <Card className={cn("overflow-hidden shadow-sm transition-all hover:shadow-md", theme.surface.cardBorder)}>
        <button
          onClick={() => toggleSection('gathered')}
          className={cn("w-full px-6 py-4 flex items-center justify-between transition-colors group", theme.surface.sectionHeader)}
        >
          <div className="flex items-center gap-3">
            <div className={cn("p-2 rounded-lg group-hover:scale-110 transition-transform", theme.surface.sectionHeaderIcon)}>
              <Database className={cn("w-5 h-5", theme.brand.icon)} />
            </div>
            <div className="text-left">
              <h3 className="text-sm font-bold text-foreground leading-none">Codebase Discovery Results</h3>
              <p className="text-[10px] text-muted-foreground mt-1 uppercase font-bold tracking-wider">Raw data gathered during indexing</p>
            </div>
          </div>
          <ChevronDown className={cn("w-5 h-5 text-muted-foreground transform transition-transform duration-300", expandedSections['gathered'] && "rotate-180")} />
        </button>

        {expandedSections['gathered'] && (
          <CardContent className="p-6 space-y-8 animate-in slide-in-from-top-2 duration-300">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="space-y-3">
                <div className="flex items-center justify-between px-1">
                  <h4 className="text-[11px] font-bold text-foreground/80 uppercase tracking-widest flex items-center gap-2">
                    <FileCode className={cn("w-3.5 h-3.5", theme.active.iconColor)} /> File Tree Structure
                  </h4>
                  <Badge variant="outline" className="text-[10px] font-mono text-muted-foreground">{data.gathered?.file_tree?.char_count.toLocaleString()} chars</Badge>
                </div>
                {renderCode(data.gathered?.file_tree?.full_content || '')}
              </div>
              <div className="space-y-3">
                <div className="flex items-center justify-between px-1">
                  <h4 className="text-[11px] font-bold text-foreground/80 uppercase tracking-widest flex items-center gap-2">
                    <Box className="w-3.5 h-3.5 text-purple-500" /> Full Dependencies
                  </h4>
                  <Badge variant="outline" className="text-[10px] font-mono text-muted-foreground">{data.gathered?.dependencies?.char_count.toLocaleString()} chars</Badge>
                </div>
                {renderCode(data.gathered?.dependencies?.full_content || '')}
              </div>
            </div>

            <div className="space-y-3">
              <h4 className="text-[11px] font-bold text-foreground/80 uppercase tracking-widest px-1">
                Config Files Handled ({data.gathered?.config_files?.files.length || 0})
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
                {data.gathered?.config_files?.files.map((f, i) => (
                  <div key={i} className={cn("px-3 py-2 rounded-lg text-[10px] font-mono text-foreground/80 flex items-center justify-between transition-colors", theme.surface.chip, theme.surface.chipHover)}>
                    <span className="truncate">{f.name}</span>
                    <span className="text-muted-foreground font-medium ml-2 shrink-0">{f.char_count}c</span>
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
          <h3 className="text-sm font-bold text-foreground uppercase tracking-widest">Phased Execution History</h3>
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
                    ? theme.active.phasePill
                    : theme.surface.inactivePhase
                )}
              >
                {p.phase.replace('phase', '').replace('_', ' ').trim()}
              </Button>
            ))}
          </div>
        )}

        {currentPhase && (
          <Card className={cn("shadow-md animate-in slide-in-from-bottom-4 duration-500 overflow-hidden", theme.surface.cardBorder, theme.surface.cardRing)}>
            <div className={cn("px-6 py-6 border-b flex items-center justify-between", theme.surface.dividerStrong, theme.surface.footer)}>
              <div className="flex items-center gap-4">
                <div className={cn("w-10 h-10 rounded-xl flex items-center justify-center", theme.surface.sectionHeaderIcon)}>
                  <Code className={cn("w-5 h-5", theme.brand.icon)} />
                </div>
                <div>
                  <h3 className="text-lg font-black text-foreground uppercase tracking-tighter leading-none">
                    {currentPhase.phase.replace('_', ' ')}
                  </h3>
                  <div className="flex items-center gap-2 mt-1.5">
                    <Badge variant="outline" className={cn("text-[10px] font-mono text-muted-foreground px-1", theme.surface.cardBorder)}>{currentPhase.timestamp}</Badge>
                  </div>
                </div>
              </div>
              <div className="flex gap-2">
                {currentPhase.rag_retrieved && (
                  <Badge className={cn("uppercase text-[9px] font-black tracking-widest py-1 px-2.5", theme.brand.ragBadge)}>
                    <Zap className="w-3 h-3 mr-1 fill-current" /> RAG Context Used
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
                        <h4 className="text-[11px] font-black text-foreground/90 uppercase tracking-widest flex items-center gap-2">
                          <span className={cn("w-2.5 h-2.5 rounded-full", theme.brand.sectionDot)}></span>
                          {key.replace('_', ' ')}
                        </h4>
                        {getTruncationBadge(sentInfo.char_count, gatheredInfo.char_count)}
                      </div>

                      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                        <div className="space-y-1.5">
                          <p className="text-[9px] uppercase font-bold text-muted-foreground tracking-[0.2em] ml-1">Original Content</p>
                          {renderCode(gatheredInfo.full_content, 'text', 'max-h-64')}
                          <p className="text-[9px] text-muted-foreground text-right font-mono pr-1">{gatheredInfo.char_count.toLocaleString()} characters</p>
                        </div>
                        <div className="space-y-1.5">
                          <p className="text-[9px] uppercase font-bold text-muted-foreground tracking-[0.2em] ml-1">Sent to AI (Final)</p>
                          <div className="relative">
                            {renderCode(sentInfo.content, 'text', 'max-h-64')}
                            {sentInfo.char_count < gatheredInfo.char_count && (
                              <div className={cn("absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t to-transparent pointer-events-none flex items-end justify-center pb-2", theme.truncation.gradient)}>
                                <Badge variant="destructive" className="text-[8px] font-black scale-90 h-4 border-none shadow-lg">TRUNCATED</Badge>
                              </div>
                            )}
                          </div>
                          <p className="text-[9px] text-muted-foreground text-right font-mono pr-1">{sentInfo.char_count.toLocaleString()} characters</p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Phase Outcome (Response) */}
              {currentPhase.output && (
                <div className={cn("space-y-4 pt-8 border-t", theme.surface.dividerStrong)}>
                  <div className="flex items-center gap-3 mb-1">
                    <div className={cn("p-1.5 rounded-lg", theme.brand.phaseOutcomeIcon)}>
                      <MessageSquare className={cn("w-4 h-4", theme.brand.icon)} />
                    </div>
                    <h4 className="text-sm font-black text-foreground uppercase tracking-tight">Phase Analysis Outcome</h4>
                  </div>
                  {renderMarkdown(currentPhase.output)}
                </div>
              )}

              {/* Exact Prompt */}
              <div className={cn("pt-6 border-t", theme.surface.dividerStrong)}>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => toggleSection(`prompt-${currentPhase.phase}`)}
                  className={cn("h-8 -ml-2 text-[10px] font-bold text-muted-foreground transition-all uppercase tracking-widest gap-2", theme.interactive.ghostBrand)}
                >
                  <ChevronDown className={cn("w-3.5 h-3.5 transform transition-transform duration-200", expandedSections[`prompt-${currentPhase.phase}`] && "rotate-180")} />
                  {expandedSections[`prompt-${currentPhase.phase}`] ? 'Hide' : 'Show'} Full AI Prompt History
                </Button>

                {expandedSections[`prompt-${currentPhase.phase}`] && (
                  <div className="mt-4 animate-in fade-in slide-in-from-top-2 duration-300">
                    <div className={cn("p-1.5 rounded-t-lg border-x border-t text-[9px] font-black text-muted-foreground uppercase tracking-widest px-4", theme.surface.promptHeader)}>
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
