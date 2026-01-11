import { z } from "zod";

export const CurrencyCodeSchema = z.string().min(3).max(3);

export const GuideStepSchema = z.object({
  icon: z.string().min(1),
  title: z.string().min(1),
  desc: z.string().min(1),
});
export type GuideStep = z.infer<typeof GuideStepSchema>;

export const DealSchema = z.object({
  offerId: z.string().min(1),

  rank: z.number().int().min(1).max(10),

  countryCode: z.string().min(2).max(2),
  country: z.string().min(1),
  city: z.string().min(1),
  flag: z.string().min(1),

  shop: z.string().min(1),
  availability: z.string().min(1),

  priceUsd: z.number().nonnegative(),
  taxRefundValue: z.number().nonnegative(),
  finalEffectivePrice: z.number().nonnegative(),

  localPrice: z.string().min(1),

  trustScore: z.number().int().min(0).max(100),

  simType: z.string().min(1),
  warranty: z.string().min(1),

  restrictionAlert: z.string().min(1),
  guideSteps: z.array(GuideStepSchema).max(10),
});
export type Deal = z.infer<typeof DealSchema>;

export const LocalMarketSchema = z.object({
  countryCode: z.string().min(2).max(2),
  country: z.string().min(1),
  currency: CurrencyCodeSchema,
  localPriceUsd: z.number().nonnegative(),
  simType: z.string().min(1),
  warranty: z.string().min(1),
});
export type LocalMarket = z.infer<typeof LocalMarketSchema>;

export const HomeResponseSchema = z.object({
  modelKey: z.string().min(1),
  skuKey: z.string().min(1),

  minTrust: z.number().int().min(0).max(100),

  homeMarket: LocalMarketSchema,

  globalWinnerOfferId: z.string().min(1),
  leaderboard: z.object({
    deals: z.array(DealSchema).max(10),
    matchCount: z.number().int().min(0),
    lastUpdatedAt: z.string().min(1) // ISO
  }),
});
export type HomeResponse = z.infer<typeof HomeResponseSchema>;
