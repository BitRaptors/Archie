"use strict";
"use client";

import { useEffect, useRef, useState } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { Github, ArrowUpRight, FileText, Folder, Search, X, Maximize2 } from "lucide-react";
import { ShaderBackground } from "@/components/ShaderBackground";
import { motion, useScroll, useSpring, AnimatePresence } from "framer-motion";
import { MarkdownRenderer } from "@/components/MarkdownRenderer";
import { FileTree } from "@/components/FileTree";
import { EXAMPLE_FILES } from "./example-files";

gsap.registerPlugin(ScrollTrigger);

const EXAMPLE_FILE_PATHS = Object.keys(EXAMPLE_FILES).sort();
const DEFAULT_FILE = "AGENTS.md";

const ExampleFileContent = ({ filePath }: { filePath: string }) => {
  const content = EXAMPLE_FILES[filePath];
  if (!content) {
    return (
      <div className="text-gray-500 text-sm font-mono p-8 text-center">
        <FileText className="w-8 h-8 mx-auto mb-3 opacity-30" />
        Select a file to preview
      </div>
    );
  }

  const isMarkdown = filePath.endsWith(".md");
  const fileName = filePath.includes("/") ? filePath : `root/${filePath}`;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-3 text-sky-blue border-b border-white/10 pb-4 mb-4 shrink-0">
        {filePath.includes("/") ? <Folder className="w-5 h-5" /> : <FileText className="w-5 h-5" />}
        <span className="font-black tracking-widest uppercase text-sm">{fileName}</span>
      </div>
      <div className="flex-1 overflow-hidden">
        {isMarkdown ? (
          <MarkdownRenderer content={content} />
        ) : (
          <pre className="bg-black/60 border border-white/10 rounded px-4 py-3 overflow-x-auto text-[11px] md:text-xs leading-relaxed">
            <code className="text-[#39ff14]/80 font-mono">{content}</code>
          </pre>
        )}
      </div>
    </div>
  );
};

export default function LandingPage() {
  const [activeFile, setActiveFile] = useState(DEFAULT_FILE);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isCtaHovered, setIsCtaHovered] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll();
  const scaleProgress = useSpring(scrollYProgress, { stiffness: 100, damping: 30 });

  useEffect(() => {
    // GSAP Scroll Animations
    const ctx = gsap.context(() => {
      // 1. Hero Heading Logic (Centered, subtle move - the "perfect" one)
      gsap.to(".hero-heading", {
        x: () => -(document.querySelector(".hero-heading")?.scrollWidth || 0 - window.innerWidth) / 4,
        rotation: -5,
        ease: "none",
        scrollTrigger: {
          trigger: ".hero-heading",
          start: "top center",
          end: "bottom top",
          scrub: 1,
        },
      });

      // 2. Side-to-side scroll for subsequent headings
      gsap.utils.toArray(".scrub-heading:not(.hero-heading)").forEach((heading: any, i: number) => {
        const direction = i % 2 === 0 ? 1 : -1;
        gsap.fromTo(heading,
          { x: direction * 500 },
          {
            x: direction * -500,
            rotation: i % 2 === 0 ? -2 : 2,
            ease: "none",
            scrollTrigger: {
              trigger: heading,
              start: "top bottom",
              end: "bottom top",
              scrub: 1,
            },
          }
        );
      });

      // 3. Parallax Images
      gsap.utils.toArray(".parallax-img-container").forEach((container: any) => {
        const img = container.querySelector(".parallax-img");
        if (img) {
          gsap.to(img, {
            y: "25%",
            ease: "none",
            scrollTrigger: {
              trigger: container,
              start: "top bottom",
              end: "bottom top",
              scrub: true,
            },
          });
        }
      });

      // 4. Fade Up
      gsap.utils.toArray(".fade-up").forEach((elem: any) => {
        gsap.from(elem, {
          y: 100,
          opacity: 0,
          duration: 1.5,
          ease: "power4.out",
          scrollTrigger: {
            trigger: elem,
            start: "top 85%",
            toggleActions: "play none none reverse",
          },
        });
      });
    }, containerRef);

    return () => ctx.revert();
  }, []);

  return (
    <main
      ref={containerRef}
      className="relative bg-deep-space-blue text-foreground selection:bg-neon selection:text-black min-h-screen antialiased"
    >
      {/* Scroll Progress Bar */}
      <motion.div
        className="fixed top-0 left-0 right-0 h-1 bg-neon z-50 origin-left"
        style={{ scaleX: scaleProgress }}
      />

      {/* Sticky Feedback Badge & Raptor */}
      <div className="fixed bottom-6 right-6 z-50 flex flex-col items-center pointer-events-none overflow-visible">
        {/* Raptor SVG peaking out from behind the badge */}
        <motion.div
          initial={{ y: 60, opacity: 0 }}
          animate={{
            y: isCtaHovered ? -40 : 60,
            opacity: isCtaHovered ? 1 : 0
          }}
          transition={{
            type: "spring",
            stiffness: 260,
            damping: 20
          }}
          className="w-24 h-24 mb-[-20px] overflow-visible"
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/raptor.svg" alt="BitRaptor" className="w-full h-full object-contain drop-shadow-[0_0_15px_rgba(57,255,20,0.5)]" />
        </motion.div>

        <a
          href="https://github.com/BitRaptors/Archie/issues"
          target="_blank"
          rel="noopener noreferrer"
          className="pointer-events-auto relative z-10 transform hover:-translate-y-1 hover:scale-105 transition-all group"
        >
          <div className="bg-neon text-black font-black uppercase tracking-widest px-4 py-2 border-2 border-black shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] flex flex-col items-center gap-1 text-xs brutalist-border">
            <div className="flex items-center gap-2 border-b border-black/20 pb-1 w-full justify-center">
              <span className="animate-pulse w-2 h-2 bg-black rounded-full block"></span>
              PREVIEW
            </div>
            <span>SEND FEEDBACK</span>
          </div>
        </a>
      </div>

      {/* Hero Section */}
      <header className="min-h-screen relative flex flex-col justify-center items-center px-4 overflow-hidden">
        <ShaderBackground />
        <div
          className="absolute inset-0 z-0 opacity-20 pointer-events-none"
          style={{
            backgroundImage: "radial-gradient(#39ff14 1px, transparent 1px)",
            backgroundSize: "40px 40px",
          }}
        ></div>

        <div className="z-10 text-center max-w-7xl mx-auto mt-10 md:mt-0">
          <h1 className="text-4xl md:text-8xl lg:text-9xl font-black mb-12 uppercase tracking-tighter mix-blend-difference text-neon scrub-heading hero-heading inline-block">
            Your agent is only<br />as good as its context.
          </h1>
          <p className="text-xl md:text-2xl text-sky-blue-600 mb-12 max-w-3xl mx-auto border-l-4 border-neon pl-6 text-left bg-black bg-opacity-40 p-6 backdrop-blur-sm">
            Archie integrates directly into Claude Code (or your favorite agent) to watch your architecture. With automatic hooks and per-folder context, it keeps every context file fresh and won't let a single markdown rot away.
          </p>
          <a
            href="https://github.com/BitRaptors/Archie"
            onPointerEnter={() => setIsCtaHovered(true)}
            onPointerLeave={() => setIsCtaHovered(false)}
            className="brutalist-border inline-flex items-center gap-4 px-6 py-4 md:px-12 md:py-6 bg-deep-space-blue text-neon font-bold text-lg md:text-xl uppercase tracking-wider hover:bg-neon hover:text-deep-space-blue transition-colors"
          >
            <Github className="w-8 h-8" />
            Analyze your first repo {"->"}
          </a>
        </div>
      </header>

      {/* Problem Section */}
      <section className="py-32 md:py-40 px-4 bg-deep-space-blue-100 relative border-y-4 border-amber-flame">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row gap-16 lg:gap-24">
          <div className="md:w-1/2 fade-up">
            <h2 className="text-3xl md:text-5xl font-black text-amber-flame uppercase mb-8 border-b-4 border-amber-flame pb-4">
              AI agents are architecturally blind
            </h2>
            <p className="text-xl mb-6 text-gray-300">
              Every session, your AI skims a few files and guesses. It doesn't know your naming conventions, your layer
              boundaries, or where things go.
            </p>
            <p className="text-xl mb-6 text-gray-300">
              After 50 AI-assisted PRs, you have 50 different interpretations of your architecture.
            </p>
            <p className="text-xl font-bold text-neon bg-black p-4 inline-block brutalist-border mt-4 text-center w-full md:w-auto">
              Result: You spend more time fixing AI output than writing code yourself.
            </p>
          </div>
          <div
            className="md:w-1/2 relative min-h-[400px] parallax-img-container border-4 border-blue-green bg-black p-8 flex flex-col justify-center"
            style={{
              borderColor: "#219ebc",
              boxShadow: "8px 8px 0px 0px #219ebc",
            }}
          >
            <div className="text-red-500 font-mono text-sm opacity-80 parallax-img flex flex-col gap-4 p-8 pt-16 filter drop-shadow-lg">
              <div className="bg-red-900 bg-opacity-20 p-2 border border-red-500">{"> Error: File placed in wrong directory"}</div>
              <div className="bg-yellow-900 bg-opacity-20 p-2 border border-yellow-500 text-yellow-500">
                {"> Warning: Naming convention mismatch"}
              </div>
              <div className="bg-red-900 bg-opacity-20 p-2 border border-red-500">{"> Error: Service layer imports from Controller"}</div>
              <div className="mt-12 space-y-10">
                <div className="space-y-4">
                  <div className="flex items-center gap-4">
                    <span className="text-6xl font-black text-amber-flame leading-none tracking-tighter">65%</span>
                    <p className="text-xl text-white font-black uppercase tracking-tight leading-tight">
                      say AI misses context<br />during refactoring.
                    </p>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-6xl font-black text-amber-flame leading-none tracking-tighter">44%</span>
                    <p className="text-xl text-white font-black uppercase tracking-tight leading-tight">
                      blame context gaps<br />for quality degradation.
                    </p>
                  </div>
                </div>

                <div className="pt-8 border-t border-white/10">
                  <a
                    href="https://www.qodo.ai/reports/state-of-ai-code-quality/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group block"
                  >
                    <div className="text-princeton-orange text-2xl font-black uppercase leading-tight group-hover:text-neon transition-all flex items-start gap-3">
                      <span className="flex-1">Not hallucinations. Not model capability. Context.</span>
                      <ArrowUpRight className="w-8 h-8 flex-shrink-0 group-hover:translate-x-1 group-hover:-translate-y-1 transition-transform" />
                    </div>
                    <div className="mt-4 text-gray-500 text-xs font-black uppercase tracking-[0.3em] flex items-center gap-2 group-hover:text-gray-300 transition-colors">
                      <div className="w-8 h-px bg-gray-500"></div>
                      SOURCE: STATE OF AI CODE QUALITY, 2025
                    </div>
                  </a>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Solution Section */}
      <section className="py-32 md:py-40 px-4 bg-deep-space-blue relative overflow-hidden">
        {/* Background Decorative Element */}
        <div className="absolute top-0 right-0 w-[60%] h-full bg-gradient-to-l from-blue-green/10 to-transparent pointer-events-none"></div>
        <div
          className="absolute -right-48 top-1/2 -translate-y-1/2 opacity-[0.03] text-white font-black mix-blend-overlay pointer-events-none select-none"
          style={{ fontSize: '30vh', lineHeight: '1', writingMode: 'vertical-rl' }}
        >
          SOLUTION
        </div>

        <div className="max-w-7xl mx-auto relative z-10">
          <div className="mb-20 md:mb-32 fade-up">
            <span className="text-neon font-black tracking-widest uppercase text-sm mb-4 block px-2 py-1 bg-neon/10 border-l-2 border-neon inline-block">
              01. THE SOLUTION
            </span>
            <h2 className="text-4xl md:text-7xl font-black text-white uppercase mt-4 mb-8">
              Deep analysis,<br />
              <span className="text-neon underline decoration-neon decoration-4 underline-offset-8">not surface scanning.</span>
            </h2>
            <p className="text-xl text-gray-400 max-w-2xl">
              We don't just prompt a model; we build a complete architectural graph and derive rules that agents can actually follow.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 lg:gap-12 text-left">
            <div className="bg-[#031d2b] p-8 md:p-12 hover:shadow-xl transition-shadow fade-up flex flex-col justify-center min-h-[300px]">
              <h3 className="text-3xl font-black text-white mb-6 uppercase tracking-tight">9-Phase Pipeline</h3>
              <p className="text-gray-400 leading-relaxed text-lg">
                Other tools scan your package.json and call it a day. Archie runs a deep AI analysis
                pipeline: observation, discovery, implementation analysis, and synthesis.
              </p>
            </div>

            <div className="bg-[#031d2b] p-8 md:p-12 hover:shadow-xl transition-shadow fade-up flex flex-col justify-center min-h-[300px]">
              <h3 className="text-3xl font-black text-white mb-6 uppercase tracking-tight">Source of Truth</h3>
              <p className="text-gray-400 leading-relaxed text-lg">
                The structured architectural blueprint becomes the truth for every AI tool in your workflow. No more
                scattered instructions or conflicting configurations.
              </p>
            </div>

            <div className="bg-[#031d2b] p-8 md:p-12 hover:shadow-xl transition-shadow fade-up flex flex-col justify-center min-h-[300px]">
              <h3 className="text-3xl font-black text-white mb-6 uppercase tracking-tight">Automatic Updates</h3>
              <p className="text-gray-400 leading-relaxed text-lg">
                As your code evolves, the blueprint evolves with it <strong className="text-amber-flame font-bold">automatically</strong>. Incremental re-
                analysis keeps context current without re-analyzing the entire codebase.
              </p>
            </div>
          </div>

          {/* Analysis Pipeline Screenshot */}
          <div className="mt-24 md:mt-32 fade-up relative group">
            <div className="absolute -inset-1 bg-gradient-to-r from-neon to-blue-green opacity-20 group-hover:opacity-40 blur transition-opacity duration-1000"></div>
            <div className="relative border-4 border-black bg-black rounded-sm overflow-hidden shadow-[8px_8px_0px_0px_rgba(57,255,20,0.2)] md:shadow-[16px_16px_0px_0px_rgba(57,255,20,0.2)]">
              <div className="flex gap-2 top-0 left-0 bg-neon text-black font-black px-6 py-2 text-xl z-20 border-b-4 border-r-4 border-black inline-block">
                LIVE ANALYSIS PIPELINE
              </div>
              <img src="/pipeline.png" alt="Analysis Pipeline" className="w-full h-auto opacity-90 hover:opacity-100 transition-opacity object-cover" />
            </div>
          </div>
        </div>
      </section>

      {/* Native inside Claude Code */}
      <section className="py-32 md:py-40 px-4 bg-deep-space-blue-100 border-t-8 border-neon relative overflow-hidden">
        <div className="max-w-7xl mx-auto fade-up relative z-10">
          <div className="relative mb-20 md:mb-32">
            <h2 className="text-3xl md:text-6xl font-black text-white underline decoration-neon decoration-4 underline-offset-8 uppercase relative z-10">
              Native inside Claude Code
            </h2>

            {/* MCP Stamp Overlay */}
            <div className="absolute -top-24 right-0 md:-right-4 md:-top-32 rotate-12 bg-amber-flame text-black font-black p-2 border-4 border-black shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] z-20 w-[260px] md:w-[280px] text-center transform transition-transform hover:scale-110 hover:rotate-[8deg] brutalist-border">
              <div className="border-2 border-dashed border-black p-3 text-sm tracking-wider uppercase flex flex-col items-center">
                <span className="opacity-90 tracking-tighter mb-1 font-bold">No Claude Code?</span>
                <span className="text-lg bg-black text-amber-flame px-3 py-1 mb-1 block leading-none">We got you covered</span>
                <span className="text-xs tracking-tight">through the built-in MCP server</span>
              </div>
            </div>
          </div>
          <div className="space-y-32">

            {/* Automatic Hooks */}
            <div>
              <h3 className="text-4xl font-black text-white mb-12 uppercase inline-block border-b-4 border-amber-flame pb-2 relative">
                Automatic Hooks
              </h3>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 md:gap-12 tracking-tight">
                <div className="brutalist-border bg-black p-8 relative flex flex-col" style={{ borderColor: "#ffb703", boxShadow: "8px 8px 0px 0px #ffb703" }}>
                  <div className="absolute -top-4 -right-4 bg-amber-flame text-black font-black px-4 py-2 text-lg md:text-xl border-2 border-black">
                    stop-review-and-refresh
                  </div>
                  <div className="text-sky-blue mb-4 text-2xl font-bold pr-16 md:pr-0 mt-2">Validates uncommitted changes</div>
                  <p className="text-gray-400 mb-6 font-mono text-sm leading-relaxed max-w-sm flex-grow">Fires after every response. Collects diffs, sends to smart-refresh API, checks against blueprints, and regenerates stale CLAUDE.md files.</p>
                  <pre className="text-sm md:text-base text-green-400 font-mono bg-gray-900 p-6 border border-gray-700 overflow-x-auto">
                    <code>
                      Session review: 3 file(s) changed.{"\n"}
                      Architecture review (2 findings):{"\n"}
                      <span className="text-amber-flame">  [WARNING]</span> src/api: Outside expected directory{"\n"}
                      <span className="text-red-500">  [ERROR]</span> src/domain: Imports from infrastructure{"\n"}
                      {"\n"}
                      Updated 1 CLAUDE.md file(s):{"\n"}
                      <span className="text-sky-blue">  src/api/routes/CLAUDE.md</span>
                    </code>
                  </pre>
                </div>

                <div className="brutalist-border bg-black p-8 relative flex flex-col" style={{ borderColor: "#8ecae6", boxShadow: "8px 8px 0px 0px #8ecae6" }}>
                  <div className="absolute -top-4 -right-4 bg-sky-blue text-black font-black px-4 py-2 text-lg md:text-xl border-2 border-black">
                    check-architecture-staleness
                  </div>
                  <div className="text-sky-blue mb-4 text-2xl font-bold pr-16 md:pr-0 mt-2">Keeps context fresh</div>
                  <p className="text-gray-400 mb-6 font-mono text-sm leading-relaxed max-w-sm flex-grow">Fires when a new session starts. Compares timestamps of local CLAUDE.md files against the blueprint source. Prompts you to sync if outdated.</p>
                  <pre className="text-sm md:text-base text-green-400 font-mono bg-gray-900 p-6 border border-gray-700 overflow-x-auto">
                    <code>
                      <span className="text-amber-flame">Architecture files are outdated.</span>{"\n"}
                      {"\n"}
                      Run <span className="text-sky-blue">/sync-architecture</span> to update.
                    </code>
                  </pre>
                </div>
              </div>
            </div>

            {/* User-invoked capabilities */}
            <div>
              <h3 className="text-4xl font-black text-white mb-12 uppercase inline-block border-b-4 border-neon pb-2">
                On-Demand Skills
              </h3>

              <div className="space-y-16 lg:space-y-24">
                <div className="brutalist-border bg-black p-8 relative lg:w-[85%]">
                  <div className="absolute -top-4 -right-4 bg-neon text-black font-black px-4 py-2 text-xl border-2 border-black">
                    /where-to-put
                  </div>
                  <div className="text-sky-blue mb-6 text-2xl font-bold">"Where should I put a new payment webhook handler?"</div>
                  <pre className="text-lg text-green-400 font-mono bg-gray-900 p-6 border border-gray-700 overflow-x-auto">
                    <code>
                      Location: worker/webhooks/payment_webhook.py{"\n"}
                      Naming: snake_case, no suffix{"\n"}
                      Pattern: Follow existing handler structure{"\n"}
                      Also update: worker/main.py, tests/webhooks/
                    </code>
                  </pre>
                </div>

                <div
                  className="brutalist-border bg-black p-8 relative ml-4 md:ml-12 lg:w-[85%] lg:ml-auto"
                  style={{
                    borderColor: "#219ebc",
                    boxShadow: "8px 8px 0px 0px #219ebc",
                  }}
                >
                  <div className="absolute -top-4 -right-4 md:-right-6 md:-top-5 bg-blue-green text-black font-black px-4 py-2 text-xl border-2 border-black rotate-1 hover:rotate-0 transition-transform">
                    /check-naming
                  </div>
                  <div className="text-sky-blue mb-6 text-2xl font-bold">"Is PaymentService a good class name?"</div>
                  <pre className="text-lg text-green-400 font-mono bg-gray-900 p-6 border border-gray-700 overflow-x-auto">
                    <code>
                      Name: PaymentService{"\n"}
                      Scope: class{"\n"}
                      Convention: PascalCase, no suffix for services{"\n"}
                      Verdict: <span className="text-black bg-neon px-2 font-black">PASS</span>
                    </code>
                  </pre>
                </div>

                <div
                  className="brutalist-border bg-black p-8 relative ml-8 md:ml-24 lg:w-[85%]"
                  style={{
                    borderColor: "#fb8500",
                    boxShadow: "8px 8px 0px 0px #fb8500",
                  }}
                >
                  <div className="absolute -top-4 -right-4 md:-right-4 md:-top-4 bg-princeton-orange text-black font-black px-4 py-2 text-xl border-2 border-black -rotate-1 hover:rotate-0 transition-transform">
                    /how-to-implement
                  </div>
                  <div className="text-sky-blue mb-6 text-2xl font-bold">"How was push notifications built?"</div>
                  <pre className="text-lg text-green-400 font-mono bg-gray-900 p-6 border border-gray-700 overflow-x-auto">
                    <code>
                      Capability: Push Notifications{"\n"}
                      Libraries: firebase-admin, APNs2{"\n"}
                      Key files: worker/push/sender.py, worker/push/formatters.py{"\n"}
                      {"\n"}
                      Usage:{"\n"}
                      <span className="text-gray-400">  from worker.push.sender import send_push</span>{"\n"}
                      <span className="text-gray-400">  send_push(user_id="abc", title="New msg")</span>{"\n"}
                      {"\n"}
                      Tips: Use existing PushFormatter, don't build payloads manually
                    </code>
                  </pre>
                </div>

                <div className="flex flex-col md:flex-row gap-8 lg:gap-12 mt-20 md:mt-24">
                  <div
                    className="bg-[#111] border-2 border-amber-flame p-8 flex-1 brutalist-border hover:-translate-y-2 transition-transform"
                    style={{
                      borderColor: "#ffb703",
                      boxShadow: "8px 8px 0px 0px #ffb703",
                    }}
                  >
                    <span className="text-amber-flame font-black text-xl md:text-2xl mb-4 block inline-block bg-black px-3 py-1 border border-amber-flame">
                      /check-architecture
                    </span>
                    <p className="text-xl text-gray-300">Validate all uncommitted changes against the blueprint: file placement, naming, and layer boundaries.</p>
                  </div>
                  <div
                    className="bg-[#111] border-2 border-sky-blue p-8 flex-1 brutalist-border hover:-translate-y-2 transition-transform"
                    style={{
                      borderColor: "#8ecae6",
                      boxShadow: "8px 8px 0px 0px #8ecae6",
                    }}
                  >
                    <span className="text-sky-blue font-black text-xl md:text-2xl mb-4 block inline-block bg-black px-3 py-1 border border-sky-blue">
                      /sync-architecture
                    </span>
                    <p className="text-xl text-gray-300">Pull the latest blueprint outputs into your project with smart merging.</p>
                  </div>
                </div>

              </div>
            </div>
          </div>
        </div>
      </section>


      {/* Per-Folder Section */}
      <section className="py-40 px-4 bg-[#0a0a0a] border-b-[16px] border-neon/20 overflow-hidden relative">
        {/* Background Depth */}
        <div className="absolute top-0 left-0 w-full h-full bg-[radial-gradient(circle_at_30%_50%,#023047_0%,transparent_50%)] opacity-40"></div>
        <div
          className="absolute -left-32 top-1/2 -translate-y-1/2 opacity-[0.02] text-neon font-black pointer-events-none select-none"
          style={{ fontSize: '30vh', lineHeight: '1', writingMode: 'vertical-rl' }}
        >
          CONTEXT
        </div>

        <div className="max-w-6xl mx-auto text-center relative z-10">
          <div className="mb-20">
            <h2 className="text-4xl md:text-[10rem] text-sky-blue font-black mb-8 scrub-heading md:whitespace-nowrap inline-block tracking-tighter uppercase">
              Per-Folder Context
            </h2>
            <div className="flex justify-center">
              <p className="text-2xl md:text-3xl font-bold text-white px-8 py-4 bg-neon/10 border-2 border-neon/30 backdrop-blur-md inline-block brutalist-border-sm mb-12">
                "Your AI lands in any folder and immediately knows the rules."
              </p>
            </div>
            <p className="text-2xl text-gray-400 max-w-3xl mx-auto leading-relaxed">
              A single root-level CLAUDE.md doesn't scale. Your frontend has different patterns than your backend.
              Archie generates per-folder files to keep focus tight and relevant.
            </p>
          </div>

          <div className="bg-[#111]/80 backdrop-blur-xl p-12 md:p-20 border border-white/5 mx-auto max-w-4xl relative mb-12 group">
            <div className="absolute -top-1 -left-1 w-20 h-20 border-t-2 border-l-2 border-neon opacity-50 group-hover:w-full group-hover:h-full transition-all duration-700"></div>
            <div className="absolute -bottom-1 -right-1 w-20 h-20 border-b-2 border-r-2 border-sky-blue opacity-50 group-hover:w-full group-hover:h-full transition-all duration-700"></div>

            <h3 className="text-4xl font-black text-neon mb-8 uppercase tracking-widest">Compound Learning</h3>
            <p className="text-2xl text-gray-300 mb-10 leading-relaxed">
              Stop teaching your AI the same lessons twice. Every session starts from deep-rooted project knowledge, not a blank slate.
            </p>

            <blockquote className="relative p-10 bg-black/40 border border-white/5 shadow-2xl overflow-hidden">
              <div className="absolute top-0 left-0 w-1 h-full bg-gradient-to-b from-neon to-sky-blue"></div>
              <p className="text-xl italic text-gray-300 text-left relative z-10 leading-relaxed">
                "Well-maintained project knowledge compounds: each documented subsystem accelerates not only its own future modifications but every adjacent feature that depends on it."
              </p>
              <footer className="mt-8 flex justify-end">
                <a
                  href="https://arxiv.org/html/2602.20478v1"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group inline-flex items-center gap-2 text-sky-blue font-black text-xl uppercase tracking-widest hover:text-neon transition-all"
                >
                  <span className="group-hover:underline decoration-neon decoration-2 underline-offset-4">Codified Context, ARXIV 2026</span>
                  <ArrowUpRight className="w-5 h-5 group-hover:translate-x-1 group-hover:-translate-y-1 transition-transform" />
                </a>
              </footer>
            </blockquote>
          </div>

        </div>
      </section>

      {/* Showcase Example Output Section */}
      <section id="showcase" className="pt-24 pb-12 md:pt-32 md:pb-16 px-4 bg-black relative overflow-hidden border-t-8 border-sky-blue/30">
        <div className="absolute top-0 right-0 w-[50%] h-full bg-[radial-gradient(circle_at_70%_50%,#023047_0%,transparent_70%)] opacity-30"></div>

        <div className="max-w-7xl mx-auto relative z-10">
          <div className="mb-12 fade-up text-left">
            <span className="text-sky-blue font-black tracking-widest uppercase text-sm mb-4 block px-2 py-1 bg-sky-blue/10 border-l-2 border-sky-blue inline-block">
              02. THE OUTPUT
            </span>
            <h2 className="text-4xl md:text-7xl font-black text-white uppercase mt-4 mb-8">
              See it in <span className="text-sky-blue underline decoration-sky-blue decoration-4 underline-offset-8">action.</span>
            </h2>
            <p className="text-xl text-gray-400 max-w-2xl">
              Archie produces high-density, actionable documentation that turns any LLM into a project expert.
              Zero fluff. Pure architectural intent.
            </p>
          </div>

          <div className="fade-up flex flex-col lg:flex-row lg:gap-0 gap-4 border-4 border-gray-800 bg-[#0a0a0a] relative group/showcase shadow-[12px_12px_0px_0px_rgba(33,158,188,0.1)]">
            {/* File Tree */}
            <div className="lg:w-[280px] shrink-0 border-r border-gray-800 hidden lg:block overflow-hidden h-[600px] relative">
              <FileTree
                filePaths={EXAMPLE_FILE_PATHS}
                activePath={activeFile}
                onSelect={setActiveFile}
              />
              <div className="absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-[#0a0a0a] to-transparent pointer-events-none"></div>
            </div>

            {/* Mobile: file selector */}
            <div className="lg:hidden px-4 pt-4">
              <select
                value={activeFile}
                onChange={(e) => setActiveFile(e.target.value)}
                className="w-full bg-black border border-gray-800 text-gray-300 font-mono text-xs p-2 uppercase tracking-wider"
              >
                {EXAMPLE_FILE_PATHS.map((p) => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>

            {/* Content */}
            <div className="flex-1 p-6 font-mono text-sm h-[600px] overflow-hidden relative">
              <ExampleFileContent filePath={activeFile} />
              <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-[#0a0a0a] to-transparent pointer-events-none"></div>
            </div>

            {/* Full Screen */}
            <div className="absolute bottom-4 right-4 opacity-0 group-hover/showcase:opacity-100 transition-opacity">
              <button
                onClick={() => setIsModalOpen(true)}
                className="bg-gray-800 hover:bg-neon hover:text-black text-gray-400 px-4 py-2 rounded-full flex items-center gap-2 text-xs font-bold uppercase tracking-widest transition-colors"
              >
                <Maximize2 className="w-4 h-4" />
                See the full file
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* What Gets Generated & By the Numbers */}
      <section className="pt-12 pb-24 md:pt-16 md:pb-32 px-4 bg-black relative">
        <div className="max-w-7xl mx-auto z-10 relative fade-up">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-16 lg:gap-24">
            <div className="text-left">
              <h2 className="text-3xl md:text-5xl font-black text-white mb-10 border-b-4 border-white pb-4 uppercase">
                WHAT GETS GENERATED
              </h2>
              <div className="flex flex-col gap-6 text-xl">
                <div className="border-l-4 border-neon pl-4">
                  <h4 className="font-black text-neon">Per-folder CLAUDE.md</h4>
                  <p className="text-gray-400">Architecture context in every significant directory</p>
                </div>
                <div className="border-l-4 border-sky-blue pl-4">
                  <h4 className="font-black text-sky-blue">Root CLAUDE.md</h4>
                  <p className="text-gray-400">Project-wide conventions and rules</p>
                </div>
                <div className="border-l-4 border-blue-green pl-4">
                  <h4 className="font-black text-blue-green">AGENTS.md</h4>
                  <p className="text-gray-400">Multi-agent coordination guidance</p>
                </div>
                <div className="border-l-4 border-amber-flame pl-4">
                  <h4 className="font-black text-amber-flame">CODEBASE_MAP.md</h4>
                  <p className="text-gray-400">Full architecture map with module guide</p>
                </div>
                <div className="border-l-4 border-princeton-orange pl-4">
                  <h4 className="font-black text-princeton-orange">.claude/rules/ & .cursor/rules/</h4>
                  <p className="text-gray-400">Claude Code & Cursor IDE rule files</p>
                </div>
                <div className="mt-8 bg-neon text-black font-black p-6 text-center text-3xl uppercase brutalist-border">
                  One analysis. Every format. Always in sync.
                </div>
              </div>
            </div>

            <div className="flex flex-col justify-center">
              <h2 className="text-3xl md:text-5xl font-black text-white mb-10 border-b-4 border-white pb-4 text-right uppercase">
                BY THE NUMBERS
              </h2>
              <div className="flex flex-col gap-6 font-mono text-right">
                <div className="bg-gray-900 border-2 border-gray-700 p-8 flex flex-col justify-center items-end hover:border-amber-flame transition-colors">
                  <span className="text-6xl font-black text-amber-flame mb-2">9-PHASE</span>
                  <span className="text-gray-400 text-xl uppercase">deep AI analysis pipeline</span>
                </div>
                <div className="bg-gray-900 border-2 border-gray-700 p-8 flex flex-col justify-center items-end hover:border-sky-blue transition-colors">
                  <span className="text-6xl font-black text-sky-blue mb-2">5 SLASH</span>
                  <span className="text-gray-400 text-xl uppercase">commands native in Claude Code</span>
                </div>
                <div
                  className="bg-gray-900 border-2 border-gray-700 p-8 flex flex-col justify-center items-end brutalist-border"
                  style={{ borderColor: "#fb8500" }}
                >
                  <span className="text-4xl font-black text-princeton-orange mb-4 uppercase">Incremental Updates</span>
                  <span className="text-gray-300 text-lg">
                    Re-analysis only updates what changed. Per-folder context, auto-validation hooks on every new file.
                  </span>
                </div>
              </div>
            </div>
          </div>

        </div>
      </section>

      {/* Final CTA */}
      <section className="py-32 md:py-40 px-4 bg-deep-space-blue border-y-[8px] border-neon text-center overflow-hidden">
        <div className="max-w-7xl mx-auto fade-up">
          <h2 className="text-4xl md:text-[8rem] leading-none font-black text-white mb-20 md:mb-24 uppercase">
            Analyze once.<br /><span className="text-neon inline-block mt-4 border-b-8 border-neon pb-2">Stay current.</span>
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8 lg:gap-12 mb-24 md:mb-32 text-left font-mono">
            <div className="bg-black p-8 border border-gray-800 hover:border-neon transition-colors">
              <div className="text-neon font-black text-3xl mb-4">1. ANALYZE</div>
              <p className="text-gray-400">Point it at your repo. A pipeline produces a structured architectural blueprint.</p>
            </div>
            <div className="bg-black p-8 border border-gray-800 hover:border-sky-blue transition-colors">
              <div className="text-sky-blue font-black text-3xl mb-4">2. SYNC</div>
              <p className="text-gray-400">
                Run <code className="text-white bg-gray-900 px-2 py-1">/sync-architecture</code>. Context provisioned with smart merging.
              </p>
            </div>
            <div className="bg-black p-8 border border-gray-800 hover:border-amber-flame transition-colors">
              <div className="text-amber-flame font-black text-3xl mb-4">3. WORK</div>
              <p className="text-gray-400">Claude Code is now deeply architecturally aware.</p>
            </div>
            <div className="bg-black p-8 border border-gray-800 hover:border-princeton-orange transition-colors">
              <div className="text-princeton-orange font-black text-3xl mb-4">4. EVOLVE</div>
              <p className="text-gray-400">Incremental re-analysis updates context as your code changes.</p>
            </div>
          </div>
          <div className="bg-black p-16 border-4 border-neon max-w-4xl mx-auto transform -rotate-1 hover:rotate-1 transition-transform brutalist-border">
            <h3 className="text-4xl font-black mb-6 uppercase text-white">The architecture your AI reads before it writes.</h3>
            <p className="text-2xl text-gray-400 mb-12 leading-relaxed">
              Rulegen scans your package.json. ContextPilot syncs your rules. We analyze your architecture and keep it current as your
              code evolves.
            </p>
            <a
              href="https://github.com/BitRaptors/Archie"
              onMouseEnter={() => setIsCtaHovered(true)}
              onMouseLeave={() => setIsCtaHovered(false)}
              className="inline-flex items-center gap-4 px-8 py-4 md:px-16 md:py-8 bg-neon text-black font-black text-xl md:text-3xl uppercase tracking-widest hover:bg-white transition-colors brutalist-border"
              style={{ borderColor: "#023047" }}
            >
              <Github size={40} />
              Analyze your first repo {"->"}
            </a>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-black py-16 px-4 border-t-2 border-gray-800 text-center text-gray-500 font-mono text-sm">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between items-center gap-6">
          <a href="https://bitraptors.com/" target="_blank" rel="noopener noreferrer" className="text-lg hover:text-neon transition-colors">Made with ❤️ by BitRaptors</a>
          <div className="flex gap-8 text-lg underline decoration-gray-800 underline-offset-4">
            <a
              href="https://github.com/BitRaptors/Archie/blob/main/docs/ARCHITECTURE.md"
              className="hover:text-neon hover:decoration-neon transition-colors"
            >
              Documentation
            </a>
            <a
              href="https://github.com/BitRaptors/Archie"
              className="hover:text-neon hover:decoration-neon transition-colors"
            >
              GitHub
            </a>
            <a href="#" className="hover:text-neon hover:decoration-neon transition-colors">
              Privacy
            </a>
          </div>
        </div>
      </footer>

      {/* Full Screen Showcase Modal */}
      <AnimatePresence>
        {isModalOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center p-4 md:p-12 bg-black/95 backdrop-blur-xl"
          >
            <motion.div
              initial={{ scale: 0.9, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.9, y: 20 }}
              className="w-full h-full max-w-7xl bg-[#0a0a0a] border-4 border-white/10 flex flex-col relative overflow-hidden shadow-[0_0_100px_rgba(33,158,188,0.2)]"
            >
              {/* Modal Header */}
              <div className="bg-gray-900 border-b-2 border-white/5 px-6 py-4 flex items-center justify-between shrink-0">
                <div className="text-white font-black uppercase tracking-[0.2em] text-sm md:text-base">
                  Archie <span className="text-gray-500 font-mono text-xs ml-2 opacity-50">Generated Output</span>
                </div>
                <button
                  onClick={() => setIsModalOpen(false)}
                  className="bg-white/5 hover:bg-neon hover:text-black p-2 transition-all group brutalist-border-sm"
                >
                  <X className="w-8 h-8 group-hover:rotate-90 transition-transform duration-300" />
                </button>
              </div>

              <div className="flex-1 flex flex-col md:flex-row overflow-hidden">
                {/* Modal Sidebar — File Tree */}
                <div className="w-full md:w-80 bg-black/50 border-r-2 border-white/5 flex flex-col shrink-0">
                  <div className="px-4 py-3 border-b border-white/5 flex items-center gap-3">
                    <Search className="w-3.5 h-3.5 text-gray-500" />
                    <span className="text-gray-500 font-mono text-[10px] uppercase tracking-widest">Explorer — {EXAMPLE_FILE_PATHS.length} files</span>
                  </div>
                  <div className="flex-1 overflow-y-auto custom-scrollbar" data-lenis-prevent>
                    <FileTree
                      filePaths={EXAMPLE_FILE_PATHS}
                      activePath={activeFile}
                      onSelect={setActiveFile}
                    />
                  </div>
                  <div className="hidden md:block p-4 border-t-2 border-white/5">
                    <div className="text-[10px] text-gray-600 uppercase tracking-widest leading-relaxed">
                      All files are dynamically generated based on codebase intent analysis and structural mapping.
                    </div>
                  </div>
                </div>

                {/* Modal Content area */}
                <div className="flex-1 p-8 md:p-12 font-mono text-sm md:text-base overflow-y-auto custom-scrollbar bg-[radial-gradient(circle_at_top_right,rgba(33,158,188,0.05),transparent_50%)]" data-lenis-prevent>
                  <div className="max-w-4xl mx-auto pb-20">
                    <ExampleFileContent filePath={activeFile} />
                  </div>
                </div>
              </div>

            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </main>
  );
}
