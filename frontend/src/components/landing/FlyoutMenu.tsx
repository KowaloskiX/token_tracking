import { Popover, PopoverButton, PopoverPanel } from '@headlessui/react'
import { BookOpenText, ChevronDownIcon, ChevronRightIcon, CircleHelp, Database, FileText, FolderSearch, Hammer, Info, ListChecks, NotepadText, Presentation } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import Image from 'next/image'
import Link from 'next/link'
import { getRecentPosts } from '@/app/constants/blogs'

const Rozwiązania = [
  { name: 'BAI', href: '/biznes/bai', icon: Database },
  { name: 'Przetargi', href: '/przetargi', icon: FolderSearch },
  { name: 'Raporty', href: '#', icon: NotepadText, comingSoon: true },
  { name: 'Oferty', href: '#', icon: FileText, comingSoon: true },
  { name: 'Dowiedz się więcej...', href: '/biznes' },
]

const Usługi = [
  { name: 'Software Development', href: '/biznes/development', icon: Hammer },
  { name: 'Warsztaty', href: '/biznes/warsztaty', icon: Presentation },
  { name: 'Audyty AI', href: '/biznes/audyty', icon: ListChecks }
]

export default function FlyoutMenu({ isMobile = false }) {
  const [isOpen, setIsOpen] = useState(false)
  const [showSolutions, setShowSolutions] = useState(false)
  const recentPosts = getRecentPosts(2)

  if (isMobile) {
    return (
      <div className="flex flex-col w-full">
        <button
          onClick={() => setShowSolutions(!showSolutions)}
          className="-mx-3 block rounded-lg px-3 py-2 font-medium text-foreground cursor-pointer hover:bg-secondary-hover"
        >
          <div className="flex items-center justify-between">
            <span>Dla Biznesu</span>
            <ChevronRightIcon
              className={`size-5 transition-transform ${showSolutions ? 'rotate-90' : ''}`}
              aria-hidden="true"
            />
          </div>
        </button>
        
        {showSolutions && (
          <div className="mt-4 space-y-6 pl-4">
            <div className="space-y-4">
              <h3 className="text-sm font-medium text-foreground">Rozwiązania</h3>
              <div className="flex flex-col space-y-4">
                {Rozwiązania.map((item) => (
                  <div key={item.name} className="flex items-center">
                    <Link
                      href={item.href}
                      className="flex items-center gap-x-4 text-sm font-medium text-foreground"
                    >
                      {item.icon && <item.icon className="size-5 text-body-text" />}
                      {item.name}
                    </Link>
                    {item.comingSoon && (
                      <Badge variant="secondary" className="text-xs">Coming soon</Badge>
                    )}
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-4">
              <h3 className="text-sm font-medium text-foreground">Usługi</h3>
              <div className="flex flex-col space-y-4">
                {Usługi.map((item) => (
                  <div key={item.name} className="flex items-center">
                    <Link
                      href={item.href}
                      className="flex items-center gap-x-4 text-sm font-medium text-foreground"
                    >
                      <item.icon className="size-5 text-body-text" />
                      {item.name}
                    </Link>
                  </div>
                ))}
              </div>
            </div>

            <div className="space-y-4">
              <h3 className="text-sm font-medium text-foreground">Recent Posts</h3>
              <div className="flex flex-col space-y-6">
                {recentPosts.map((post) => (
                  <article key={post.id} className="flex flex-col gap-y-3">
                    <Image
                      src={post.imageUrl}
                      alt=""
                      width={1200}
                      height={800}
                      className="aspect-[2/1] w-full rounded-lg bg-secondary object-cover"
                    />
                    <div className="flex items-center gap-x-4">
                      <time dateTime={post.datetime} className="text-sm text-body-text">
                        {post.date}
                      </time>
                      <Link
                        href={post.category.href}
                        className="rounded-full bg-secondary px-3 py-1.5 text-xs font-medium text-body-text"
                      >
                        {post.category.title}
                      </Link>
                    </div>
                    <h4 className="text-sm font-medium text-foreground">
                      <Link href={post.href}>{post.title}</Link>
                    </h4>
                    <p className="text-sm text-body-text">{post.description}</p>
                  </article>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <div 
      className="relative"
      onMouseEnter={() => setIsOpen(true)}
      onMouseLeave={() => setIsOpen(false)}
    >
      <Popover className="relative isolate z-50">
        <PopoverButton className="inline-flex py-4 cursor-pointer items-center gap-x-1 text-sm/6 font-medium text-foreground outline-none">
          Dla Biznesu
          <ChevronDownIcon
            className={`size-5 transition-transform ${isOpen ? 'rotate-180' : ''}`}
            aria-hidden="true"
          />
        </PopoverButton>

        {isOpen && (
          <PopoverPanel
            static
            className="absolute left-1/2 rounded-2xl -translate-x-1/2 top-full lg:ml-[10svw] xl:ml-[6svw] 2xl:ml-[3.5svw] w-screen max-w-5xl bg-background shadow border border-secondary-border"
          >
            <div className="mx-auto grid grid-cols-1 gap-x-8 gap-y-10 px-6 py-10 lg:grid-cols-2 lg:px-10">
              <div className="grid grid-cols-2 gap-x-6 sm:gap-x-0">
                <div>
                  <h3 className="text-sm text-body-text">Rozwiązania</h3>
                  <div className="mt-4 flow-root">
                    <div className="-my-2">
                      {Rozwiązania.map((item) => (
                        <div key={item.name} className="flex items-center gap-2 py-2">
                          <Link
                            href={item.href}
                            className="flex gap-x-4 text-sm font-medium text-foreground"
                          >
                            {item.icon && <item.icon className="size-5 text-body-text" />}
                            {item.name}
                          </Link>
                          {item.comingSoon && (
                            <Badge variant="secondary" className="text-xs">Coming soon</Badge>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
                <div>
                  <h3 className="text-sm text-body-text">Usługi</h3>
                  <div className="mt-4 flow-root">
                    <div className="-my-2">
                      {Usługi.map((item) => (
                        <div key={item.name} className="flex items-center gap-2 py-2">
                          <Link
                            href={item.href}
                            className="flex gap-x-4 text-sm font-medium text-foreground"
                          >
                            <item.icon className="size-4 flex-none text-body-text" />
                            {item.name}
                          </Link>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-1 gap-10 sm:gap-8 lg:grid-cols-2">
                <h3 className="sr-only">Recent posts</h3>
                {recentPosts.map((post) => (
                  <article
                    key={post.id}
                    className="relative isolate flex max-w-2xl flex-col gap-x-8 gap-y-6 sm:flex-row sm:items-start lg:flex-col lg:items-stretch"
                  >
                    <div className="relative flex-none">
                      <Image
                        alt=""
                        width={1200}
                        height={800}
                        src={post.imageUrl}
                        className="aspect-[2/1] w-full rounded-lg bg-secondary object-cover sm:aspect-video sm:h-32 lg:h-auto"
                      />
                      <div className="absolute inset-0 rounded-lg ring-1 ring-inset ring-gray-900/10" />
                    </div>
                    <div>
                      <div className="flex items-center gap-x-4">
                        <time dateTime={post.datetime} className="text-sm text-body-text">
                          {post.date}
                        </time>
                        <Link
                          href={post.category.href}
                          className="relative z-10 rounded-full bg-secondary px-3 py-1.5 text-xs text-body-text hover:bg-secondary"
                        >
                          {post.category.title}
                        </Link>
                      </div>
                      <h4 className="mt-2 text-sm font-medium text-foreground">
                        <Link href={post.href}>
                          <span className="absolute inset-0" />
                          {post.title}
                        </Link>
                      </h4>
                      <p className="mt-2 text-sm text-body-text">{post.description}</p>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          </PopoverPanel>
        )}
      </Popover>
    </div>
  )
}