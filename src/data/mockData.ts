export interface Deal {
  rank: number;
  country: string;
  city: string;
  flag: string;
  priceUsd: number;
  localPrice: string;
  savings: number;
  shop: string;
  availability: "In Stock" | "Limited" | "Out of Stock";
  trustScore: number;
  restriction: string;
  airportGuide: string;
}

export interface Model {
  id: string;
  name: string;
  icon: string;
}

export const MOCK_DEALS: Deal[] = [
  {
    rank: 1,
    country: "Japan",
    city: "Tokyo",
    flag: "🇯🇵",
    priceUsd: 741,
    localPrice: "¥112,800",
    savings: 38,
    shop: "Bic Camera",
    availability: "In Stock",
    trustScore: 98,
    restriction: "Camera shutter sound always on (J/A model)",
    airportGuide: "Tax Refund at Narita Terminal 2, look for the 'Tax-free' blue counter near Gate 61."
  },
  {
    rank: 2,
    country: "USA",
    city: "Delaware",
    flag: "🇺🇸",
    priceUsd: 799,
    localPrice: "$799",
    savings: 32,
    shop: "Apple Store (Tax-Free State)",
    availability: "Limited",
    trustScore: 100,
    restriction: "eSIM only, no physical SIM slot (LL/A model)",
    airportGuide: "No VAT refund in USA, but Delaware has 0% Sales Tax at point of purchase."
  },
  {
    rank: 3,
    country: "Hong Kong",
    city: "Central",
    flag: "🇭🇰",
    priceUsd: 815,
    localPrice: "HK$6,350",
    savings: 29,
    shop: "Fortress HK",
    availability: "In Stock",
    trustScore: 94,
    restriction: "Dual Physical SIM slots supported (ZA/A model)",
    airportGuide: "HK is a free port. No VAT refund needed, prices are already net."
  },
  {
    rank: 4,
    country: "UAE",
    city: "Dubai",
    flag: "🇦🇪",
    priceUsd: 845,
    localPrice: "AED 3,100",
    savings: 25,
    shop: "Sharaf DG",
    availability: "In Stock",
    trustScore: 92,
    restriction: "FaceTime now works, but model is AE/A",
    airportGuide: "Planet Tax Free kiosks at DXB Terminal 3. Scan QR code before checking bags."
  }
];

export const MODELS: Model[] = [
  { id: '16pro', name: '16 Pro', icon: 'smartphone' },
  { id: '16promax', name: '16 Pro Max', icon: 'smartphone' },
  { id: '16', name: 'iPhone 16', icon: 'smartphone' },
  { id: '15pro', name: '15 Pro', icon: 'smartphone' }
];

export const BASE_PRICE_EUR = 1200;
