export interface PosePoint {
  x: number;
  y: number;
  z?: number;
  visibility?: number;
}

export type SquatPhase =
  | "ready"
  | "descending"
  | "bottom"
  | "ascending";

export interface SquatAnalysis {
  tracked: boolean;
  phase: SquatPhase;
  reps: number;
  kneeAngle: number | null;
  torsoLean: number | null;
  feedback: string;
  side: "left" | "right" | null;
  lastRepWasGood: boolean | null;
}

interface JointSet {
  shoulder: PosePoint;
  hip: PosePoint;
  knee: PosePoint;
  ankle: PosePoint;
}

const LEFT = { shoulder: 11, hip: 23, knee: 25, ankle: 27 } as const;
const RIGHT = { shoulder: 12, hip: 24, knee: 26, ankle: 28 } as const;
const MIN_VISIBILITY = 0.6;

function pointAt(
  landmarks: PosePoint[],
  index: number,
): PosePoint | undefined {
  return landmarks[index];
}

function jointsFor(
  landmarks: PosePoint[],
  indices: typeof LEFT | typeof RIGHT,
): JointSet | null {
  const shoulder = pointAt(landmarks, indices.shoulder);
  const hip = pointAt(landmarks, indices.hip);
  const knee = pointAt(landmarks, indices.knee);
  const ankle = pointAt(landmarks, indices.ankle);
  if (!shoulder || !hip || !knee || !ankle) {
    return null;
  }
  return { shoulder, hip, knee, ankle };
}

function averageVisibility(joints: JointSet | null): number {
  if (!joints) {
    return 0;
  }
  const values = Object.values(joints).map(
    (point) => point.visibility ?? 1,
  );
  return values.reduce((total, value) => total + value, 0) / values.length;
}

function angleAt(
  first: PosePoint,
  vertex: PosePoint,
  third: PosePoint,
  width: number,
  height: number,
): number {
  const firstVector = {
    x: (first.x - vertex.x) * width,
    y: (first.y - vertex.y) * height,
  };
  const thirdVector = {
    x: (third.x - vertex.x) * width,
    y: (third.y - vertex.y) * height,
  };
  const dot =
    firstVector.x * thirdVector.x + firstVector.y * thirdVector.y;
  const firstLength = Math.hypot(firstVector.x, firstVector.y);
  const thirdLength = Math.hypot(thirdVector.x, thirdVector.y);
  if (firstLength === 0 || thirdLength === 0) {
    return 180;
  }
  const cosine = Math.min(
    1,
    Math.max(-1, dot / (firstLength * thirdLength)),
  );
  return (Math.acos(cosine) * 180) / Math.PI;
}

function torsoLean(
  shoulder: PosePoint,
  hip: PosePoint,
  width: number,
  height: number,
): number {
  const horizontal = Math.abs((shoulder.x - hip.x) * width);
  const vertical = Math.abs((shoulder.y - hip.y) * height);
  return (Math.atan2(horizontal, vertical) * 180) / Math.PI;
}

export class SquatAnalyzer {
  private phase: SquatPhase = "ready";
  private reps = 0;
  private minimumKneeAngle = 180;
  private maximumTorsoLean = 0;
  private smoothedKneeAngle: number | null = null;
  private smoothedTorsoLean: number | null = null;
  private lastRepWasGood: boolean | null = null;
  private lastFeedback = "Stand side-on with your full body visible.";

  reset(): void {
    this.phase = "ready";
    this.reps = 0;
    this.minimumKneeAngle = 180;
    this.maximumTorsoLean = 0;
    this.smoothedKneeAngle = null;
    this.smoothedTorsoLean = null;
    this.lastRepWasGood = null;
    this.lastFeedback = "Stand side-on with your full body visible.";
  }

  update(
    landmarks: PosePoint[],
    width: number,
    height: number,
  ): SquatAnalysis {
    const left = jointsFor(landmarks, LEFT);
    const right = jointsFor(landmarks, RIGHT);
    const leftVisibility = averageVisibility(left);
    const rightVisibility = averageVisibility(right);
    const side = leftVisibility >= rightVisibility ? "left" : "right";
    const joints = side === "left" ? left : right;
    const visibility = Math.max(leftVisibility, rightVisibility);

    if (!joints || visibility < MIN_VISIBILITY) {
      this.lastFeedback =
        "Move back until your shoulder, hip, knee and ankle are visible.";
      return this.result(false, null, null, null);
    }

    const measuredKneeAngle = angleAt(
      joints.hip,
      joints.knee,
      joints.ankle,
      width,
      height,
    );
    const measuredTorsoLean = torsoLean(
      joints.shoulder,
      joints.hip,
      width,
      height,
    );
    this.smoothedKneeAngle = this.smooth(
      this.smoothedKneeAngle,
      measuredKneeAngle,
    );
    this.smoothedTorsoLean = this.smooth(
      this.smoothedTorsoLean,
      measuredTorsoLean,
    );

    const kneeAngle = this.smoothedKneeAngle;
    const lean = this.smoothedTorsoLean;
    this.minimumKneeAngle = Math.min(this.minimumKneeAngle, kneeAngle);
    this.maximumTorsoLean = Math.max(this.maximumTorsoLean, lean);

    if (lean > 45 && this.phase !== "ready") {
      this.lastFeedback = "Keep your chest a little more upright.";
    }

    switch (this.phase) {
      case "ready":
        if (kneeAngle < 150) {
          this.phase = "descending";
          this.minimumKneeAngle = kneeAngle;
          this.maximumTorsoLean = lean;
          this.lastFeedback = "Lower under control.";
        } else {
          this.lastFeedback = "Ready. Begin your squat when comfortable.";
        }
        break;
      case "descending":
        if (kneeAngle <= 115) {
          this.phase = "bottom";
          this.lastFeedback = "Good depth. Drive upward smoothly.";
        } else if (kneeAngle >= 160) {
          this.phase = "ready";
          this.lastFeedback = "Try a little more depth on the next rep.";
          this.clearRepMeasurements();
        } else if (lean <= 45) {
          this.lastFeedback = "Lower under control.";
        }
        break;
      case "bottom":
        if (kneeAngle > 125) {
          this.phase = "ascending";
          this.lastFeedback = "Stand up smoothly.";
        }
        break;
      case "ascending":
        if (kneeAngle >= 160) {
          this.reps += 1;
          this.lastRepWasGood =
            this.minimumKneeAngle <= 115 && this.maximumTorsoLean <= 45;
          this.lastFeedback = this.lastRepWasGood
            ? `Rep ${this.reps} complete. Good control.`
            : `Rep ${this.reps} complete. Keep your chest more upright.`;
          this.phase = "ready";
          this.clearRepMeasurements();
        }
        break;
    }

    return this.result(true, kneeAngle, lean, side);
  }

  private smooth(previous: number | null, current: number): number {
    return previous === null ? current : previous * 0.65 + current * 0.35;
  }

  private clearRepMeasurements(): void {
    this.minimumKneeAngle = 180;
    this.maximumTorsoLean = 0;
  }

  private result(
    tracked: boolean,
    kneeAngle: number | null,
    lean: number | null,
    side: "left" | "right" | null,
  ): SquatAnalysis {
    return {
      tracked,
      phase: this.phase,
      reps: this.reps,
      kneeAngle,
      torsoLean: lean,
      feedback: this.lastFeedback,
      side,
      lastRepWasGood: this.lastRepWasGood,
    };
  }
}
