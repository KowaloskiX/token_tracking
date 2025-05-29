export default function SolutionStats({
  title,
  description,
  stats
}: any) {
  return (
    <div className="py-24 sm:py-0 sm:pb-20">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-2xl lg:mx-0">
          <h2 className="text-pretty text-4xl tracking-tight text-foreground sm:text-5xl">
            {title}
          </h2>
          <p className="mt-6 text-base/7 text-body-text">
            {description}
          </p>
        </div>
        <div className="mx-auto mt-16 flex max-w-2xl flex-col gap-8 lg:mx-0 lg:mt-20 lg:max-w-none lg:flex-row lg:items-end">
          {stats.map((stat: any, index: any) => (
            <div key={index} 
                 className={`flex flex-col-reverse justify-between gap-x-16 gap-y-8 rounded-2xl p-8 
                            ${stat.bgColor || 'bg-secondary'}
                            ${stat.widthClass || 'sm:w-3/4 sm:max-w-md'}
                            sm:flex-row-reverse sm:items-end lg:w-72 lg:max-w-none lg:flex-none lg:flex-col lg:items-start`}>
              <p className={`flex-none text-3xl font-medium tracking-tight ${stat.valueColor || 'text-body-text'}`}>
                {stat.value}
              </p>
              <div className="sm:w-80 sm:shrink lg:w-auto lg:flex-none">
                <p className={`text-lg font-medium tracking-tight ${stat.titleColor || 'text-body-text'}`}>
                  {stat.title}
                </p>
                <p className={`mt-2 text-base/7 ${stat.descriptionColor || 'text-body-text'}`}>
                  {stat.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}