export interface GuideStep {
  icon: string;
  title: string;
  desc: string;
}

export interface Deal {
  rank: number;
  country: string;
  city: string;
  flag: string;
  priceUsd: number;
  taxRefundValue: number;
  finalEffectivePrice: number;
  localPrice: string;
  savings: number;
  shop: string;
  availability: "In Stock" | "Limited" | "Out of Stock";
  trustScore: number;
  simType: string;
  warranty: string;
  restrictionAlert: string;
  guideSteps: GuideStep[];
}

export interface Model {
  id: string;
  name: string;
  icon: string;
}

export interface LocalMarket {
  country: string;
  currency: string;
  iphone16pro_price_usd: number;
  simType: string;
  warranty: string;
}

export const LOCAL_MARKET_DATA: LocalMarket = {
  country: "Germany",
  currency: "€ (EUR)",
  iphone16pro_price_usd: 1199,
  simType: "eSIM + Physical SIM",
  warranty: "2-Year EU Consumer Law"
};

export const MOCK_DEALS: Deal[] = [
  {
    rank: 1,
    country: "Japan",
    city: "Tokyo",
    flag: "🇯🇵",
    priceUsd: 741,
    taxRefundValue: 65,
    finalEffectivePrice: 676,
    localPrice: "¥112,800",
    savings: 44,
    shop: "Bic Camera",
    availability: "In Stock",
    trustScore: 98,
    simType: "eSIM + Physical SIM",
    warranty: "1-Year Apple Global",
    restrictionAlert: "Camera shutter sound always on (J/A model)",
    guideSteps: [
      { icon: "map-pin", title: "Where to Buy", desc: "Bic Camera Yurakucho. Show passport at checkout for tax-free price." },
      { icon: "plane", title: "Airport Refund", desc: "Narita Terminal 2, 'Customs' counter before security. Goods must be sealed." },
      { icon: "cpu", title: "Hardware Check", desc: "Verify Model A3102. Shutter sound is permanent." }
    ]
  },
  {
    rank: 2,
    country: "USA",
    city: "Delaware",
    flag: "🇺🇸",
    priceUsd: 799,
    taxRefundValue: 0,
    finalEffectivePrice: 799,
    localPrice: "$799",
    savings: 33,
    shop: "Apple Store",
    availability: "Limited",
    trustScore: 100,
    simType: "eSIM Only (No Physical Slot)",
    warranty: "1-Year Apple Global",
    restrictionAlert: "Model LL/A - No physical SIM tray.",
    guideSteps: [
      { icon: "map-pin", title: "Tax-Free State", desc: "Buy in Delaware or Oregon for 0% sales tax at register." },
      { icon: "cpu", title: "Important Info", desc: "Ensure your home carrier supports eSIM before buying." }
    ]
  },
  {
    rank: 3,
    country: "Hong Kong",
    city: "Central",
    flag: "🇭🇰",
    priceUsd: 815,
    taxRefundValue: 0,
    finalEffectivePrice: 815,
    localPrice: "HK$6,350",
    savings: 32,
    shop: "Fortress HK",
    availability: "In Stock",
    trustScore: 94,
    simType: "Dual Physical SIM",
    warranty: "1-Year Apple Global",
    restrictionAlert: "Dual Physical SIM slots supported (ZA/A model)",
    guideSteps: [
      { icon: "map-pin", title: "Where to Buy", desc: "Fortress HK in Central or Apple Causeway Bay for official pricing." },
      { icon: "check", title: "Free Port", desc: "HK is a free port. No VAT refund needed, prices are already net." }
    ]
  },
  {
    rank: 4,
    country: "UAE",
    city: "Dubai",
    flag: "🇦🇪",
    priceUsd: 845,
    taxRefundValue: 35,
    finalEffectivePrice: 810,
    localPrice: "AED 3,100",
    savings: 32,
    shop: "Sharaf DG",
    availability: "In Stock",
    trustScore: 92,
    simType: "eSIM + Physical SIM",
    warranty: "1-Year Apple Global",
    restrictionAlert: "FaceTime usually works outside UAE, but verify.",
    guideSteps: [
      { icon: "plane", title: "Planet Tax Free", desc: "Scan QR code at Planet kiosks in DXB Terminal 3 before checking bags." },
      { icon: "alert-triangle", title: "FaceTime Note", desc: "FaceTime is disabled in UAE but usually activates when abroad." }
    ]
  }
];

export const MODELS: Model[] = [
  { id: '16pro', name: '16 Pro', icon: 'smartphone' },
  { id: '16promax', name: '16 Pro Max', icon: 'smartphone' }
];

export const BASE_PRICE_EUR = 1200;
