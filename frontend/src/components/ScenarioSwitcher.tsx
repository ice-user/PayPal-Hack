import { Scenario } from "../types/api";

export function ScenarioSwitcher({
  scenario,
  onChange,
}: {
  scenario: Scenario;
  onChange: (s: Scenario) => void;
}) {
  const scenarios: { value: Scenario; label: string }[] = [
    { value: "one_carrier_delays", label: "One Carrier Delays" },
    { value: "many_carriers_delays", label: "Many Carriers Delays" },
    { value: "delivered_orders", label: "Delivered Orders" },
  ];

  return (
    <select value={scenario} onChange={(e) => onChange(e.target.value as Scenario)} className="scenario-select">
      {scenarios.map((s) => (
        <option key={s.value} value={s.value}>
          {s.label}
        </option>
      ))}
    </select>
  );
}