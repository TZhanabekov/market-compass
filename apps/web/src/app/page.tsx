"use client";

import { useState, useRef } from "react";
import { Header } from "@/components/Header";
import { HeroSection } from "@/components/HeroSection";
import { ModelSelector } from "@/components/ModelSelector";
import { CompareCard } from "@/components/CompareCard";
import { Leaderboard } from "@/components/Leaderboard";
import { RiskSlider } from "@/components/RiskSlider";
import { ComparisonModal } from "@/components/ComparisonModal";
import { useHomeData } from "@/lib/hooks";

export default function Home() {
  const [selectedModel, setSelectedModel] = useState("16pro");
  const [minTrust, setMinTrust] = useState(80);
  const [isCompareModalOpen, setIsCompareModalOpen] = useState(false);
  const leaderboardRef = useRef<HTMLDivElement>(null);

  // Map model to SKU (simplified - in production this would be more sophisticated)
  const skuMap: Record<string, string> = {
    "16pro": "iphone-16-pro-256gb-black-new",
    "16promax": "iphone-16-pro-max-256gb-black-new",
  };

  const { data, isLoading, error } = useHomeData({
    sku: skuMap[selectedModel] || skuMap["16pro"],
    home: "DE",
    minTrust,
    lang: "en",
  });

  const bestDeal = data?.leaderboard.deals[0];

  const handleViewDeal = () => {
    setIsCompareModalOpen(false);
    // Scroll to leaderboard after modal closes
    setTimeout(() => {
      leaderboardRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 300);
  };

  return (
    <div className="min-h-screen bg-background">
      <Header homeMarket={data?.homeMarket} />
      <main className="max-w-3xl mx-auto">
        <HeroSection />
        <ModelSelector 
          selectedModel={selectedModel} 
          onSelectModel={setSelectedModel} 
        />
        {data && (
          <>
            <CompareCard 
              onCompareClick={() => setIsCompareModalOpen(true)} 
              homeMarket={data.homeMarket}
              bestDeal={bestDeal}
            />
            <div ref={leaderboardRef}>
              <Leaderboard 
                minTrust={minTrust}
                deals={data.leaderboard.deals}
                matchCount={data.leaderboard.matchCount}
                homeMarket={data.homeMarket}
                isLoading={isLoading}
                error={error}
              />
            </div>
          </>
        )}
        {isLoading && (
          <div className="px-4 py-12 text-center">
            <p className="text-titanium">Loading deals...</p>
          </div>
        )}
        {error && (
          <div className="px-4 py-12 text-center">
            <p className="text-warning">Failed to load deals. Please try again later.</p>
          </div>
        )}
      </main>
      <RiskSlider value={minTrust} onChange={setMinTrust} />
      
      {/* Comparison Modal */}
      {bestDeal && data && (
        <ComparisonModal
          isOpen={isCompareModalOpen}
          onClose={() => setIsCompareModalOpen(false)}
          deal={bestDeal}
          homeMarket={data.homeMarket}
          onViewDeal={handleViewDeal}
        />
      )}
    </div>
  );
}
