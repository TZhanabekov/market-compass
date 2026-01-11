interface TrustMeterProps {
  score: number;
}

export const TrustMeter = ({ score }: TrustMeterProps) => {
  const bars = 5;
  const filledBars = Math.round((score / 100) * bars);

  return (
    <div className="flex items-center gap-1.5">
      {Array.from({ length: bars }).map((_, index) => (
        <div
          key={index}
          className={`
            w-1.5 rounded-full transition-all duration-300
            ${index < filledBars 
              ? "bg-primary h-3" 
              : "bg-surface-3 h-2"
            }
          `}
          style={{
            boxShadow: index < filledBars ? "0 0 6px hsl(211 100% 50% / 0.5)" : "none"
          }}
        />
      ))}
      <span className="ml-1 text-xs font-medium text-titanium">{score}</span>
    </div>
  );
};
