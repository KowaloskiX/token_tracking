import { JSX, SVGProps } from "react"
import Image from "next/image"
import Link from "next/link"

const navigation = {
    main: [
      { name: 'O nas', href: '/o-nas' },
      { name: 'Dla Biznesu', href: '/biznes' },
      { name: 'Kontakt', href: '/kontakt/product-question' },
      { name: 'Prywatność', href: '/documents/Polityka_Prywatności.pdf' }
    ],
    social: [
      // {
      //   name: 'Facebook',
      //   href: '#',
      //   icon: (props: JSX.IntrinsicAttributes & SVGProps<SVGSVGElement>) => (
      //     <svg fill="currentColor" viewBox="0 0 24 24" {...props}>
      //       <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-facebook"><path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/></svg>
      //     </svg>
      //   ),
      // },
      {
        name: 'Instagram',
        href: '#',
        icon: (props: JSX.IntrinsicAttributes & SVGProps<SVGSVGElement>) => (
          <svg xmlns="https://www.instagram.com/asystent_ai/" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-instagram"><rect width="20" height="20" x="2" y="2" rx="5" ry="5"/><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/><line x1="17.5" x2="17.51" y1="6.5" y2="6.5"/></svg>
        ),
      },
      // {
      //   name: 'X',
      //   href: '#',
      //   icon: (props: JSX.IntrinsicAttributes & SVGProps<SVGSVGElement>) => (
      //     <svg fill="currentColor" viewBox="0 0 24 24" {...props}>
      //       <path d="M13.6823 10.6218L20.2391 3H18.6854L12.9921 9.61788L8.44486 3H3.2002L10.0765 13.0074L3.2002 21H4.75404L10.7663 14.0113L15.5685 21H20.8131L13.6819 10.6218H13.6823ZM11.5541 13.0956L10.8574 12.0991L5.31391 4.16971H7.70053L12.1742 10.5689L12.8709 11.5655L18.6861 19.8835H16.2995L11.5541 13.096V13.0956Z" />
      //     </svg>
      //   ),
      // },
      {
        name: 'LinkedIn',
        href: '#',
        icon: (props: JSX.IntrinsicAttributes & SVGProps<SVGSVGElement>) => (
          <svg xmlns="https://www.linkedin.com/company/asystentai" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.25" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-linkedin"><path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z"/><rect width="4" height="12" x="2" y="9"/><circle cx="4" cy="4" r="2"/></svg>  
        )
      }
      // {
      //   name: 'GitHub',
      //   href: '#',
      //   icon: (props: JSX.IntrinsicAttributes & SVGProps<SVGSVGElement>) => (
      //     <svg fill="currentColor" viewBox="0 0 24 24" {...props}>
      //       <path
      //         fillRule="evenodd"
      //         d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
      //         clipRule="evenodd"
      //       />
      //     </svg>
      //   ),
      // },
      // {
      //   name: 'YouTube',
      //   href: '#',
      //   icon: (props: JSX.IntrinsicAttributes & SVGProps<SVGSVGElement>) => (
      //     <svg fill="currentColor" viewBox="0 0 24 24" {...props}>
      //       <path
      //         fillRule="evenodd"
      //         d="M19.812 5.418c.861.23 1.538.907 1.768 1.768C21.998 8.746 22 12 22 12s0 3.255-.418 4.814a2.504 2.504 0 0 1-1.768 1.768c-1.56.419-7.814.419-7.814.419s-6.255 0-7.814-.419a2.505 2.505 0 0 1-1.768-1.768C2 15.255 2 12 2 12s0-3.255.417-4.814a2.507 2.507 0 0 1 1.768-1.768C5.744 5 11.998 5 11.998 5s6.255 0 7.814.418ZM15.194 12 10 15V9l5.194 3Z"
      //         clipRule="evenodd"
      //       />
      //     </svg>
      //   ),
      // },
    ],
  }
  
  export default function Footer() {
    return (
      <footer>
        <div className="mx-auto max-w-7xl overflow-hidden px-6 py-20 sm:py-24 lg:px-8">
            <Image 
                src="/images/asystent_ai_logo_brown_long.png"
                width={400}
                height={400}
                alt="Asystent AI Logo"
                className="mx-auto w-auto h-12 mb-12 opacity-20"
            />
          <nav aria-label="Footer" className="-mb-6 flex flex-wrap justify-center gap-x-6 sm:gap-x-12 gap-y-3 text-sm/6">
            {navigation.main.map((item) => (
              <Link key={item.name} href={item.href} className="text-body-text hover:text-foreground">
                {item.name}
              </Link>
            ))}
          </nav>
          <div className="mt-16 flex justify-center gap-x-10">
            {navigation.social.map((item) => (
              <Link key={item.name} href={item.href} className="text-body-text hover:text-foreground">
                <span className="sr-only">{item.name}</span>
                <item.icon aria-hidden="true" className="size-6" />
              </Link>
            ))}
          </div>
          <p className="mt-10 text-center text-sm/6 text-neutral-400">&copy; 2025 Yepp sp. z o.o. All rights reserved.</p>
        </div>
      </footer>
    )
  }
  