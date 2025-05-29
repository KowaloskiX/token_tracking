import { useEffect, useState } from "react"

export default function SolutionFeature({ 
  imagePosition = 'right',
  subtitle,
  title,
  description,
  features,
  imageSrc,
  imageAlt = "Product screenshot"
}: any) {
  const [isDesktop, setIsDesktop] = useState(false)

  useEffect(() => {
    const handleResize = () => {
      setIsDesktop(window.innerWidth >= 1024) 
    }

    handleResize()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const ContentSection = () => (
    <div className="px-6 lg:px-0 lg:pr-4 lg:pt-4">
      <div className="mx-auto max-w-2xl lg:mx-0 lg:max-w-lg">
        <h2 className="text-base/7 font-medium text-body-text">{subtitle}</h2>
        <p className="mt-2 text-pretty text-4xl tracking-tight text-foreground sm:text-5xl">
          {title}
        </p>
        <p className="mt-6 text-lg/8 text-body-text">
          {description}
        </p>
        <dl className="mt-10 max-w-xl space-y-8 text-base/7 text-body-text lg:max-w-none">
          {features.map((feature: any) => (
            <div key={feature.name} className="relative pl-9">
              <dt className="inline font-medium text-foreground">
                <feature.icon aria-hidden="true" className="absolute left-1 top-1 size-5 text-foreground" />
                {feature.name}
              </dt>{' '}
              <dd className="inline">{feature.description}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  )

  const ImageSection = () => (
    <div className="sm:px-6 lg:px-0">
      <div className="relative isolate overflow-hidden bg-secondary px-6 pt-8 sm:mx-auto sm:max-w-2xl sm:rounded-3xl sm:pt-16 lg:mx-0 lg:max-w-none"
        style={{
          paddingLeft: imagePosition === 'right' ? '4rem' : '1.5rem',
          paddingRight: imagePosition === 'left' ? '4rem' : '1.5rem'
        }}>
        <div
          aria-hidden="true"
          className={`absolute -inset-y-px ${imagePosition === 'right' ? '-left-3' : '-right-3'} -z-10 w-full origin-bottom-left skew-x-[-30deg] bg-background opacity-20 ring-1 ring-inset ring-secondary-hover`}
          style={{
            transform: `skewX(${imagePosition === 'right' ? '-30deg' : '30deg'})`,
            transformOrigin: imagePosition === 'right' ? 'bottom left' : 'bottom right'
          }}
        />
        <div className="mx-auto max-w-2xl sm:mx-0 sm:max-w-none relative h-96">
          <img
            alt={imageAlt}
            src={imageSrc}
            className={`absolute inset-0 w-full h-full object-cover object-center ${
              imagePosition === 'right' ? 'rounded-tl-xl' : 'rounded-tr-xl'
            } bg-secondary-hover ring-1 ring-secondary-hover`}
          />
        </div>
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 ring-2 ring-inset ring-secondary-border sm:rounded-3xl"
        />
      </div>
    </div>
  )

  return (
    <div className="overflow-hidden py-24 sm:py-32">
      <div className="mx-auto max-w-7xl md:px-6 lg:px-8">
        <div className="grid grid-cols-1 gap-x-28 gap-y-16 sm:gap-y-20 lg:grid-cols-2 lg:items-start">
          {isDesktop && imagePosition === 'left' ? (
            <>
              <ImageSection />
              <ContentSection />
            </>
          ) : (
            <>
              <ContentSection />
              <ImageSection />
            </>
          )}
        </div>
      </div>
    </div>
  )
}