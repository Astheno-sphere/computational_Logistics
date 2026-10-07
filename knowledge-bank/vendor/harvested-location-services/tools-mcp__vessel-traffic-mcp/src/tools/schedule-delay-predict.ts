import { z } from 'zod/v4';

import type { ScheduleDelayPredictionResult, SourceMetadata } from '../providers/types.js';
import { nowIso } from './vessel-routing.js';

export const scheduleDelayPredictInputSchema = z
  .object({
    plannedArrivalAt: z.iso.datetime().optional(),
    estimatedArrivalAt: z.iso.datetime().optional(),
    actualArrivalAt: z.iso.datetime().optional(),
    plannedDepartureAt: z.iso.datetime().optional(),
    actualDepartureAt: z.iso.datetime().optional(),
    currentPositionObservedAt: z.iso.datetime().optional(),
    now: z.iso.datetime().optional(),
  })
  .superRefine((data, ctx) => {
    if (!data.plannedArrivalAt) {
      ctx.addIssue({
        code: 'custom',
        path: ['plannedArrivalAt'],
        message: 'schedule_delay_predict requires plannedArrivalAt.',
      });
    }
    if (data.plannedDepartureAt && data.actualDepartureAt) {
      const planned = Date.parse(data.plannedDepartureAt);
      const actual = Date.parse(data.actualDepartureAt);
      if (Number.isFinite(planned) && Number.isFinite(actual) && actual < planned - 24 * 60 * 60 * 1000) {
        ctx.addIssue({
          code: 'custom',
          path: ['actualDepartureAt'],
          message: 'actualDepartureAt is more than 24 hours before plannedDepartureAt; check the schedule fields.',
        });
      }
    }
  });

export type ScheduleDelayPredictInput = z.infer<typeof scheduleDelayPredictInputSchema>;

const SOURCE: SourceMetadata = {
  provider: 'schedule-delay-predict',
  adapterVersion: 'schedule-delay-predict-0.1.0',
  transport: 'derived',
  coverage: 'Derived from supplied carrier schedule timestamps; no external provider call is made.',
  confidence: 'medium',
  termsNote: 'Derived calculation only. Preserve upstream schedule source attribution in adjacent tool output.',
};

function hoursBetween(laterIso: string, earlierIso: string): number {
  return (Date.parse(laterIso) - Date.parse(earlierIso)) / (60 * 60 * 1000);
}

function statusFromDelayHours(delayHours: number): ScheduleDelayPredictionResult['status'] {
  if (!Number.isFinite(delayHours)) return 'unknown';
  if (delayHours >= 6) return 'delayed';
  if (delayHours >= 2) return 'at_risk';
  return 'on_time';
}

export async function scheduleDelayPredict(
  input: ScheduleDelayPredictInput,
): Promise<Record<string, unknown>> {
  const evaluatedAt = input.now ?? nowIso();
  const basis: string[] = [];
  const comparisonAt = input.actualArrivalAt ?? input.estimatedArrivalAt;
  const plannedArrivalAt = input.plannedArrivalAt;

  if (!plannedArrivalAt) {
    return {
      ok: false,
      reason: 'unsupported_query',
      message: 'schedule_delay_predict requires plannedArrivalAt.',
      retrievedAt: evaluatedAt,
      source: SOURCE,
      caveats: ['Delay prediction is heuristic and must be paired with the original source URL.'],
    };
  }

  if (!comparisonAt) {
    return {
      ok: true,
      data: {
        status: 'unknown',
        confidence: 'unknown',
        basis: ['No estimatedArrivalAt or actualArrivalAt supplied; cannot compare against planned arrival.'],
        evaluatedAt,
      },
      retrievedAt: evaluatedAt,
      source: SOURCE,
      caveats: ['Delay prediction is heuristic and must be paired with the original source URL.'],
    };
  }

  const delayHours = Math.round(hoursBetween(comparisonAt, plannedArrivalAt) * 10) / 10;
  basis.push(
    input.actualArrivalAt
      ? `actualArrivalAt differs from plannedArrivalAt by ${delayHours} hours.`
      : `estimatedArrivalAt differs from plannedArrivalAt by ${delayHours} hours.`,
  );

  let confidence: ScheduleDelayPredictionResult['confidence'] = input.actualArrivalAt ? 'high' : 'medium';
  if (input.plannedDepartureAt && input.actualDepartureAt) {
    const departureDelayHours =
      Math.round(hoursBetween(input.actualDepartureAt, input.plannedDepartureAt) * 10) / 10;
    basis.push(`departure variance is ${departureDelayHours} hours.`);
    if (departureDelayHours >= 6 && delayHours < 2) {
      confidence = 'low';
      basis.push('Arrival estimate does not reflect a large departure variance; prediction confidence lowered.');
    }
  }

  if (input.currentPositionObservedAt) {
    const staleHours = Math.round(hoursBetween(evaluatedAt, input.currentPositionObservedAt) * 10) / 10;
    basis.push(`latest position observation is ${staleHours} hours old.`);
    if (staleHours > 24 && confidence === 'medium') confidence = 'low';
  }

  const data: ScheduleDelayPredictionResult = {
    status: statusFromDelayHours(delayHours),
    delayHours,
    confidence,
    basis,
    evaluatedAt,
  };

  return {
    ok: true,
    data,
    retrievedAt: evaluatedAt,
    source: SOURCE,
    caveats: ['Delay prediction is heuristic and must be paired with the original source URL.'],
  };
}
