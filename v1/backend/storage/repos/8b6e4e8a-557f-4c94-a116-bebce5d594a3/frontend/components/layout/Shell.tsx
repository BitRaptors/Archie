
import { cn } from "@/lib/utils"

interface ShellProps extends React.HTMLAttributes<HTMLDivElement> {
    sidebar: React.ReactNode
}

export function Shell({ children, sidebar, className, ...props }: ShellProps) {
    return (
        <div className="flex min-h-screen">
            <aside className="fixed inset-y-0 left-0 z-50 hidden w-64 border-r bg-background lg:block">
                {sidebar}
            </aside>
            <main className={cn("lg:pl-64 w-full min-h-screen bg-gradient-to-br from-papaya-50 via-white to-teal-50/10", className)} {...props}>
                {children}
            </main>
        </div>
    )
}
