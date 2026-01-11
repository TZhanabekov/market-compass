import { motion, AnimatePresence } from "framer-motion";
import { X, ArrowRight, Smartphone, Shield, Check, Minus, CreditCard } from "lucide-react";
import { Deal, LOCAL_MARKET_DATA } from "@/data/mockData";
import { AnimatedNumber } from "./AnimatedNumber";

interface ComparisonModalProps {
  isOpen: boolean;
  onClose: () => void;
  deal: Deal;
  onViewDeal: () => void;
}

export const ComparisonModal = ({ isOpen, onClose, deal, onViewDeal }: ComparisonModalProps) => {
  const savings = LOCAL_MARKET_DATA.iphone16pro_price_usd - deal.finalEffectivePrice;
  const savingsPercent = Math.round((savings / LOCAL_MARKET_DATA.iphone16pro_price_usd) * 100);

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50"
          />

          {/* Modal */}
          <motion.div
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", damping: 30, stiffness: 300 }}
            className="fixed inset-x-0 bottom-0 z-50 max-h-[90vh] overflow-y-auto rounded-t-3xl bg-background titanium-border border-b-0"
          >
            {/* Handle Bar */}
            <div className="sticky top-0 bg-background pt-4 pb-2 flex justify-center">
              <div className="w-12 h-1.5 rounded-full bg-titanium/30" />
            </div>

            {/* Header */}
            <div className="px-6 pb-4 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-foreground">
                  Arbitrage Analysis
                </h2>
                <p className="text-sm text-titanium">
                  {LOCAL_MARKET_DATA.country} vs. {deal.country}
                </p>
              </div>
              <motion.button
                whileHover={{ scale: 1.1 }}
                whileTap={{ scale: 0.9 }}
                onClick={onClose}
                className="w-10 h-10 rounded-full glass titanium-border flex items-center justify-center"
              >
                <X className="w-5 h-5 text-titanium" />
              </motion.button>
            </div>

            {/* Content */}
            <div className="px-6 pb-6 space-y-6">
              {/* Price Breakdown Table */}
              <div className="card-titanium p-4">
                <h3 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                  <Smartphone className="w-4 h-4 text-primary" />
                  Price Breakdown
                </h3>
                
                {/* Table Header */}
                <div className="grid grid-cols-3 gap-2 mb-3 pb-3 border-b titanium-border border-x-0 border-t-0">
                  <div className="text-xs text-titanium"></div>
                  <div className="text-xs text-titanium text-center font-medium">
                    Local ({LOCAL_MARKET_DATA.country})
                  </div>
                  <div className="text-xs text-primary text-center font-medium">
                    Target ({deal.country})
                  </div>
                </div>

                {/* Retail Price Row */}
                <div className="grid grid-cols-3 gap-2 py-3 border-b titanium-border border-x-0 border-t-0">
                  <div className="text-sm text-titanium">Retail Price</div>
                  <div className="text-sm text-foreground text-center font-medium">
                    ${LOCAL_MARKET_DATA.iphone16pro_price_usd}
                  </div>
                  <div className="text-sm text-foreground text-center font-medium">
                    ${deal.priceUsd}
                  </div>
                </div>

                {/* Tax Refund Row */}
                <div className="grid grid-cols-3 gap-2 py-3 border-b titanium-border border-x-0 border-t-0">
                  <div className="text-sm text-titanium">Tax Refund (Est.)</div>
                  <div className="text-sm text-titanium text-center">
                    —
                  </div>
                  <div className="text-sm text-success text-center font-medium">
                    {deal.taxRefundValue > 0 ? `-$${deal.taxRefundValue}` : "—"}
                  </div>
                </div>

                {/* Effective Price Row */}
                <div className="grid grid-cols-3 gap-2 py-3">
                  <div className="text-sm font-semibold text-foreground">Effective Price</div>
                  <div className="text-base text-foreground text-center font-bold">
                    ${LOCAL_MARKET_DATA.iphone16pro_price_usd}
                  </div>
                  <div className="text-base text-success text-center font-bold">
                    $<AnimatedNumber value={deal.finalEffectivePrice} />
                  </div>
                </div>

                {/* Savings Highlight */}
                <div className="mt-4 p-3 rounded-xl bg-success/10 border border-success/30 flex items-center justify-between">
                  <span className="text-sm text-foreground font-medium">Total Savings</span>
                  <span className="text-lg font-bold text-success">
                    $<AnimatedNumber value={savings} /> ({savingsPercent}%)
                  </span>
                </div>
              </div>

              {/* Hardware Spec Table */}
              <div className="card-titanium p-4">
                <h3 className="text-sm font-semibold text-foreground mb-4 flex items-center gap-2">
                  <Shield className="w-4 h-4 text-primary" />
                  Hardware Comparison
                </h3>

                {/* Table Header */}
                <div className="grid grid-cols-3 gap-2 mb-3 pb-3 border-b titanium-border border-x-0 border-t-0">
                  <div className="text-xs text-titanium"></div>
                  <div className="text-xs text-titanium text-center font-medium">
                    Local ({LOCAL_MARKET_DATA.country})
                  </div>
                  <div className="text-xs text-primary text-center font-medium">
                    Target ({deal.country})
                  </div>
                </div>

                {/* SIM Type Row */}
                <div className="grid grid-cols-3 gap-2 py-3 border-b titanium-border border-x-0 border-t-0">
                  <div className="text-sm text-titanium flex items-center gap-1.5">
                    <CreditCard className="w-3.5 h-3.5" />
                    SIM Type
                  </div>
                  <div className="text-xs text-foreground text-center">
                    {LOCAL_MARKET_DATA.simType}
                  </div>
                  <div className="text-xs text-foreground text-center">
                    {deal.simType}
                  </div>
                </div>

                {/* Warranty Row */}
                <div className="grid grid-cols-3 gap-2 py-3">
                  <div className="text-sm text-titanium flex items-center gap-1.5">
                    <Shield className="w-3.5 h-3.5" />
                    Warranty
                  </div>
                  <div className="text-xs text-foreground text-center">
                    {LOCAL_MARKET_DATA.warranty}
                  </div>
                  <div className="text-xs text-foreground text-center">
                    {deal.warranty}
                  </div>
                </div>

                {/* SIM Compatibility Check */}
                <div className="mt-4 p-3 rounded-xl bg-surface-1 titanium-border">
                  <div className="flex items-center gap-2">
                    {deal.simType === LOCAL_MARKET_DATA.simType ? (
                      <>
                        <Check className="w-4 h-4 text-success" />
                        <span className="text-xs text-titanium">SIM type matches your local model</span>
                      </>
                    ) : (
                      <>
                        <Minus className="w-4 h-4 text-warning" />
                        <span className="text-xs text-titanium">Different SIM configuration - verify compatibility</span>
                      </>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Sticky Footer CTA */}
            <div className="sticky bottom-0 p-6 bg-gradient-to-t from-background via-background to-transparent">
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={onViewDeal}
                className="w-full btn-electric flex items-center justify-center gap-2 py-4"
              >
                View {deal.country} Deal & Guide
                <ArrowRight className="w-4 h-4" />
              </motion.button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};
