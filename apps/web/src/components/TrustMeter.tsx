"use client";

import { motion } from "framer-motion";

interface TrustMeterProps {
  score: number;
}

export const TrustMeter = ({ score }: TrustMeterProps) => {
  const bars = 5;
  const filledBars = Math.round((score / 100) * bars);

  return (
    <div className="flex items-center gap-1.5">
      {Array.from({ length: bars }).map((_, index) => (
        <motion.div
          key={index}
          initial={{ scaleY: 0 }}
          animate={{ scaleY: 1 }}
          transition={{ delay: index * 0.05, duration: 0.3 }}
          className={`
            w-1.5 rounded-full transition-all duration-300 origin-bottom
            ${index < filledBars 
              ? "bg-primary h-3" 
              : "bg-surface-3 h-2"
            }
          `}
          style={{
            boxShadow: index < filledBars ? "0 0 6px oklch(0.6 0.2 250 / 50%)" : "none"
          }}
        />
      ))}
      <span className="ml-1 text-xs font-medium text-titanium tabular-nums">{score}</span>
    </div>
  );
};
