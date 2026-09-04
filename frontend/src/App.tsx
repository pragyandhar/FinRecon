import { useState } from "react";
import { UploadScreen } from "./components/UploadScreen";
import { ProcessingScreen } from "./components/ProcessingScreen";
import { Dashboard } from "./components/Dashboard";

type Screen =
  | { kind: "upload" }
  | { kind: "processing"; jobId: string }
  | { kind: "dashboard"; jobId: string };

export default function App() {
  const [screen, setScreen] = useState<Screen>({ kind: "upload" });

  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>FinRecon</h1>
          <div className="subtitle">Financial reconciliation, understood and executed end to end</div>
        </div>
      </header>

      {screen.kind === "upload" && (
        <UploadScreen onJobCreated={(jobId) => setScreen({ kind: "processing", jobId })} />
      )}

      {screen.kind === "processing" && (
        <ProcessingScreen
          jobId={screen.jobId}
          onComplete={() => setScreen({ kind: "dashboard", jobId: screen.jobId })}
          onRestart={() => setScreen({ kind: "upload" })}
        />
      )}

      {screen.kind === "dashboard" && (
        <Dashboard jobId={screen.jobId} onRestart={() => setScreen({ kind: "upload" })} />
      )}
    </div>
  );
}
