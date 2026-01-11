import { useState } from "react";
import { motion } from "framer-motion";
import { MapPin, ChevronDown } from "lucide-react";
import { LocationModal } from "./LocationModal";
import { LOCAL_MARKET_DATA } from "@/data/mockData";

export const Header = () => {
  const [isLocationModalOpen, setIsLocationModalOpen] = useState(false);
  const [currentLocation, setCurrentLocation] = useState(LOCAL_MARKET_DATA.country);

  return (
    <>
      <motion.header
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
        className="sticky top-0 z-40 glass titanium-border border-t-0 border-x-0"
      >
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            {/* Logo */}
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center glow-blue-subtle">
                <span className="text-primary-foreground font-black text-sm">iP</span>
              </div>
              <span className="text-xl font-bold tracking-tight-custom text-foreground">
                iPASSPORT
              </span>
            </div>

            {/* Location Bar - Clickable to open modal */}
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => setIsLocationModalOpen(true)}
              className="flex items-center gap-2 px-4 py-2 rounded-full glass titanium-border hover:bg-surface-2 transition-colors"
            >
              <MapPin className="w-4 h-4 text-primary" />
              <span className="text-sm text-titanium">
                <span className="hidden sm:inline">📍 Sensed: </span>
                <span className="text-foreground font-medium">{currentLocation}</span>
                <span className="text-titanium ml-1.5 hidden sm:inline">
                  • Local: <span className="text-foreground font-medium">${LOCAL_MARKET_DATA.iphone16pro_price_usd}</span>
                </span>
              </span>
              <ChevronDown className="w-4 h-4 text-titanium" />
            </motion.button>
          </div>
        </div>
      </motion.header>

      {/* Location Modal */}
      <LocationModal
        isOpen={isLocationModalOpen}
        onClose={() => setIsLocationModalOpen(false)}
        currentLocation={currentLocation}
        onLocationChange={setCurrentLocation}
      />
    </>
  );
};
