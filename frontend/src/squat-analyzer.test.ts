import { describe, expect, it } from "vitest";

import { SquatAnalyzer, type PosePoint } from "./squat-analyzer";

function poseAtKneeAngle(
  kneeAngle: number,
  visibility = 1,
): PosePoint[] {
  const points = Array.from({ length: 33 }, () => ({
    x: 0,
    y: 0,
    visibility: 0,
  }));
  const knee = { x: 0.55, y: 0.65, visibility };
  const radians = ((90 + kneeAngle) * Math.PI) / 180;
  const hip = {
    x: knee.x + Math.cos(radians) * 0.25,
    y: knee.y + Math.sin(radians) * 0.25,
    visibility,
  };
  const ankle = { x: knee.x, y: knee.y + 0.25, visibility };
  const shoulder = { x: hip.x, y: hip.y - 0.25, visibility };

  points[11] = shoulder;
  points[23] = hip;
  points[25] = knee;
  points[27] = ankle;
  return points;
}

function updateRepeatedly(
  analyzer: SquatAnalyzer,
  kneeAngle: number,
  count = 10,
) {
  let analysis = analyzer.update(poseAtKneeAngle(kneeAngle), 1000, 1000);
  for (let index = 1; index < count; index += 1) {
    analysis = analyzer.update(poseAtKneeAngle(kneeAngle), 1000, 1000);
  }
  return analysis;
}

describe("SquatAnalyzer", () => {
  it("counts a complete squat after reaching depth", () => {
    const analyzer = new SquatAnalyzer();

    updateRepeatedly(analyzer, 175);
    updateRepeatedly(analyzer, 140);
    updateRepeatedly(analyzer, 100);
    updateRepeatedly(analyzer, 135);
    const result = updateRepeatedly(analyzer, 175);

    expect(result.reps).toBe(1);
    expect(result.phase).toBe("ready");
    expect(result.lastRepWasGood).toBe(true);
  });

  it("does not count a shallow movement", () => {
    const analyzer = new SquatAnalyzer();

    updateRepeatedly(analyzer, 175);
    updateRepeatedly(analyzer, 140);
    const result = updateRepeatedly(analyzer, 175);

    expect(result.reps).toBe(0);
    expect(result.feedback).toContain("depth");
  });

  it("refuses to evaluate low-confidence landmarks", () => {
    const analyzer = new SquatAnalyzer();

    const result = analyzer.update(poseAtKneeAngle(100, 0.2), 1000, 1000);

    expect(result.tracked).toBe(false);
    expect(result.kneeAngle).toBeNull();
    expect(result.feedback).toContain("visible");
  });
});
