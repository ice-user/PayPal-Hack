export function AbstainBanner({ reason }: { reason: string }) {
  return (
    <div className="abstain-banner" role="alert">
      <span className="abstain-icon">⚠️</span>
      <div>
        <strong>System Abstains:</strong> {reason}
      </div>
    </div>
  );
}