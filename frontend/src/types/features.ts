type TierName = 'Darmowy' | 'Standard' | 'Enterprise';


type Frequency = {
  value: 'monthly' | 'annually'
  label: string
  priceSuffix: string
}

type Tier = {
  name: string
  id: 'free' | 'standard' | 'enterprise'
  href: string
  description: string
  features: string[]
  mostPopular: boolean
  buttonText: string
}


interface StringFeature {
  name: string;
  tiers: Record<TierName, string>;
}

interface BooleanFeature {
  name: string;
  tiers: Record<TierName, boolean>;
}

type Feature = StringFeature | BooleanFeature;

interface Section {
  name: string;
  features: Feature[];
}

type FrequencyOption = 'monthly' | 'annually';
