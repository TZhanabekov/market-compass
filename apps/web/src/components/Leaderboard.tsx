"use client";

import { motion } from "framer-motion";
import { MOCK_DEALS } from "@/data/mockData";
import { DealCard } from "./DealCard";

interface LeaderboardProps {
  minTrust: number;
}

export const Leaderboard = ({ minTrust }: LeaderboardProps) => {
  const filteredDeals = MOCK_DEALS.filter(deal => deal.trustScore >= minTrust);

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
          {filteredDeals.length} matches
        </span>
      </motion.div>

      <div className="space-y-3">
        {MOCK_DEALS.map((deal, index) => (
          <DealCard 
            key={deal.rank} 
            deal={deal} 
            index={index}
            minTrust={minTrust}
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
