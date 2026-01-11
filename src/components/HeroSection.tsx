import { motion } from "framer-motion";
import { TrendingUp, Globe } from "lucide-react";

export const HeroSection = () => {
  return (
    <section className="px-4 pt-8 pb-4">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="text-center space-y-4"
      >
        <div className="flex items-center justify-center gap-2 text-primary">
          <Globe className="w-5 h-5" />
          <span className="text-sm font-medium uppercase tracking-wider">
            Real-time Arbitrage Intelligence
          </span>
        </div>
        
        <h1 className="text-4xl sm:text-5xl font-black tracking-tight-custom text-foreground">
          Outsmart{" "}
          <span className="text-gradient-blue">Global</span>
          {" "}Markets
        </h1>
        
        <p className="text-titanium text-lg max-w-md mx-auto">
          Find the best iPhone prices worldwide. Save up to €450 on your next device.
        </p>

        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.3 }}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass border border-success/30"
        >
          <TrendingUp className="w-4 h-4 text-success" />
          <span className="text-sm text-foreground">
            <span className="font-bold text-success">4</span> arbitrage opportunities available
          </span>
        </motion.div>
      </motion.div>
    </section>
  );
};
