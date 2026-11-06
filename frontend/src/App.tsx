import { useState, useEffect } from "react";
import { SituationPanel } from "./components/SituationPanel";
import { PrecedentsPanel } from "./components/PrecedentsPanel";
import { PlanPanel } from "./components/PlanPanel";
import { TimelinePanel } from "./components/TimelinePanel";
import { ScenarioSwitcher } from "./components/ScenarioSwitcher";
import { AbstainBanner } from "./components/AbstainBanner";
import { LoadingState } from "./components/LoadingState";
import { ErrorState } from "./components/ErrorState";
import { loadScenario, getSituation, getRecommendation, getTimeline, healthCheck } from "./api/client";
import type { SituationRecord, Recommendation, MerchantTimeline, Scenario } from "./types/api";
import "./App.css";

function App() {
  const [merchantId, setMerchantId] = useState("demo-merchant-1");
  const [scenario, setScenario] = useState<Scenario>("one_carrier_delays");
  const [situation, setSituation] = useState<SituationRecord | null>(null);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [timeline, setTimeline] = useState<MerchantTimeline | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showWithoutPrecedent, setShowWithoutPrecedent] = useState(false);
  const [situationId, setSituationId] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      // Load scenario (creates situation)
      const scenarioResp = await loadScenario(merchantId, scenario);
      setSituationId(scenarioResp.situation_id);
      setSituation(scenarioResp.situation);

      // Get recommendation
      const rec = await getRecommendation(scenarioResp.situation_id);
      setRecommendation(rec);

      // Get timeline
      const tl = await getTimeline(merchantId);
      setTimeline(tl);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [scenario]);

  const handleScenarioChange = (newScenario: Scenario) => {
    setScenario(newScenario);
    setShowWithoutPrecedent(false);
  };

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={loadData} />;
  if (!situation || !recommendation) return <LoadingState />;

  return (
    <div className="app">
      <header className="app-header">
        <h1>Precedent — PayPal Dispute Intelligence</h1>
        <ScenarioSwitcher scenario={scenario} onChange={handleScenarioChange} />
      </header>

      {recommendation.abstain && (
        <AbstainBanner reason={recommendation.abstain_reason || "Insufficient evidence"} />
      )}

      <main className="app-main">
        <div className="three-columns">
          <SituationPanel situation={situation} />
          <PrecedentsPanel
            precedents={recommendation.precedents}
            showWithoutPrecedent={showWithoutPrecedent}
            onToggleWithoutPrecedent={setShowWithoutPrecedent}
          />
          <PlanPanel
            recommendation={recommendation}
            onApprove={() => {}}
            onReject={() => {}}
          />
        </div>
        <TimelinePanel timeline={timeline} />
      </main>

      <footer className="app-footer">
        <small>
          Demo scenario: {scenario} | All simulated elements labelled "simulated" | 
          No causal claims — every recommendation cites precedents with provenance
        </small>
      </footer>
    </div>
  );
}

export default App;