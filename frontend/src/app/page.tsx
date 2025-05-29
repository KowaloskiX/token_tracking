// app/page.tsx
"use client"
import React from 'react';
import { Toaster } from "@/components/ui/toaster";
import HeroSection from '@/components/landing/HeroSection';
import UseCases from '@/components/landing/UseCases';
import FeatureGrid from '@/components/landing/FeatureGrid';
import VersionChoice from '@/components/landing/VersionChoice';
import CtaSection from '@/components/landing/CtaSection';
import Footer from '@/components/landing/Footer';
import DepartmentsSection from '@/components/landing/DepartamentsSection';

export default function Landing() {
  const heroContent = {
    title: "Bądź produktywny\nz Asystentem AI.",
    description: "Twoim niezawodnym partnerem w analizie danych, generowaniu dokumentów oraz automatyzacji procesów.",
    primaryButton: {
      text: "Dołącz do oczekujących",
      href: "/waitlist"
    },
    secondaryButton: {
      text: "Skontaktuj się",
      href: "/kontakt/product-question"
    }
  };

  return (
    <>
      <div className="min-h-screen flex flex-col bg-background">
        <HeroSection {...heroContent} />
        <VersionChoice />
        <FeatureGrid />
        <UseCases />
        <DepartmentsSection />
        <CtaSection />
        <Footer />
      </div>
      <Toaster />
    </>
  );
}