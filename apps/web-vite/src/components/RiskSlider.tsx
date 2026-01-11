import { motion } from "framer-motion";
import { Shield, ShieldAlert, ShieldCheck } from "lucide-react";
import { Slider } from "@/components/ui/slider";

interface RiskSliderProps {
  value: number;
  onChange: (value: number) => void;
}

export const RiskSlider = ({ value, onChange }: RiskSliderProps) => {
  const getRiskLevel = () => {
    if (value >= 95) return { label: "Conservative", icon: ShieldCheck, color: "text-success" };
    if (value >= 85) return { label: "Balanced", icon: Shield, color: "text-primary" };
    return { label: "Aggressive", icon: ShieldAlert, color: "text-warning" };
  };

  const risk = getRiskLevel();
  const RiskIcon = risk.icon;

  return (
    <motion.div
      initial={{ y: 100, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ delay: 0.4, type: "spring", stiffness: 100 }}
      className="fixed bottom-0 left-0 right-0 z-50 p-4"
    >
      <div className="container mx-auto max-w-2xl">
        <div className="glass-card rounded-2xl p-4 shadow-2xl titanium-border">
          <div className="flex items-center gap-4 mb-3">
            <div className={`w-10 h-10 rounded-xl bg-surface-2 flex items-center justify-center titanium-border ${risk.color}`}>
              <RiskIcon className="w-5 h-5" />
            </div>
            <div className="flex-1">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-foreground">Risk Tolerance</span>
                <span className={`text-sm font-semibold ${risk.color}`}>{risk.label}</span>
              </div>
              <p className="text-xs text-titanium">Min trust score: {value}</p>
            </div>
          </div>
          
          <Slider
            value={[value]}
            onValueChange={(v) => onChange(v[0])}
            min={0}
            max={100}
            step={5}
            className="py-2"
          />
          
          <div className="flex justify-between text-xs text-titanium mt-1">
            <span>High Risk</span>
            <span>Low Risk</span>
          </div>
        </div>
      </div>
    </motion.div>
  );
};
