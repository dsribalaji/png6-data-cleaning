import React from "react";
import { Routes, Route } from "react-router-dom";
import { Layout } from "./components/Layout";
import { Datasets } from "./pages/Datasets";
import { DatasetDetail } from "./pages/DatasetDetail";
import { Profile } from "./pages/Profile";
import { PlanReview } from "./pages/PlanReview";
import { Execute } from "./pages/Execute";
import { Tests } from "./pages/Tests";
import { Quarantine } from "./pages/Quarantine";
import { Audit } from "./pages/Audit";
import { ModelSettings } from "./pages/ModelSettings";

export default function App(): React.ReactElement {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<Datasets />} />
        <Route path="datasets/:id" element={<DatasetDetail />} />
        <Route path="datasets/:id/profile" element={<Profile />} />
        <Route path="datasets/:id/plan" element={<PlanReview />} />
        <Route path="datasets/:id/execute" element={<Execute />} />
        <Route path="datasets/:id/tests" element={<Tests />} />
        <Route path="datasets/:id/quarantine" element={<Quarantine />} />
        <Route path="audit" element={<Audit />} />
        <Route path="settings/model" element={<ModelSettings />} />
      </Route>
    </Routes>
  );
}
