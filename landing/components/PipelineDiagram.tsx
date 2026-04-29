"use client"

import { motion } from "framer-motion"
import { ArrowDown, Boxes, Cpu, Layers, Network, Sparkles } from "lucide-react"

const WAVE_1_AGENTS = [
  { name: "Structure", desc: "components, layers, placement", icon: Layers },
  { name: "Patterns", desc: "communication, design patterns", icon: Network },
  { name: "Technology", desc: "stack, deployment, dev rules", icon: Cpu },
  { name: "UI Layer", desc: "state, routing (if frontend)", icon: Boxes },
]

function PhaseCard({
  step,
  title,
  desc,
  accent = "sky-blue",
}: {
  step: string
  title: string
  desc: string
  accent?: "sky-blue" | "neon"
}) {
  const border = accent === "neon" ? "border-neon" : "border-sky-blue"
  const text = accent === "neon" ? "text-neon" : "text-sky-blue"
  return (
    <div className={`border-2 ${border} bg-deep-space-blue-100 p-5`}>
      <div className={`font-mono text-xs uppercase tracking-widest ${text} mb-2`}>{step}</div>
      <div className="font-black text-white text-lg uppercase tracking-tight mb-1">{title}</div>
      <div className="font-mono text-xs text-gray-300">{desc}</div>
    </div>
  )
}

export function PipelineDiagram() {
  return (
    <div className="flex flex-col gap-3">
      <PhaseCard step="STEP 1" title="Deterministic scan" desc="file tree, frameworks, layer detection" />

      <ArrowDown className="w-4 h-4 text-sky-blue mx-auto" aria-hidden="true" />

      {/* Wave 1: parallel agents */}
      <div className="border-2 border-sky-blue bg-deep-space-blue-100 p-5">
        <div className="font-mono text-xs uppercase tracking-widest text-sky-blue mb-2">
          Step 2 — Wave 1
        </div>
        <div className="font-black text-white text-lg uppercase tracking-tight mb-3">
          Parallel Sonnet agents
        </div>
        <motion.div
          className="grid grid-cols-2 gap-2"
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, margin: "-10%" }}
          variants={{
            hidden: {},
            visible: { transition: { staggerChildren: 0.1 } },
          }}
        >
          {WAVE_1_AGENTS.map(({ name, desc, icon: Icon }) => (
            <motion.div
              key={name}
              variants={{
                hidden: { opacity: 0, y: 10 },
                visible: { opacity: 1, y: 0 },
              }}
              className="flex items-start gap-2 border border-sky-blue/40 bg-black/40 p-2.5"
            >
              <Icon className="w-4 h-4 text-sky-blue mt-0.5 flex-shrink-0" />
              <div>
                <div className="font-black text-white text-xs uppercase">{name}</div>
                <div className="font-mono text-[10px] text-gray-400 leading-snug">{desc}</div>
              </div>
            </motion.div>
          ))}
        </motion.div>
      </div>

      <ArrowDown className="w-4 h-4 text-sky-blue mx-auto" aria-hidden="true" />

      <PhaseCard
        step="STEP 3 — Wave 2"
        title="Opus reasoning"
        desc="decision chains, trade-offs, pitfalls with causal links"
        accent="neon"
      />

      <ArrowDown className="w-4 h-4 text-neon mx-auto" aria-hidden="true" />

      <div className="border-2 border-neon bg-deep-space-blue-100 p-5">
        <div className="flex items-start gap-3">
          <Sparkles className="w-5 h-5 text-neon flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <div className="font-mono text-xs uppercase tracking-widest text-neon mb-2">STEP 4</div>
            <div className="font-black text-white text-lg uppercase tracking-tight mb-1">
              Intent layer
            </div>
            <div className="font-mono text-xs text-gray-300">
              per-folder CLAUDE.md generated via bottom-up DAG
            </div>
          </div>
        </div>
      </div>

      <div className="text-center mt-4">
        <span className="text-gray-400 font-mono text-[10px] uppercase tracking-[0.3em]">
          One-time, ~15 min
        </span>
      </div>
    </div>
  )
}
