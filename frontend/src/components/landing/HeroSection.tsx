'use client'

import Link from "next/link"
import Navbar from "./Navbar"
import { Button } from "../ui/button"

interface HeroSectionProps {
  title: string
  description: string
  primaryButton: {
    text: string
    href: string
  }
  secondaryButton?: {
    text: string
    href: string
  }
}

export default function HeroSection({
  title,
  description,
  primaryButton,
  secondaryButton,
}: HeroSectionProps) {
  return (
    <div>
      <Navbar />
      <div className="relative isolate pt-14">
        <div
          aria-hidden="true"
          className="absolute inset-x-0 -top-40 -z-10 transform-gpu overflow-hidden blur-3xl sm:-top-80"
        >
        </div>
        <div className="py-10 pb-32 sm:py-32 lg:pb-40">
          <div className="mx-auto max-w-7xl px-6 lg:px-8">
            <div className="mx-auto max-w-3xl text-center">
              <h1 className="text-balance text-[2.5rem] tracking-tight leading-tight text-foreground sm:text-7xl">
                {title}
              </h1>
              <p className="mt-8 text-pretty text-lg text-body-text mx-auto w-3/4 sm:text-xl/8">
                {description}
              </p>
              <div className="mt-10 flex flex-wrap gap-y-4 sm:gap-y-0 items-center justify-center gap-x-6">
                <Button asChild className="w-full px-12 py-2.5 sm:w-auto">
                  <Link href={primaryButton.href}>
                    {primaryButton.text}
                  </Link>
                </Button>
                {secondaryButton &&
                  <Link
                    href={secondaryButton.href}
                    className="rounded-md bg-secondary w-full sm:w-auto hover:bg-secondary-hover border border-secondary-border px-12 sm:px-20 py-2.5 text-sm font-medium text-foreground shadow-sm hover:shadow-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
                  >
                    {secondaryButton.text}
                  </Link>
                }
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}