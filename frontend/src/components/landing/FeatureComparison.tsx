'use client'
import { Check, X } from 'lucide-react'
import clsx from 'clsx'
import { sections, tiers } from '@/app/constants'

function isStringFeature(feature: Feature): feature is StringFeature {
    return typeof Object.values(feature.tiers)[0] === 'string';
  }
  
  // The component with proper typing
  export default function FeatureComparison() {
    return (
      <div className="bg-background">
        <div className="mt-24">
          <div className="mx-auto max-w-7xl">
            {/* Mobile comparison (up to lg) */}
            <section aria-labelledby="mobile-comparison-heading" className="lg:hidden">
              <h2 id="mobile-comparison-heading" className="sr-only">
                Feature comparison
              </h2>
  
              <div className="mx-auto max-w-2xl space-y-16">
                {tiers.map((tier) => (
                  <div key={tier.id} className="border-t border-border">
                    <div className={clsx(
                      tier.mostPopular ? 'border-primary' : 'border-transparent',
                      '-mt-px w-72 border-t-2 pt-10 md:w-80',
                    )}>
                      <h3 className={clsx(
                        tier.mostPopular ? 'text-primary' : 'text-foreground',
                        'text-sm/6 font-medium',
                      )}>
                        {tier.name}
                      </h3>
                      <p className="mt-1 text-sm/6 text-body-text">{tier.description}</p>
                    </div>
  
                    <div className="mt-10 space-y-10">
                      {sections.map((section) => (
                        <div key={section.name}>
                          <h4 className="text-sm/6 font-medium text-foreground text-left">{section.name}</h4>
                          <div className="relative mt-6">
                            <div className={clsx(
                              tier.mostPopular ? 'ring-2 ring-primary' : 'ring-1 ring-border',
                              'relative rounded-2xl bg-secondary shadow-sm',
                            )}>
                              <dl className="divide-y divide-border text-sm/6">
                                {section.features.map((feature) => (
                                  <div key={feature.name} className="flex items-center justify-between px-4 py-3">
                                    <dt className="pr-4 text-body-text">{feature.name}</dt>
                                    <dd className="flex items-center justify-end">
                                      {isStringFeature(feature) ? (
                                        <span className={tier.mostPopular ? 'font-medium text-primary' : 'text-foreground'}>
                                          {feature.tiers[tier.name as keyof typeof feature.tiers]}
                                        </span>
                                      ) : (
                                        <>
                                          {feature.tiers[tier.name as keyof typeof feature.tiers] ? (
                                            <Check className="h-5 w-5 text-primary" />
                                          ) : (
                                            <X className="h-5 w-5 text-body-text" />
                                          )}
                                        </>
                                      )}
                                    </dd>
                                  </div>
                                ))}
                              </dl>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </section>
  
            {/* Desktop comparison (lg+) */}
            <section aria-labelledby="comparison-heading" className="hidden lg:block">
              <h2 id="comparison-heading" className="sr-only">
                Feature comparison
              </h2>
  
              {/* Plan headers */}
              <div className="grid grid-cols-4 gap-x-8 border-t border-border">
                <div className="pt-10"> {/* Empty cell for alignment */}</div>
                {tiers.map((tier) => (
                  <div key={tier.id} className="-mt-px">
                    <div className={clsx(
                      tier.mostPopular ? 'border-primary' : 'border-transparent',
                      'border-t-2 pt-10',
                    )}>
                      <p className={clsx(
                        tier.mostPopular ? 'text-primary' : 'text-foreground',
                        'text-sm/6 font-medium',
                      )}>
                        {tier.name}
                      </p>
                      <p className="mt-1 text-sm/6 text-body-text">{tier.description}</p>
                    </div>
                  </div>
                ))}
              </div>
  
              {/* Feature sections */}
              <div className="mt-8 space-y-16">
                {sections.map((section) => (
                  <div key={section.name}>
                    <h3 className="text-left text-sm/6 font-medium text-foreground mb-8">{section.name}</h3>
                    <div className="relative">
                      {/* Background cards */}
                      <div className="absolute right-0 inset-y-0 w-3/4 grid grid-cols-3 gap-x-8">
                        {tiers.map((tier) => (
                          <div
                            key={tier.id}
                            className={clsx(
                              tier.mostPopular ? 'ring-2 ring-primary' : 'ring-1 ring-border',
                              'rounded-2xl bg-secondary h-full',
                            )}
                          />
                        ))}
                      </div>
  
                      {/* Features grid */}
                      <div className="relative">
                        <table className="w-full">
                          <tbody>
                            {section.features.map((feature) => (
                              <tr key={feature.name}>
                                <th scope="row" className="w-1/4 py-4 pr-8 text-left text-sm/6 font-normal text-body-text">
                                  {feature.name}
                                </th>
                                {tiers.map((tier) => (
                                  <td key={tier.id} className="w-1/4 px-8 py-4 text-center relative">
                                    {isStringFeature(feature) ? (
                                      <span className={clsx(
                                        tier.mostPopular ? 'font-medium text-primary' : 'text-foreground',
                                        'text-sm/6',
                                      )}>
                                        {feature.tiers[tier.name as keyof typeof feature.tiers]}
                                      </span>
                                    ) : (
                                      <>
                                        {feature.tiers[tier.name as keyof typeof feature.tiers] ? (
                                          <Check className="mx-auto h-5 w-5 text-primary" />
                                        ) : (
                                          <X className="mx-auto h-5 w-5 text-body-text" />
                                        )}
                                      </>
                                    )}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </div>
        </div>
      </div>
    );
  }