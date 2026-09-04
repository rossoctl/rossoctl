// Copyright 2025 IBM Corp.
// Licensed under the Apache License, Version 2.0

import { describe, it, expect } from 'vitest';
import { shouldAutoFinalize } from './buildFinalize';

describe('shouldAutoFinalize', () => {
  it('fires once when the build has succeeded and finalize has not been attempted', () => {
    expect(
      shouldAutoFinalize({ phase: 'Succeeded', hasAutoFinalized: false, isPending: false }),
    ).toBe(true);
  });

  it('does NOT re-fire after finalize was already attempted (issue #2489: no retrigger loop)', () => {
    // On a finalize error the phase stays "Succeeded"; without this guard the
    // effect would re-fire every poll tick, hammering the backend and hiding
    // the error Alert. Once attempted, it must stay off.
    expect(
      shouldAutoFinalize({ phase: 'Succeeded', hasAutoFinalized: true, isPending: false }),
    ).toBe(false);
  });

  it('does not fire while a finalize request is already in flight', () => {
    expect(
      shouldAutoFinalize({ phase: 'Succeeded', hasAutoFinalized: false, isPending: true }),
    ).toBe(false);
  });

  it('does not fire for non-succeeded phases', () => {
    for (const phase of ['Running', 'Failed', 'Pending', undefined]) {
      expect(
        shouldAutoFinalize({ phase, hasAutoFinalized: false, isPending: false }),
      ).toBe(false);
    }
  });
});
