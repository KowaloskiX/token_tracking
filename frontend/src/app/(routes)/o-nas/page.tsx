"use client"

import CtaSection from "@/components/landing/CtaSection";
import Footer from "@/components/landing/Footer";
import HeroSection from "@/components/landing/HeroSection";
import Mission from "@/components/landing/Mission";
import Navbar from "@/components/landing/Navbar";
import SolutionHero from "@/components/landing/solutions/SolutionHero";
import Timeline from "@/components/landing/Timeline";

const AboutUs = () => {

    const heroContent = {
        subtitle: "Produkt Polski",
        title: "Polski Zespół z Globalnymi Ambicjami.",
        description: "Naszą misją jest pokazanie światu, że Polska i Europa również potrafi w technologię.",
        imageSrc: "/images/buro.png",
        primaryButton: {
          text: "Skontaktuj się",
          href: "/kontakt/others"
        }
      };

      
    return (
        <div className="min-h-screen flex flex-col bg-background">
        <Navbar />
        <SolutionHero {...heroContent} />
        <Mission />
        <Timeline />
        <CtaSection />
        <Footer />
        </div>
    )
}

export default AboutUs;