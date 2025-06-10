import { SOURCE_CONFIG } from "@/app/constants/tenders";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { TenderSourceIconProps } from "@/types/tenders";
import Image from "next/image";

const isValidSource = (key: string): key is keyof typeof SOURCE_CONFIG => {
  return key in SOURCE_CONFIG;
};

const TenderSourceIcon: React.FC<TenderSourceIconProps> = ({ source, url }) => {
  let sourceConfig = source && isValidSource(source) ? SOURCE_CONFIG[source] : undefined;
  
  if (!sourceConfig && url) {
    const sourceType = Object.keys(SOURCE_CONFIG).find(key => {
      if (!isValidSource(key)) return false;
      const config = SOURCE_CONFIG[key as keyof typeof SOURCE_CONFIG];
      return config.urlPattern && url.includes(config.urlPattern);
    });
    
    if (sourceType && isValidSource(sourceType)) {
      sourceConfig = SOURCE_CONFIG[sourceType];
    }
  }
  
  if (!sourceConfig) return null;

  const isTedSource = source?.includes('ted');

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className={`relative ${isTedSource ? 'w-7 h-7' : 'w-5 h-5'}`}>
            <Image
              src={sourceConfig.icon}
              alt={sourceConfig.label}
              fill
              className="object-contain"
            />
          </div>
        </TooltipTrigger>
        <TooltipContent>
          <p>{sourceConfig.label}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};

export default TenderSourceIcon;