// Adapted from shadcn/ui (MIT); see THIRD_PARTY_NOTICES.md.
import type { ComponentProps } from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'
const variants = cva('button inline-flex items-center justify-center gap-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-45 disabled:cursor-not-allowed', {
  variants: {
    variant: { default: 'button-primary', outline: 'button-outline', ghost: 'button-ghost' },
    size: { default: 'h-10 px-4', sm: 'h-8 px-3', icon: 'h-10 w-10' },
  }, defaultVariants: { variant: 'default', size: 'default' },
})
export function Button({ className, variant, size, type = 'button', ...props }: ComponentProps<'button'> & VariantProps<typeof variants>) {
  return <button type={type} className={twMerge(clsx(variants({ variant, size }), className))} {...props} />
}
