"use client";

import { Dialog, DialogPanel } from '@headlessui/react'
import { Menu, XIcon } from 'lucide-react'
import { useState } from 'react'
import FlyoutMenu from './FlyoutMenu'
import Link from 'next/link'

const navigation = [
  { name: 'Solutions', href: '#', isSolutions: true },
  { name: 'O nas', href: '/o-nas' },
  // { name: 'Oferta', href: '/oferta' },
]

const Navbar = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [showSolutions, setShowSolutions] = useState(false)

  return (
    <header className="fixed backdrop-blur-sm bg-background/50 inset-x-0 top-0 z-50">
      <nav aria-label="Global" className="flex items-center justify-between p-4 sm:px-10">
        <div className="flex lg:flex-1">
          <Link href="/" className="-m-1.5 p-1.5">
            <span className="sr-only">Asystent AI</span>
            <img
              alt=""
              src="/images/asystent_ai_logo_brown_long.png"
              className="h-10 w-auto"
            />
          </Link>
        </div>
        <div className="flex lg:hidden">
          <button
            type="button"
            onClick={() => setMobileMenuOpen(true)}
            className="-m-2.5 inline-flex items-center justify-center rounded-md p-2.5 text-foreground"
          >
            <span className="sr-only">Otwórz menu główne</span>
            <Menu aria-hidden="true" className="size-6" />
          </button>
        </div>
        <div className="hidden lg:flex lg:gap-x-12">
          <FlyoutMenu />
          {navigation.filter(item => !item.isSolutions).map((item) => (
            <Link key={item.name} href={item.href} className="text-sm/6 py-4 cursor-pointer font-medium text-foreground">
              {item.name}
            </Link>
          ))}
        </div>
        <div className="hidden lg:flex lg:flex-1 lg:justify-end">
          <Link href="/dashboard/tenders/chat" className="text-sm/6 shadow-sm hover:shadow-none font-medium cursor-pointer text-foreground px-6 rounded-sm bg-secondary hover:bg-secondary-hover border border-secondary-border py-2">
          Zaloguj się <span aria-hidden="true">&rarr;</span>
          </Link>
        </div>
      </nav>
      <Dialog open={mobileMenuOpen} onClose={setMobileMenuOpen} className="lg:hidden">
        <div className="fixed inset-0 z-50" />
        <DialogPanel className="fixed inset-y-0 right-0 z-50 w-full overflow-y-auto bg-background px-6 py-6 sm:max-w-sm sm:ring-1 sm:ring-foreground/10">
          <div className="flex items-center justify-between">
            <Link href="#" className="-m-1.5 p-1.5">
              <span className="sr-only">Asystent AI</span>
              <img
                alt=""
                src="/images/asystent_ai_logo_brown_long.png"
                className="h-8 w-auto"
              />
            </Link>
            <button
              type="button"
              onClick={() => {
                setMobileMenuOpen(false)
                setShowSolutions(false)
              }}
              className="-m-2.5 rounded-md p-2.5 text-foreground"
            >
              <span className="sr-only">Zamknij menu</span>
              <XIcon aria-hidden="true" className="size-6" />
            </button>
          </div>
          <div className="mt-6 flow-root">
            <div className="-my-6 divide-y divide-foreground/10">
              <div className="space-y-2 py-6">
                <FlyoutMenu isMobile />
                {navigation.filter(item => !item.isSolutions).map((item) => (
                  <Link
                    key={item.name}
                    href={item.href}
                    className="-mx-3 block rounded-lg px-3 py-2 font-medium text-foreground cursor-pointer hover:bg-secondary-hover"
                  >
                    {item.name}
                  </Link>
                ))}
              </div>
              <div className="py-6">
                <Link
                  href="/dashboard/tenders/chat"
                  className="-mx-3 block rounded-lg px-3 py-2.5 font-medium text-foreground hover:bg-secondary-hover"
                >
                  Zaloguj się
                </Link>
              </div>
            </div>
          </div>
        </DialogPanel>
      </Dialog>
    </header>
  )
}

export default Navbar