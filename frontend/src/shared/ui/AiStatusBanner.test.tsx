import "@testing-library/jest-dom/vitest";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { AiStatusBanner } from "./AiStatusBanner";
import { toRules } from "../../features/datasets/api";
import { MSG_AI_OFF } from "../constants/messages";

describe("AiStatusBanner (Level 3 B2: AI failures are never silent)", () => {
  it("explains that AI is off when no model is configured", () => {
    render(<AiStatusBanner status="off" />);
    expect(screen.getByRole("status")).toHaveTextContent(MSG_AI_OFF);
  });

  it("shows the failure reason", () => {
    render(<AiStatusBanner status="failed" message="AI suggestions unavailable (timeout)" />);
    expect(screen.getByRole("status")).toHaveTextContent("timeout");
  });

  it("renders nothing when AI suggestions were used without issues", () => {
    const { container } = render(<AiStatusBanner status="used" />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("toRules", () => {
  it("unwraps the API's items and keeps the source", () => {
    const rules = toRules({
      datasetId: "d1",
      items: [
        {
          id: "r1",
          ruleType: "entity_group",
          columns: ["supplier"],
          expression: {},
          confidence: 0.9,
          evidence: { variants: 7 },
          source: "llm",
        },
      ],
    });
    expect(rules).toHaveLength(1);
    expect(rules[0]).toMatchObject({ datasetId: "d1", source: "llm", evidenceRows: [{ variants: 7 }] });
  });
});
