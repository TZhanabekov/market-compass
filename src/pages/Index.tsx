import { useState } from "react";
import { Header } from "@/components/Header";
import { HeroSection } from "@/components/HeroSection";
import { ModelSelector } from "@/components/ModelSelector";
import { Leaderboard } from "@/components/Leaderboard";
import { RiskSlider } from "@/components/RiskSlider";

const Index = () => {
  const [selectedModel, setSelectedModel] = useState("16pro");
  const [minTrust, setMinTrust] = useState(80);

  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main className="max-w-3xl mx-auto">
        <HeroSection />
        <ModelSelector 
          selectedModel={selectedModel} 
          onSelectModel={setSelectedModel} 
        />
        <Leaderboard minTrust={minTrust} />
      </main>
      <RiskSlider value={minTrust} onChange={setMinTrust} />
    </div>
  );
};

export default Index;
