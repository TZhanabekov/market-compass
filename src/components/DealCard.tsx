import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, Plane, AlertTriangle, ArrowRight } from "lucide-react";
import { Deal, BASE_PRICE_EUR } from "@/data/mockData";
import { TrustMeter } from "./TrustMeter";
import { AnimatedNumber } from "./AnimatedNumber";

interface DealCardProps {
  deal: Deal;
  index: number;
  minTrust: number;
}

export const DealCard = ({ deal, index, minTrust }: DealCardProps) => {
  const [isExpanded, setIsExpanded] = useState(false);
  
  // Calculate EUR savings relative to base price
  const savingsEur = Math.round(BASE_PRICE_EUR * (deal.savings / 100));
  
  // Filter out deals below trust threshold
  if (deal.trustScore < minTrust) return null;

  // Availability dot class
  const getAvailabilityClass = () => {
    switch (deal.availability) {
      case "In Stock": return "availability-dot-instock";
      case "Limited": return "availability-dot-limited";
      case "Out of Stock": return "availability-dot-outofstock";
      default: return "availability-dot-limited";
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ delay: index * 0.08, duration: 0.4 }}
      layout
      className="card-titanium overflow-hidden"
    >
      {/* Main Card Content */}
      <div 
        className="flex items-center gap-4 cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        {/* Rank Badge */}
        <div className={`
          w-10 h-10 rounded-xl flex items-center justify-center font-bold text-lg titanium-border
          ${deal.rank === 1 
            ? "bg-primary/20 text-primary glow-blue-subtle border-primary/30" 
            : "bg-surface-2 text-titanium"
          }
        `}>
          #{deal.rank}
        </div>

        {/* Country Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-2xl">{deal.flag}</span>
            <span className="font-semibold text-foreground truncate">{deal.country}</span>
            <span className="text-sm text-titanium">• {deal.city}</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-titanium">{deal.shop}</span>
            <div className="flex items-center gap-1.5">
              <div className={getAvailabilityClass()} />
              <span className="text-xs text-titanium">{deal.availability}</span>
            </div>
          </div>
        </div>

        {/* Price & Savings with Animation */}
        <div className="text-right flex-shrink-0">
          <div className="text-lg font-bold text-foreground">
            <AnimatedNumber value={deal.priceUsd} prefix="$" />
          </div>
          <div className="text-sm text-success font-medium">
            Save <AnimatedNumber value={savingsEur} prefix="€" />
          </div>
        </div>

        {/* Trust Score & Expand */}
        <div className="flex items-center gap-3">
          <TrustMeter score={deal.trustScore} />
          <motion.div
            animate={{ rotate: isExpanded ? 180 : 0 }}
            transition={{ duration: 0.2 }}
            className="text-titanium"
          >
            <ChevronDown className="w-5 h-5" />
          </motion.div>
        </div>
      </div>

      {/* Expanded Content */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div className="pt-4 mt-4 border-t titanium-border border-x-0 border-b-0 space-y-4">
              {/* Tactical Guide */}
              <div className="flex gap-3 p-3 rounded-xl bg-surface-1 titanium-border">
                <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center flex-shrink-0">
                  <Plane className="w-4 h-4 text-primary" />
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-foreground mb-1">
                    Tactical Guide
                  </h4>
                  <p className="text-sm text-titanium leading-relaxed">
                    {deal.airportGuide}
                  </p>
                </div>
              </div>

              {/* Hardware Alert */}
              <div className="flex gap-3 p-3 rounded-xl bg-warning/10 titanium-border">
                <div className="w-8 h-8 rounded-lg bg-warning/20 flex items-center justify-center flex-shrink-0">
                  <AlertTriangle className="w-4 h-4 text-warning" />
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-foreground mb-1">
                    Hardware Alert
                  </h4>
                  <p className="text-sm text-titanium leading-relaxed">
                    {deal.restriction}
                  </p>
                </div>
              </div>

              {/* CTA Button - Mobile First, one-hand operation */}
              <motion.button
                whileHover={{ scale: 1.01, x: 4 }}
                whileTap={{ scale: 0.98 }}
                className="w-full btn-electric flex items-center justify-center gap-2 py-4"
              >
                Claim Arbitrage
                <ArrowRight className="w-4 h-4" />
              </motion.button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};
