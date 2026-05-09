// Validator tests для telemetry + feedback (DoS + injection guards).

import { describe, expect, it } from 'vitest';

import {
  isValidFeedback,
  isValidTelemetryBatch,
  type FeedbackSubmission,
  type TelemetryEventBatch
} from '../lib/schema';

describe('TelemetryEventBatch validator', () => {
  it('accepts canonical batch', () => {
    const batch: TelemetryEventBatch = {
      events: [
        {
          event_type: 'forecast_started',
          timestamp: '2026-05-09T12:00:00Z',
          payload: { project_id: 'p' }
        }
      ]
    };
    expect(isValidTelemetryBatch(batch)).toBe(true);
  });

  it('rejects empty events array', () => {
    expect(isValidTelemetryBatch({ events: [] })).toBe(false);
  });

  it('rejects oversized batch (DoS guard)', () => {
    const events = Array.from({ length: 600 }, (_, i) => ({
      event_type: 'spam',
      timestamp: '2026-05-09T12:00:00Z',
      payload: { i }
    }));
    expect(isValidTelemetryBatch({ events })).toBe(false);
  });

  it('rejects oversized event_type string', () => {
    expect(
      isValidTelemetryBatch({
        events: [
          {
            event_type: 'x'.repeat(200),
            timestamp: '2026-05-09T12:00:00Z',
            payload: {}
          }
        ]
      })
    ).toBe(false);
  });
});

describe('FeedbackSubmission validator', () => {
  it('accepts minimal feedback', () => {
    const fb: FeedbackSubmission = { text: 'Hello, found a bug' };
    expect(isValidFeedback(fb)).toBe(true);
  });

  it('rejects empty text', () => {
    expect(isValidFeedback({ text: '' })).toBe(false);
  });

  it('rejects oversized text (DoS guard)', () => {
    expect(isValidFeedback({ text: 'x'.repeat(10_000) })).toBe(false);
  });

  it('rejects oversized screenshot (5 MB cap)', () => {
    expect(
      isValidFeedback({
        text: 'ok',
        screenshot_base64: 'A'.repeat(6_000_000)
      })
    ).toBe(false);
  });

  it('rejects oversized log excerpt (32 KB cap)', () => {
    expect(
      isValidFeedback({
        text: 'ok',
        log_excerpt: 'x'.repeat(50_000)
      })
    ).toBe(false);
  });
});
