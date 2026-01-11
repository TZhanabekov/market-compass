import { useState, useRef } from "react";
import { Header } from "@/components/Header";
import { HeroSection } from "@/components/HeroSection";
import { ModelSelector } from "@/components/ModelSelector";
import { CompareCard } from "@/components/CompareCard";
import { Leaderboard } from "@/components/Leaderboard";
import { RiskSlider } from "@/components/RiskSlider";
import { ComparisonModal } from "@/components/ComparisonModal";
import { MOCK_DEALS } from "@/data/mockData";

const Index = () => {
  const [selectedModel, setSelectedModel] = useState("16pro");
  const [minTrust, setMinTrust] = useState(80);
  const [isCompareModalOpen, setIsCompareModalOpen] = useState(false);
  const leaderboardRef = useRef<HTMLDivElement>(null);

  const bestDeal = MOCK_DEALS[0];

  const handleViewDeal = () => {
    setIsCompareModalOpen(false);
    // Scroll to leaderboard after modal closes
    setTimeout(() => {
      leaderboardRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 300);
  };

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="max-w-3xl mx-auto">
        <HeroSection />
        <ModelSelector 
          selectedModel={selectedModel} 
          onSelectModel={setSelectedModel} 
        />
        <CompareCard onCompareClick={() => setIsCompareModalOpen(true)} />
        <div ref={leaderboardRef}>
          <Leaderboard minTrust={minTrust} />
        </div>
      </main>
      <RiskSlider value={minTrust} onChange={setMinTrust} />
      
      {/* Comparison Modal */}
      <ComparisonModal
        isOpen={isCompareModalOpen}
        onClose={() => setIsCompareModalOpen(false)}
        deal={bestDeal}
        onViewDeal={handleViewDeal}
      />
    </div>
  );
};

export default Index;
