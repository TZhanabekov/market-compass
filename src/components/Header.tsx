import { motion } from "framer-motion";
import { MapPin, ChevronDown } from "lucide-react";

export const Header = () => {
  return (
    <motion.header
      initial={{ y: -20, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
      className="sticky top-0 z-50 glass border-b border-glass-border"
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

          {/* Location Bar */}
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="flex items-center gap-2 px-4 py-2 rounded-full glass hover:bg-surface-2 transition-colors"
          >
            <MapPin className="w-4 h-4 text-primary" />
            <span className="text-sm text-titanium">
              <span className="hidden sm:inline">📍 Sensed from IP: </span>
              <span className="text-foreground font-medium">Germany</span>
            </span>
            <ChevronDown className="w-4 h-4 text-titanium" />
          </motion.button>
        </div>
      </div>
    </motion.header>
  );
};
