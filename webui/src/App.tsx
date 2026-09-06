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

