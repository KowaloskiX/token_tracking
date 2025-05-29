import React, { useState } from 'react';
import { Phone } from 'lucide-react';
import Link from 'next/link';

export default function FloatingCTA() {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <Link 
      href="https://cal.com/asystent-ai/prezentacja-automatyzacji-przetargow"
      className="fixed bottom-8 right-8 z-50"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div className="relative flex items-center">
        <div className={`
          h-16 flex items-center bg-primary rounded-full shadow-lg transition-all duration-300 ease-in-out
          ${isHovered ? 'w-56' : 'w-16'}
        `}>
          <div className={`
            ml-6 mr-12 text-primary-foreground whitespace-nowrap overflow-hidden transition-all duration-300 ease-in-out
            ${isHovered ? 'opacity-100 max-w-40' : 'opacity-0 max-w-0'}
          `}>
            Umów demo
          </div>
          <div className="absolute right-0 flex items-center justify-center w-16 h-16">
            <Phone className="w-5 h-5 text-primary-foreground" />
          </div>
        </div>
      </div>
    </Link>
  );
}