import { getRecentPosts } from '@/app/constants/blogs'
import Image from 'next/image'
import Link from 'next/link'

export default function Blogs() {
  const posts = getRecentPosts(3) // Get 3 most recent posts for the landing page

  return (
    <div className="py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-balance text-4xl tracking-tight text-foreground sm:text-5xl">
            Asystent AI w akcji
          </h2>
          <p className="mt-2 text-lg/8 text-body-text">
            Stale rozwijamy nasze rozwiązania tak, aby zwiększały Twoją produktywność.
          </p>
        </div>
        <div className="mx-auto mt-16 grid max-w-2xl grid-cols-1 gap-x-8 gap-y-20 lg:mx-0 lg:max-w-none lg:grid-cols-3">
          {posts.map((post) => (
            <article key={post.id} className="flex flex-col items-start">
              <div className="relative w-full">
                <Image
                  src={post.imageUrl}
                  alt=""
                  width={2400}
                  height={1600}
                  className="aspect-video w-full rounded-lg border-secondary-border border-2 bg-secondary object-cover sm:aspect-[2/1] lg:aspect-[3/2]"
                />
                <div className="absolute inset-0 rounded-lg border-secondary-border border-2 ring-1 ring-inset ring-foreground/10" />
              </div>
              <div className="max-w-xl">
                <div className="mt-8 flex items-center gap-x-4 text-xs">
                  <time dateTime={post.datetime} className="text-body-text">
                    {post.date}
                  </time>
                  <Link
                    href={post.category.href}
                    className="relative z-10 rounded-full bg-secondary px-3 py-1.5 font-medium text-foreground hover:bg-secondary-hover"
                  >
                    {post.category.title}
                  </Link>
                </div>
                <div className="group relative">
                  <h3 className="mt-3 text-lg/6 font-medium text-foreground group-hover:text-body-text">
                    <Link href={`/blog/${post.id}`}>
                      <span className="absolute inset-0" />
                      {post.title}
                    </Link>
                  </h3>
                  <p className="mt-5 line-clamp-3 text-sm/6 text-body-text">
                    {post.description}
                  </p>
                </div>
              </div>
            </article>
          ))}
        </div>
      </div>
    </div>
  )
}