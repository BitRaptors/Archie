'use client'

import React from 'react'
import { Folder } from 'lucide-react'

interface ProjectTreeProps {
    structure: string
}

export function ProjectTree({ structure }: ProjectTreeProps) {
    // Filter out files (identified by 📄 or lack of folder markers) to strictly show directory hierarchy
    const lines = structure.split('\n').filter(line => {
        const trimmed = line.trim();
        return trimmed && !line.includes('📄');
    });

    return (
        <div className="flex flex-col gap-0.5 py-4">
            {lines.map((line, index) => {
                // Determine indentation depth based on leading tree symbols (e.g., │, ├──, └──)
                const depthMatch = line.match(/^([│\s├└─]+)/)
                const depth = depthMatch ? Math.floor(depthMatch[1].length / 4) : 0

                // Clean structural symbols and emojis to extract the folder name
                const name = line.replace(/[📁📄├──└──│]/g, '').trim()

                return (
                    <div
                        key={index}
                        className="flex items-center gap-2.5 py-1 text-sm text-ink/80 hover:text-ink transition-colors"
                        style={{ paddingLeft: `${depth * 1.5}rem` }}
                    >
                        <Folder className="w-4 h-4 text-ink/20 shrink-0" />
                        <span className="truncate leading-none">{name}</span>
                    </div>
                )
            })}
        </div>
    )
}
