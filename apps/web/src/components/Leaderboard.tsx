"use client";

import { motion } from "framer-motion";
import { DealCard } from "./DealCard";
import type { Deal, HomeMarket } from "@/lib/api";

interface LeaderboardProps {
  minTrust: number;
  deals: Deal[];
  matchCount: number;
  homeMarket: HomeMarket;
  isLoading?: boolean;
  error?: Error | null;
}

export const Leaderboard = ({ 
  minTrust, 
  deals, 
  matchCount,
  homeMarket,
  isLoading,
  error 
}: LeaderboardProps) => {
  // Filter deals by trust score (API already filters, but we do it client-side too for UI consistency)
  const filteredDeals = deals.filter(deal => deal.trustScore >= minTrust);

  if (isLoading) {
    return (
      <section className="px-4 pb-32">
        <div className="text-center py-12">
          <p className="text-titanium">Loading deals...</p>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="px-4 pb-32">
        <div className="text-center py-12">
          <p className="text-warning">Failed to load deals. Please try again later.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="px-4 pb-32">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="flex items-center justify-between mb-4"
      >
        <h2 className="text-sm font-medium text-titanium uppercase tracking-wider">
          Top 10 Global Deals
        </h2>
        <span className="text-xs text-titanium titanium-border px-2 py-1 rounded-full">
          {matchCount} matches
        </span>
      </motion.div>

      <div className="space-y-3">
        {filteredDeals.map((deal, index) => (
          <DealCard 
            key={deal.offerId} 
            deal={deal} 
            index={index}
            minTrust={minTrust}
            homeMarket={homeMarket}
          />
        ))}
      </div>

      {filteredDeals.length === 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-center py-12"
        >
          <p className="text-titanium text-lg">No deals match your trust threshold</p>
          <p className="text-sm text-titanium/60 mt-1">Try lowering your risk tolerance</p>
        </motion.div>
      )}
    </section>
  );
};
