import { motion } from "framer-motion";
import { Smartphone } from "lucide-react";
import { MODELS } from "@/data/mockData";

interface ModelSelectorProps {
  selectedModel: string;
  onSelectModel: (id: string) => void;
}

export const ModelSelector = ({ selectedModel, onSelectModel }: ModelSelectorProps) => {
  return (
    <section className="py-6">
      <motion.h2
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="text-sm font-medium text-titanium uppercase tracking-wider mb-4 px-4"
      >
        Select Model
      </motion.h2>
      
      <div className="flex gap-3 overflow-x-auto pb-4 px-4 scrollbar-hide">
        {MODELS.map((model, index) => {
          const isSelected = selectedModel === model.id;
          
          return (
            <motion.button
              key={model.id}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.1 + index * 0.05 }}
              whileHover={{ scale: 1.02, y: -2 }}
              whileTap={{ scale: 0.98 }}
              onClick={() => onSelectModel(model.id)}
              className={`
                relative flex-shrink-0 flex flex-col items-center gap-3 p-4 rounded-2xl
                min-w-[120px] transition-all duration-300
                ${isSelected 
                  ? "glass-card border-2 border-primary glow-blue-subtle" 
                  : "glass-card border border-transparent hover:border-glass-border"
                }
              `}
            >
              {/* Phone Icon */}
              <div className={`
                w-14 h-14 rounded-xl flex items-center justify-center
                ${isSelected ? "bg-primary/20" : "bg-surface-2"}
                transition-colors duration-300
              `}>
                <Smartphone 
                  className={`w-7 h-7 ${isSelected ? "text-primary" : "text-titanium"}`}
                />
              </div>
              
              {/* Model Name */}
              <span className={`
                text-sm font-semibold tracking-tight whitespace-nowrap
                ${isSelected ? "text-foreground" : "text-titanium"}
              `}>
                {model.name}
              </span>

              {/* Selection indicator */}
              {isSelected && (
                <motion.div
                  layoutId="model-indicator"
                  className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-8 h-1 bg-primary rounded-full"
                  transition={{ type: "spring", stiffness: 400, damping: 30 }}
                />
              )}
            </motion.button>
          );
        })}
      </div>
    </section>
  );
};
