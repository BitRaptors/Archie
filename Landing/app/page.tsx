"use strict";
"use client";

import { useEffect, useRef } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { Github, ArrowRight } from "lucide-react";
import { ShaderBackground } from "@/components/ShaderBackground";
import { motion, useScroll, useSpring } from "framer-motion";

gsap.registerPlugin(ScrollTrigger);

export default function LandingPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll();
  const scaleProgress = useSpring(scrollYProgress, { stiffness: 100, damping: 30 });

  useEffect(() => {
    // GSAP Scroll Animations
    const ctx = gsap.context(() => {
      // 1. Horizontal scroll for big headings
      gsap.utils.toArray(".scrub-heading").forEach((heading: any) => {
        gsap.to(heading, {
          x: () => -(heading.scrollWidth - window.innerWidth) / 2,
          rotation: -5,
          ease: "none",
          scrollTrigger: {
            trigger: heading,
            start: "top bottom",
            end: "bottom top",
            scrub: 1,
          },
        });
      });

      // 2. Parallax Images
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

      // 3. Fade Up
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

        <div className="z-10 text-center max-w-7xl mx-auto mt-20">
          <h1 className="text-5xl md:text-8xl lg:text-9xl font-black mb-12 uppercase tracking-tighter mix-blend-difference text-neon scrub-heading inline-block">
            Your AI is only<br />as good as its context.
          </h1>
          <p className="text-xl md:text-2xl text-sky-blue-600 mb-12 max-w-3xl mx-auto border-l-4 border-neon pl-6 text-left bg-black bg-opacity-40 p-6 backdrop-blur-sm">
            Architecture Blueprints deeply analyzes your codebase — then integrates directly into Claude Code with
            slash commands, auto-validation hooks, and per-folder context that makes every session smarter than the last.
          </p>
          <a
            href="https://github.com/gbrbks/architecture_mcp"
            className="brutalist-border inline-flex items-center gap-4 px-12 py-6 bg-deep-space-blue text-neon font-bold text-xl uppercase tracking-wider hover:bg-neon hover:text-deep-space-blue transition-colors"
          >
            <Github className="w-8 h-8" />
            Analyze your first repo {"->"}
          </a>
        </div>
      </header>

      {/* Problem Section */}
      <section className="py-24 px-4 bg-deep-space-blue-100 relative pt-32 pb-32 border-y-4 border-amber-flame">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row gap-16">
          <div className="md:w-1/2 fade-up">
            <h2 className="text-5xl font-black text-amber-flame uppercase mb-8 border-b-4 border-amber-flame pb-4">
              AI agents are architecturally blind
            </h2>
            <p className="text-xl mb-6 text-gray-300">
              Every session, your AI skims a few files and guesses. It doesn't know your naming conventions, your layer
              boundaries, or where things go.
            </p>
            <p className="text-xl mb-6 text-gray-300">
              After 50 AI-assisted PRs, you have 50 different interpretations of your architecture.
            </p>
            <p className="text-xl font-bold text-neon bg-black p-4 inline-block brutalist-border mt-4">
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
              <div className="text-3xl mt-8 text-white font-black uppercase">
                65% of developers say missing context is the top cause of bad AI-generated code.
              </div>
              <div className="text-princeton-orange mt-4 text-xl">— Not hallucinations. Not model capability. Context.</div>
            </div>
          </div>
        </div>
      </section>

      {/* Solution Section */}
      <section className="py-32 px-4 bg-deep-space-blue relative overflow-hidden">
        <div
          className="absolute right-[-10vw] top-1/4 opacity-5 text-neon select-none pointer-events-none scrub-heading rotate-90"
          aria-hidden="true"
        >
          SOLUTION
        </div>
        <div className="max-w-7xl mx-auto relative z-10">
          <h2 className="text-6xl font-black text-neon mb-16 uppercase fade-up">
            Deep analysis,<br />not surface scanning.
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 text-lg">
            <div className="bg-black p-8 brutalist-border fade-up">
              <h3 className="text-2xl font-black text-sky-blue mb-4 uppercase">9-Phase Pipeline</h3>
              <p className="text-gray-400">
                Other tools scan your package.json and call it a day. Architecture Blueprints runs a deep AI analysis
                pipeline — observation, discovery, implementation analysis, and synthesis.
              </p>
            </div>
            <div
              className="bg-black p-8 brutalist-border fade-up transition-transform duration-200 lg:mt-12"
              style={{
                borderColor: "#219ebc",
                boxShadow: "8px 8px 0px 0px #219ebc",
              }}
            >
              <h3 className="text-2xl font-black text-blue-green mb-4 uppercase">Source of Truth</h3>
              <p className="text-gray-400">
                The structured architectural blueprint becomes the truth for every AI tool in your workflow. No more
                scattered instructions or conflicting configurations.
              </p>
            </div>
            <div
              className="bg-black p-8 brutalist-border fade-up transition-transform duration-200 lg:mt-24"
              style={{
                borderColor: "#ffb703",
                boxShadow: "8px 8px 0px 0px #ffb703",
              }}
            >
              <h3 className="text-2xl font-black text-amber-flame mb-4 uppercase">Incremental Updates</h3>
              <p className="text-gray-400">
                As your code evolves, the blueprint evolves with it — incremental re-analysis keeps context current without
                re-analyzing the entire codebase.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Native inside Claude Code */}
      <section className="py-32 px-4 bg-deep-space-blue-100 border-t-8 border-neon relative overflow-hidden">
        <div className="max-w-7xl mx-auto fade-up relative z-10">
          <h2 className="text-5xl font-black text-white mb-16 underline decoration-neon decoration-4 underline-offset-8 uppercase">
            Native inside Claude Code
          </h2>
          <div className="space-y-16">
            <div className="brutalist-border bg-black p-8 relative">
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
              className="brutalist-border bg-black p-8 relative ml-4 md:ml-12"
              style={{
                borderColor: "#219ebc",
                boxShadow: "8px 8px 0px 0px #219ebc",
              }}
            >
              <div className="absolute -top-4 -right-4 bg-blue-green text-black font-black px-4 py-2 text-xl border-2 border-black">
                /check-naming
              </div>
              <div className="text-sky-blue mb-6 text-2xl font-bold">"Is PaymentService a good class name?"</div>
              <pre className="text-lg text-green-400 font-mono bg-gray-900 p-6 border border-gray-700 overflow-x-auto">
                <code>
                  Convention: PascalCase, no suffix for services{"\n"}
                  Verdict: <span className="text-neon bg-black px-2">PASS</span>
                </code>
              </pre>
            </div>

            <div
              className="brutalist-border bg-black p-8 relative ml-8 md:ml-24"
              style={{
                borderColor: "#fb8500",
                boxShadow: "8px 8px 0px 0px #fb8500",
              }}
            >
              <div className="absolute -top-4 -right-4 bg-princeton-orange text-black font-black px-4 py-2 text-xl border-2 border-black">
                /how-to-implement
              </div>
              <div className="text-sky-blue mb-6 text-2xl font-bold">"How was email verification built?"</div>
              <pre className="text-lg text-green-400 font-mono bg-gray-900 p-6 border border-gray-700 overflow-x-auto">
                <code>
                  Libraries: firebase-functions, Gmail API{"\n"}
                  Key files: gmail_webhook/main.py, worker/email_handler.py{"\n"}
                  Tips: Use existing GmailWebhookParser, don't roll your own
                </code>
              </pre>
            </div>

            <div className="flex flex-col md:flex-row gap-8 mt-16">
              <div
                className="bg-[#111] border-2 border-amber-flame p-8 flex-1 brutalist-border"
                style={{
                  borderColor: "#ffb703",
                  boxShadow: "8px 8px 0px 0px #ffb703",
                }}
              >
                <span className="text-amber-flame font-black text-2xl mb-4 block inline-block bg-black px-2">
                  /check-architecture
                </span>
                <p className="text-xl text-gray-300">Validate all uncommitted changes against the blueprint in seconds.</p>
              </div>
              <div
                className="bg-[#111] border-2 border-sky-blue p-8 flex-1 brutalist-border"
                style={{
                  borderColor: "#8ecae6",
                  boxShadow: "8px 8px 0px 0px #8ecae6",
                }}
              >
                <span className="text-sky-blue font-black text-2xl mb-4 block inline-block bg-black px-2">/sync-architecture</span>
                <p className="text-xl text-gray-300">Pull the latest blueprint outputs into your project with smart merging.</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Evolution Section */}
      <section className="py-32 px-4 bg-black overflow-hidden relative border-y-2 border-gray-800">
        <div className="absolute inset-0 flex items-center justify-center opacity-[0.02] pointer-events-none">
          <div className="text-[25vw] font-black text-white whitespace-nowrap scrub-heading" style={{ transform: "rotate(15deg)" }}>
            EVOLUTION
          </div>
        </div>
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row gap-16 relative z-10">
          <div className="md:w-1/2 fade-up parallax-img-container">
            <div className="parallax-img justify-start mt-8">
              <div className="bg-gray-900 border-2 border-neon p-8 font-mono text-lg brutalist-border">
                <div className="text-sky-blue mb-4 text-xl">1. You: "add a notifications service"</div>
                <div className="text-gray-400 mb-4 text-xl">
                  2. Claude creates <span className="text-white">worker/notifications/service.py</span>
                </div>
                <div className="text-amber-flame mb-4 bg-black p-4 text-xl border-l-4 border-amber-flame">
                  3. Hook fires: "Service files belong in worker/services/"
                </div>
                <div className="text-neon font-black text-2xl bg-black p-2 border-2 border-neon text-center mt-8 uppercase">
                  4. Claude moves the file automatically
                </div>
              </div>
            </div>
          </div>
          <div className="md:w-1/2 fade-up py-12">
            <div className="text-princeton-orange font-black text-3xl mb-4 inline-block border-b-4 border-princeton-orange">
              02. LIVING ARCHITECTURE
            </div>
            <h2 className="text-6xl font-black text-white mb-8 uppercase leading-tight">Your blueprint evolves with your code</h2>
            <p className="text-2xl text-gray-400 mb-8 font-light">
              Architecture isn't static. You add new modules, refactor layers, introduce new patterns. Incremental re-analysis detects
              what changed and regenerates only the affected per-folder context files.
            </p>
            <div className="bg-deep-space-blue p-8 brutalist-border text-xl text-sky-blue shadow-xl">
              Your CLAUDE.md files stay accurate without manual maintenance. The compound knowledge your AI relies on is always grounded
              in the actual state of your codebase.
            </div>
          </div>
        </div>
      </section>

      {/* Per-Folder Section */}
      <section className="py-32 px-4 bg-deep-space-blue-100 border-b-[16px] border-amber-flame">
        <div className="max-w-6xl mx-auto text-center fade-up">
          <h2 className="text-6xl md:text-8xl text-sky-blue font-black mb-12 scrub-heading whitespace-nowrap">PER-FOLDER CONTEXT</h2>
          <p className="text-3xl font-bold bg-black text-white p-4 inline-block brutalist-border mb-12">
            Your AI lands in any folder and immediately knows the rules.
          </p>
          <p className="text-2xl text-gray-300 mb-20 max-w-4xl mx-auto">
            A single root-level CLAUDE.md doesn't scale. Your frontend has different patterns than your backend. Architecture Blueprints
            generates per-folder files.
          </p>
          <div className="bg-black p-16 brutalist-border mx-auto max-w-4xl transform hover:scale-105 transition-transform">
            <h3 className="text-4xl font-black text-neon mb-8 uppercase">Compound Learning</h3>
            <p className="text-2xl mb-8">Stop teaching your AI the same lessons twice. Every session starts from zero without us.</p>
            <blockquote className="text-xl italic text-gray-400 border-l-4 border-white pl-8 text-left bg-gray-900 p-8 shadow-inner">
              "Well-maintained project knowledge compounds: each documented subsystem accelerates not only its own future modifications but
              every adjacent feature."
              <br />
              <span className="block mt-6 text-sky-blue font-bold text-2xl uppercase not-italic">— Codified Context, arxiv 2026</span>
            </blockquote>
          </div>
        </div>
      </section>

      {/* What Gets Generated & By the Numbers */}
      <section className="py-32 px-4 bg-black relative">
        <div className="max-w-7xl mx-auto z-10 relative fade-up">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-16">
            <div className="text-left">
              <h2 className="text-5xl font-black text-white mb-10 border-b-4 border-white pb-4 uppercase">
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
              <h2 className="text-5xl font-black text-white mb-10 border-b-4 border-white pb-4 text-right uppercase">
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
      <section className="py-32 px-4 bg-deep-space-blue border-y-[8px] border-neon text-center overflow-hidden">
        <div className="max-w-7xl mx-auto fade-up">
          <h2 className="text-6xl md:text-[8rem] leading-none font-black text-white mb-16 uppercase pt-12">
            Analyze once.<br /><span className="text-neon inline-block mt-4 border-b-8 border-neon pb-2">Stay current.</span>
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-24 text-left font-mono">
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
              Rulegen scans your package.json. ContextPilot syncs your rules. We analyze your architecture — and keep it current as your
              code evolves.
            </p>
            <a
              href="https://github.com/gbrbks/architecture_mcp"
              className="inline-flex items-center gap-4 px-16 py-8 bg-neon text-black font-black text-3xl uppercase tracking-widest hover:bg-white transition-colors brutalist-border"
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
          <div className="text-lg">© 2026 Architecture Blueprints. All systems nominal.</div>
          <div className="flex gap-8 text-lg underline decoration-gray-800 underline-offset-4">
            <a
              href="https://github.com/gbrbks/architecture_mcp/blob/main/docs/ARCHITECTURE.md"
              className="hover:text-neon hover:decoration-neon transition-colors"
            >
              Documentation
            </a>
            <a
              href="https://github.com/gbrbks/architecture_mcp"
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
    </main>
  );
}
