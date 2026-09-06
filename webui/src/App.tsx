import { useState } from "react";
import { api } from "./api/client";
import { Layout, RailKey } from "./components/Layout";
import { BindingWorkbench } from "./components/BindingWorkbench";
import { BOQTable } from "./components/BOQTable";
import { MeasurementPanel } from "./components/MeasurementPanel";
import { EntityProperties } from "./components/EntityProperties";
import { HistoryPanel } from "./components/HistoryPanel";
import { Canvas2D } from "./components/Canvas2D";
import { theme } from "./theme";

export default function App() {
  const [activeRail, setActiveRail] = useState<RailKey>("binding");

  useEffect(() => {
    api.health().then(setHealth);
  }, []);

  const PANELS: Record<RailKey, React.ReactNode> = {
    binding: <BindingWorkbench />,
    boq: <BOQTable />,
    measure: <MeasurementPanel />,
    properties: <EntityProperties />,
    history: <HistoryPanel />,
  };

  return (
    <Layout
      activeRail={activeRail}
      onRailChange={setActiveRail}
      theme={theme}
      statusBar={
        <div>
          <div style={{ color: "var(--text-primary)", fontWeight: 600, marginBottom: 8, fontSize: 14 }}>
            {activeRail === "binding" && "🔗 绑定工作台"}
            {activeRail === "boq" && "📋 BOQ 清单"}
            {activeRail === "measure" && "📐 计量"}
            {activeRail === "properties" && "🏷️ 实体属性"}
            {activeRail === "history" && "🕘 操作记录"}
          </div>
          {PANELS[activeRail]}
        </div>
      }
    >
      <Canvas2D />
    </Layout>
  );
}
