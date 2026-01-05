---
id: frontend-pattern-cva-components
title: Component with CVA Variants
category: frontend
tags: [pattern, cva, components, styling]
related: [frontend-patterns-overview]
---

# Pattern 6: Component with CVA Variants

Using shadcn/ui patterns with analytics integration.

```typescript
// components/atoms/button.tsx
import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/utils/cn'
import mixpanel from 'mixpanel-browser'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-1.5 whitespace-nowrap text-center font-sans font-bold transition-all duration-200',
  {
    variants: {
      variant: {
        primary: cn(
          'bg-background-1 text-text-color',
          'hover:bg-container-light-1-hover',
          'active:bg-background-2',
        ),
        secondary: cn(
          'border-2 border-border-color-inv text-text-color-inv',
          'hover:border-background-2',
        ),
        tertiary: cn(
          'text-text-color bg-container-light-2',
          'hover:bg-container-light-1-hover',
        ),
        ghost: 'hover:bg-accent hover:text-accent-foreground',
        destructive: 'text-text-error hover:bg-container-light-1-hover',
      },
      size: {
        xs: 'rounded-lg p-1 text-button-3',
        sm: 'rounded-lg px-2 py-3 text-button-2',
        md: 'rounded-2xl p-3 text-button-1',
        lg: 'rounded-2xl p-4 text-button-1',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
  eventData?: {
    eventId: string
  } & Record<string, unknown>
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, onClick, eventData, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'

    const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
      if (eventData) {
        const { eventId, ...data } = eventData
        mixpanel.track(eventId, data)
      }
      onClick?.(e)
    }

    return (
      <Comp
        className={cn(
          'outline-none disabled:pointer-events-none disabled:opacity-30',
          buttonVariants({ variant, size }),
          className,
        )}
        ref={ref}
        onClick={handleClick}
        {...props}
      />
    )
  },
)
Button.displayName = 'Button'

export { Button, buttonVariants }
```


