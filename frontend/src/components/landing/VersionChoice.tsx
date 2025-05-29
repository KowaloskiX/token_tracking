import Link from "next/link"

export default function VersionChoice() {

  return (
    <div className="flex justify-center w-full">
      <div className="px-6 sm:px-8 lg:max-w-7xl w-full">
        <div className="grid min-h-full grid-cols-1 grid-rows-2 w-full lg:grid-cols-2 lg:grid-rows-1 shadow rounded-xl overflow-hidden">
          <Link href="/waitlist" className="relative flex overflow-hidden ">
            <img
              alt="Desk setup with computer and office accessories"
              src="/images/aesthetic_desk.jpg"
              className="absolute inset-0 size-full object-cover"
            />
            <div className="relative flex w-full flex-col items-start justify-end bg-black/60 sm:bg-black/40 hover:bg-black/60 p-8 sm:p-12 transition-colors">
              <h2 className="text-lg text-white/75">Nowa wersja</h2>
              <p className="mt-1 text-2xl font-medium text-secondary">Nowy Asystent AI już wkrótce</p>
              <span className="mt-4 font-medium rounded-sm px-4 py-2.5 text-sm text-foreground bg-secondary hover:bg-secondary-hover">
                Dołącz do oczekujących
              </span>
            </div>
          </Link>
          <Link href="/biznes" className="relative flex overflow-hidden">
            <img
              alt="Modern office space"
              src="/images/aesthetic_office.png"
              className="absolute inset-0 size-full object-cover"
            />
            <div className="relative flex w-full flex-col items-start justify-end bg-black/60 sm:bg-black/40 hover:bg-black/60 p-8 sm:p-12 transition-colors">
              <h2 className="text-lg text-white/75">Dla Biznesu</h2>
              <p className="mt-1 text-2xl font-medium text-secondary">Asystent Al dla Twojej Firmy</p>
              <span className="mt-4 rounded-sm font-medium px-4 py-2.5 text-sm text-foreground bg-secondary hover:bg-secondary-hover">
                Dowiedz się więcej
              </span>
            </div>
          </Link>
        </div>
      </div>
    </div>
  )
}