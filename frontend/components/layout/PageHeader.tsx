import React from 'react'
import { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

interface PageHeaderProps {
    title: string
    subtitle?: string | React.ReactNode
    icon?: LucideIcon
    actions?: React.ReactNode
    className?: string
}

export function PageHeader({ title, subtitle, icon: Icon, actions, className }: PageHeaderProps) {
    return (
        <div className={cn(
            "border-b bg-white/50 px-8 py-6 flex items-center justify-between backdrop-blur-sm sticky top-0 z-20 shrink-0",
            className
        )}>
            <div className="flex items-center gap-5">
                {Icon && (
                    <div className="p-3 rounded-2xl bg-white border border-papaya-400 shadow-sm shrink-0">
                        <Icon className="w-6 h-6 text-ink-300" />
                    </div>
                )}
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-ink">
                        {title}
                    </h1>
                    {subtitle && (
                        <div className="text-xs text-ink-300 font-bold uppercase tracking-widest mt-0.5">
                            {subtitle}
                        </div>
                    )}
                </div>
            </div>

            {actions && (
                <div className="flex items-center gap-3">
                    {actions}
                </div>
            )}
        </div>
    )
}
