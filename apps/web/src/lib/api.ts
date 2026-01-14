/**
 * API client for Market Compass backend
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

export interface GuideStep {
  icon: string;
  title: string;
  desc: string;
}

export interface Deal {
  offerId: string;
  rank: number;
  countryCode: string;
  country: string;
  city: string;
  flag: string;
  shop: string;
  availability: string;
  priceUsd: number;
  taxRefundValue: number;
  finalEffectivePrice: number;
  localPrice: string;
  trustScore: number;
  simType: string;
  warranty: string;
  restrictionAlert: string | null;
  guideSteps: GuideStep[];
}

export interface HomeMarket {
  countryCode: string;
  country: string;
  currency: string;
  localPriceUsd: number;
  simType: string;
  warranty: string;
}

export interface Leaderboard {
  deals: Deal[];
  matchCount: number;
  lastUpdatedAt: string;
}

export interface HomeResponse {
  modelKey: string;
  skuKey: string;
  minTrust: number;
  homeMarket: HomeMarket;
  globalWinnerOfferId: string;
  leaderboard: Leaderboard;
}

export interface HomeQueryParams {
  sku?: string;
  home?: string;
  minTrust?: number;
  lang?: string;
}

/**
 * Fetch home page data from API
 */
export async function fetchHomeData(params: HomeQueryParams = {}): Promise<HomeResponse> {
  const searchParams = new URLSearchParams();
  
  if (params.sku) searchParams.set('sku', params.sku);
  if (params.home) searchParams.set('home', params.home);
  if (params.minTrust !== undefined) searchParams.set('minTrust', params.minTrust.toString());
  if (params.lang) searchParams.set('lang', params.lang);

  const url = `${API_BASE_URL}/v1/ui/home?${searchParams.toString()}`;
  
  const response = await fetch(url, {
    headers: {
      'Accept': 'application/json',
    },
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`API error: ${response.status} ${errorText}`);
  }

  return response.json();
}

/**
 * Health check endpoint
 */
export async function checkHealth(): Promise<{ ok: boolean }> {
  const response = await fetch(`${API_BASE_URL}/health`, {
    headers: {
      'Accept': 'application/json',
    },
  });

  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status}`);
  }

  return response.json();
}
