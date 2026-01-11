"use client";

import { useEffect, useState } from "react";
import { motion, useSpring, useTransform } from "framer-motion";

interface AnimatedNumberProps {
  value: number;
  prefix?: string;
  suffix?: string;
  className?: string;
  duration?: number;
}

export const AnimatedNumber = ({ 
  value, 
  prefix = "", 
  suffix = "",
  className = "",
  duration = 0.8
}: AnimatedNumberProps) => {
  const [displayValue, setDisplayValue] = useState(value);
  
  const spring = useSpring(0, { 
    stiffness: 100, 
    damping: 30,
    duration: duration * 1000
  });
  
  const display = useTransform(spring, (latest) => Math.round(latest));

  useEffect(() => {
    spring.set(value);
    const unsubscribe = display.on("change", (latest) => {
      setDisplayValue(latest);
    });
    return () => unsubscribe();
  }, [value, spring, display]);

  return (
    <motion.span 
      className={className}
      key={value}
      initial={{ opacity: 0.5, y: -5 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
    >
      {prefix}{displayValue}{suffix}
    </motion.span>
  );
};
