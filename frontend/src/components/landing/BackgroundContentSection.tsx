import React, { PropsWithChildren } from 'react';
import Image from 'next/image';

interface BackgroundContentSectionProps {
  backgroundSrc?: string;
  alt?: string;
}

const BackgroundContentSection: React.FC<PropsWithChildren<BackgroundContentSectionProps>> = ({ 
  children, 
  backgroundSrc = '/images/asystent_firmowy_mockup.png',
  alt = 'Background'
}) => {
  return (
    <div className="relative w-full my-20">
      {/* Background Image Container */}
      <div className="absolute inset-0 w-full h-full">
        <Image
          src={backgroundSrc}
          alt={alt}
          fill
          className="object-cover rounded-3xl mx-auto max-w-7xl"
          priority
        />
      </div>
      
      {/* Content Overlay */}
      <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="bg-background/80 backdrop-blur-sm rounded-2xl p-12 shadow-xl">
          {children}
        </div>
      </div>
    </div>
  );
};

export default BackgroundContentSection;