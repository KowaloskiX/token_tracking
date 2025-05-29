// app/page.tsx
"use client"
import React from 'react';
import { Toaster } from "@/components/ui/toaster";
import HeroSection from '@/components/landing/HeroSection';
import UseCases from '@/components/landing/UseCases';
import FeatureGrid from '@/components/landing/FeatureGrid';
import Image from 'next/image';
import CtaSection from '@/components/landing/CtaSection';
import Footer from '@/components/landing/Footer';
import CustomerLogos from '@/components/landing/CustomerLogos';
import FeaturesList from '@/components/landing/FeaturesList';
import BusinessTestimonials from '@/components/landing/solutions/BusinessTestimonials';
import BackgroundContentSection from '@/components/landing/BackgroundContentSection';
import DepartamentsSection from '@/components/landing/DepartamentsSection';
import ContactCtaSection from '@/components/landing/ContactCtaSection';

export default function Landing() {
  const heroContent = {
    title: "Zwiększ produktywność firmy z AI.",
    description: "Zastosuj sztuczną inteligencję w codziennych procesach firmowych i zyskaj przewagę konkurencyjną.",
    primaryButton: {
      text: "Skontaktuj się",
      href: "/kontakt/others"
    }
  };

  return (
    <>
      <div className="min-h-screen flex flex-col bg-background">
        <HeroSection {...heroContent} />
        <Image src="/images/asystent_firmowy_mockup.png" alt="" width={2000} height={1200} className='mx-auto max-w-7xl rounded-3xl shadow-xl -mt-20 w-11/12 sm:w-auto' />
        <CustomerLogos />
        <FeatureGrid />
        <FeaturesList />
        <BackgroundContentSection backgroundSrc="/images/aesthetic_office.png">
        <div className="flex flex-wrap sm:flex-nowrap w-full justify-between gap-8 items-end">
          <div className='w-full'>
          <h2 className="text-base/7 font-medium text-body-text">Architektura Rozwiązania</h2>
          <p className="mt-2 text-pretty text-4xl tracking-tight text-foreground sm:text-5xl lg:text-balance">
            Praktyczne Podejście do AI w Biznesie.
          </p>
          </div>
          <p className="mt-4 text-lg/8 text-body-text">
            W dzisiejszych czasach rozwój firmy nie jest uzależniony od ilości osób. Obecnie każda firma ma możliwość posiadania zespołów Asystentów AI skupionych na różnorodnych zdaniamch.
          </p>
        </div>
        <Image src="/images/BAI-Architektura.png" alt="" width={2000} height={1200} className='mx-auto w-full rounded-3xl mt-8' />
        </BackgroundContentSection>
        <DepartamentsSection />
        <BusinessTestimonials />

        <UseCases />
        <ContactCtaSection />
        <Footer />
      </div>
      <Toaster />
    </>
  );
}