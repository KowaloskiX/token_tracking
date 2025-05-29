"use client"
import { SOLUTIONS } from "@/app/constants/solutions"
import ContactCtaSection from "@/components/landing/ContactCtaSection"
import Footer from "@/components/landing/Footer"
import Navbar from "@/components/landing/Navbar"
import BusinessTestimonials from "@/components/landing/solutions/BusinessTestimonials"
import SolutionFeature from "@/components/landing/solutions/SolutionFeature"
import SolutionHero from "@/components/landing/solutions/SolutionHero"
import SolutionStats from "@/components/landing/solutions/SolutionStats"
import { useParams } from "next/navigation"
import { notFound } from "next/navigation"

const Solution = () => {
    const params = useParams();
    const solutionName = params.solutionName as string;
    
    // Check if the solution exists
    if (!SOLUTIONS[solutionName]) {
        notFound();
    }

    const solutionContent = SOLUTIONS[solutionName];

    // Helper function to check if features array has valid content
    const hasValidFeatures = (features: any[]) => {
        return features && features.length > 0 && features.some(feature => 
            feature.subtitle && feature.title && feature.description
        );
    }

    // Helper function to check if stats have valid content
    const hasValidStats = (stats: any) => {
        return stats && 
               stats.title && 
               stats.description && 
               stats.stats && 
               stats.stats.length > 0;
    }

    // Helper function to check if hero has valid content
    const hasValidHero = (hero: any) => {
        return hero && 
               hero.title && 
               hero.description;
    }

    return (
        <div>
            <Navbar />
            {/* Only render hero if content exists */}
            {hasValidHero(solutionContent.hero) && (
                <SolutionHero {...solutionContent.hero} />
            )}

            {/* Only render stats if content exists */}
            {hasValidStats(solutionContent.stats) && (
                <SolutionStats {...solutionContent.stats} />
            )}

            {/* Only render features if array has valid content */}
            {hasValidFeatures(solutionContent.features) && 
                solutionContent.features.map((featureContent, index) => (
                    <SolutionFeature 
                        key={featureContent.subtitle || index}
                        {...featureContent} 
                        imagePosition={index % 2 === 0 ? 'right' : 'left'}
                    />
                ))
            }

            <BusinessTestimonials />
            <ContactCtaSection />
            <Footer />
        </div>
    )
}

export default Solution