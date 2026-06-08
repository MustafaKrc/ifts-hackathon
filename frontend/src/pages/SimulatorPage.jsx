import React from "react";
import { useOutletContext } from "react-router-dom";

import SprintScenarioSimulator from "../components/SprintScenarioSimulator";

export default function SimulatorPage() {
  const ctx = useOutletContext();
  return (
    <SprintScenarioSimulator
      simulation={ctx.simulation}
      onSimulate={ctx.handleSimulate}
      canSimulate={ctx.selectedKeys.length > 0}
      loading={ctx.loading.simulate}
    />
  );
}
