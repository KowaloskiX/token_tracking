"use client"

import { useEffect, useState, Suspense } from "react"
import { useSearchParams } from "next/navigation"
import { SOLUTIONS } from "@/app/constants/solutions"
import Footer from "@/components/landing/Footer"
import Navbar from "@/components/landing/Navbar"
import BusinessTestimonials from "@/components/landing/solutions/BusinessTestimonials"
import SolutionFeature from "@/components/landing/solutions/SolutionFeature"
import SolutionStats from "@/components/landing/solutions/SolutionStats"
import ContactFixedButton from "@/components/landing/solutions/tenders/ContactFixedButton"
import PresentationCTA from "@/components/landing/solutions/tenders/PresentationCTA"
import TendersHero from "@/components/landing/solutions/tenders/TendersHero"
import MeetingScheduledPopup from "@/components/landing/solutions/tenders/MeetingScheduledPopup"

// Separate component for the success popup logic
const SuccessPopupHandler = () => {
    const [showPopup, setShowPopup] = useState(false)
    const searchParams = useSearchParams()

    useEffect(() => {
        const isSuccess = searchParams.get('isSuccessBookingPage') === 'true'
        if (isSuccess) {
            setShowPopup(true)
        }
    }, [searchParams])

    if (!showPopup) return null
    return <MeetingScheduledPopup onClose={() => setShowPopup(false)} />
}

// Main page component
const PrzetargiLandingPage = () => {
    const content = SOLUTIONS["przetargi"]

    return (
        <div>
            <Navbar />
            <TendersHero {...content.hero} />
            <ContactFixedButton />
            <SolutionStats {...content.stats} />
            {
                content.features.map((featureContent, index) => (
                    <SolutionFeature 
                        key={featureContent.subtitle || index}
                        {...featureContent}
                        imagePosition={index % 2 === 0 ? 'right' : 'left'}
                    />
                ))
            }
            
            <BusinessTestimonials />
            <PresentationCTA />
            <Footer />

            <Suspense fallback={null}>
                <SuccessPopupHandler />
            </Suspense>
        </div>
    )
}

export default PrzetargiLandingPage;