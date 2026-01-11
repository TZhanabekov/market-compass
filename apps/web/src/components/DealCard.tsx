"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, AlertTriangle, ArrowRight, MapPin, Plane, Cpu, Check } from "lucide-react";
import { Deal, LOCAL_MARKET_DATA } from "@/data/mockData";
import { TrustMeter } from "./TrustMeter";
import { AnimatedNumber } from "./AnimatedNumber";

interface DealCardProps {
  deal: Deal;
  index: number;
  minTrust: number;
}

// Icon mapping for guide steps
const getGuideIcon = (iconName: string) => {
  const icons: Record<string, React.ReactNode> = {
    "map-pin": <MapPin className="w-4 h-4 text-primary" />,
    "plane": <Plane className="w-4 h-4 text-primary" />,
    "cpu": <Cpu className="w-4 h-4 text-primary" />,
    "check": <Check className="w-4 h-4 text-success" />,
    "alert-triangle": <AlertTriangle className="w-4 h-4 text-warning" />,
  };
  return icons[iconName] || <MapPin className="w-4 h-4 text-primary" />;
};

export const DealCard = ({ deal, index, minTrust }: DealCardProps) => {
  const [isExpanded, setIsExpanded] = useState(false);
  
  // Calculate savings relative to local market price
  const savingsUsd = LOCAL_MARKET_DATA.iphone16pro_price_usd - deal.finalEffectivePrice;
  
  // Filter out deals below trust threshold
  if (deal.trustScore < minTrust) return null;

  // Availability dot class
  const getAvailabilityClass = () => {
    switch (deal.availability) {
      case "In Stock": return "availability-dot availability-dot-instock";
      case "Limited": return "availability-dot availability-dot-limited";
      case "Out of Stock": return "availability-dot availability-dot-outofstock";
      default: return "availability-dot availability-dot-limited";
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
            <AnimatedNumber value={deal.finalEffectivePrice} prefix="$" />
          </div>
          <div className="text-sm text-success font-medium">
            Save <AnimatedNumber value={savingsUsd} prefix="$" />
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
              {/* Savings Header */}
              <div className="flex items-center justify-between p-3 rounded-xl bg-success/10 border border-success/30">
                <span className="text-sm text-foreground font-medium">Potential Savings vs {LOCAL_MARKET_DATA.country}</span>
                <span className="text-lg font-bold text-success">
                  $<AnimatedNumber value={savingsUsd} />
                </span>
              </div>

              {/* Hardware Alert */}
              {deal.restrictionAlert && (
                <div className="flex gap-3 p-3 rounded-xl bg-warning/10 titanium-border">
                  <div className="w-8 h-8 rounded-lg bg-warning/20 flex items-center justify-center flex-shrink-0">
                    <AlertTriangle className="w-4 h-4 text-warning" />
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-foreground mb-1">
                      Hardware Alert
                    </h4>
                    <p className="text-sm text-titanium leading-relaxed">
                      {deal.restrictionAlert}
                    </p>
                  </div>
                </div>
              )}

              {/* Tactical Intel Section */}
              <div className="p-4 rounded-xl bg-surface-1 titanium-border">
                <h4 className="text-sm font-semibold text-foreground mb-3 flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-primary" />
                  Tactical Intel
                </h4>
                <div className="space-y-3">
                  {deal.guideSteps.map((step, stepIndex) => (
                    <motion.div
                      key={stepIndex}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: stepIndex * 0.1 }}
                      className="flex gap-3"
                    >
                      <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                        {getGuideIcon(step.icon)}
                      </div>
                      <div>
                        <h5 className="text-sm font-semibold text-foreground">
                          {step.title}
                        </h5>
                        <p className="text-sm text-titanium leading-relaxed">
                          {step.desc}
                        </p>
                      </div>
                    </motion.div>
                  ))}
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
