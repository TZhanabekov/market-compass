import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, MapPin, AlertTriangle, Search } from "lucide-react";

interface LocationModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentLocation: string;
  onLocationChange: (location: string) => void;
}

const LOCATIONS = [
  { code: "DE", name: "Germany", flag: "🇩🇪" },
  { code: "US", name: "United States", flag: "🇺🇸" },
  { code: "GB", name: "United Kingdom", flag: "🇬🇧" },
  { code: "FR", name: "France", flag: "🇫🇷" },
  { code: "JP", name: "Japan", flag: "🇯🇵" },
  { code: "AU", name: "Australia", flag: "🇦🇺" },
  { code: "CA", name: "Canada", flag: "🇨🇦" },
  { code: "SG", name: "Singapore", flag: "🇸🇬" },
];

export const LocationModal = ({ 
  isOpen, 
  onClose, 
  currentLocation, 
  onLocationChange 
}: LocationModalProps) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [showVpnWarning] = useState(true);

  const filteredLocations = LOCATIONS.filter(loc =>
    loc.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50"
            onClick={onClose}
          />
          
          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ type: "spring", damping: 25, stiffness: 300 }}
            className="fixed left-4 right-4 top-1/2 -translate-y-1/2 z-50 max-w-md mx-auto"
          >
            <div className="glass-card rounded-3xl p-6 titanium-border">
              {/* Header */}
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-primary/20 flex items-center justify-center">
                    <MapPin className="w-5 h-5 text-primary" />
                  </div>
                  <div>
                    <h2 className="text-lg font-bold text-foreground">Your Location</h2>
                    <p className="text-sm text-titanium">Select your home market</p>
                  </div>
                </div>
                <motion.button
                  whileHover={{ scale: 1.1 }}
                  whileTap={{ scale: 0.9 }}
                  onClick={onClose}
                  className="w-8 h-8 rounded-full bg-surface-2 flex items-center justify-center"
                >
                  <X className="w-4 h-4 text-titanium" />
                </motion.button>
              </div>

              {/* VPN Warning */}
              {showVpnWarning && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex gap-3 p-3 rounded-xl bg-warning/10 mb-4 titanium-border"
                >
                  <AlertTriangle className="w-5 h-5 text-warning flex-shrink-0" />
                  <p className="text-sm text-titanium">
                    VPN detected. Your actual location may differ from IP-sensed location.
                  </p>
                </motion.div>
              )}

              {/* Search */}
              <div className="relative mb-4">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-titanium" />
                <input
                  type="text"
                  placeholder="Search countries..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-10 pr-4 py-3 rounded-xl bg-surface-1 titanium-border text-foreground placeholder:text-titanium/50 focus:outline-none focus:border-primary/50"
                />
              </div>

              {/* Location List */}
              <div className="space-y-2 max-h-64 overflow-y-auto scrollbar-hide">
                {filteredLocations.map((location) => {
                  const isSelected = location.name === currentLocation;
                  return (
                    <motion.button
                      key={location.code}
                      whileHover={{ scale: 1.01, x: 4 }}
                      whileTap={{ scale: 0.99 }}
                      onClick={() => {
                        onLocationChange(location.name);
                        onClose();
                      }}
                      className={`
                        w-full flex items-center gap-3 p-3 rounded-xl transition-all
                        ${isSelected 
                          ? "bg-primary/20 border border-primary/50" 
                          : "bg-surface-1 titanium-border hover:bg-surface-2"
                        }
                      `}
                    >
                      <span className="text-2xl">{location.flag}</span>
                      <span className={`font-medium ${isSelected ? "text-foreground" : "text-titanium"}`}>
                        {location.name}
                      </span>
                      {isSelected && (
                        <div className="ml-auto w-2 h-2 rounded-full bg-primary" />
                      )}
                    </motion.button>
                  );
                })}
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};
