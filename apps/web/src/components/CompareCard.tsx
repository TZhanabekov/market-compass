"use client";

import { motion } from "framer-motion";
import { ArrowRight, TrendingDown } from "lucide-react";
import { LOCAL_MARKET_DATA, MOCK_DEALS } from "@/data/mockData";
import { AnimatedNumber } from "./AnimatedNumber";

interface CompareCardProps {
  onCompareClick: () => void;
}

export const CompareCard = ({ onCompareClick }: CompareCardProps) => {
  const bestDeal = MOCK_DEALS[0];
  const savings = LOCAL_MARKET_DATA.iphone16pro_price_usd - bestDeal.finalEffectivePrice;
  const savingsPercent = Math.round((savings / LOCAL_MARKET_DATA.iphone16pro_price_usd) * 100);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.3, duration: 0.5 }}
      className="px-4 mb-6"
    >
      <motion.button
        whileHover={{ scale: 1.01, y: -2 }}
        whileTap={{ scale: 0.99 }}
        onClick={onCompareClick}
        className="w-full card-titanium p-5 text-left group"
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-success/20 flex items-center justify-center">
              <TrendingDown className="w-4 h-4 text-success" />
            </div>
            <span className="text-sm font-semibold text-foreground">
              Compare Local vs. Global Winner
            </span>
          </div>
          <motion.div
            className="text-titanium group-hover:text-primary transition-colors"
            animate={{ x: [0, 4, 0] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          >
            <ArrowRight className="w-5 h-5" />
          </motion.div>
        </div>

        {/* Comparison Preview */}
        <div className="flex items-center justify-between gap-4">
          {/* Local Market */}
          <div className="flex-1 text-center p-3 rounded-xl bg-surface-1 titanium-border">
            <div className="text-xs text-titanium mb-1">
              {LOCAL_MARKET_DATA.country}
            </div>
            <div className="text-lg font-bold text-titanium">
              ${LOCAL_MARKET_DATA.iphone16pro_price_usd}
            </div>
          </div>

          {/* VS Badge */}
          <div className="flex-shrink-0 text-xs font-bold text-titanium">
            VS
          </div>

          {/* Best Deal */}
          <div className="flex-1 text-center p-3 rounded-xl bg-success/10 border border-success/30">
            <div className="text-xs text-titanium mb-1 flex items-center justify-center gap-1">
              <span>{bestDeal.flag}</span>
              <span>{bestDeal.country}</span>
            </div>
            <div className="text-lg font-bold text-success">
              $<AnimatedNumber value={bestDeal.finalEffectivePrice} />
            </div>
          </div>
        </div>

        {/* Savings Banner */}
        <div className="mt-4 flex items-center justify-center gap-2 py-2 px-4 rounded-full bg-success/10 border border-success/20">
          <span className="text-sm text-success font-semibold">
            Save <AnimatedNumber value={savings} prefix="$" /> ({savingsPercent}%)
          </span>
        </div>
      </motion.button>
    </motion.div>
  );
};
