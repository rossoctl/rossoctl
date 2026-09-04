// Copyright 2025 IBM Corp.
// Licensed under the Apache License, Version 2.0

/**
 * Decide whether the build-progress pages should auto-trigger the finalize
 * (workload-creation) step.
 *
 * Fires exactly once per build: only when the BuildRun has succeeded, finalize
 * has not already been attempted, and no finalize request is in flight. The
 * `hasAutoFinalized` guard is what stops the retrigger loop from issue #2489 --
 * on a finalize failure (e.g. the agent-label-protection 403) the phase stays
 * "Succeeded", so without this the effect would re-fire on every poll tick,
 * hammering the backend and preventing the error Alert from stabilizing. Once
 * attempted, auto-finalize stays off; the user re-runs it via the Retry button.
 */
export function shouldAutoFinalize(args: {
  phase?: string;
  hasAutoFinalized: boolean;
  isPending: boolean;
}): boolean {
  return args.phase === 'Succeeded' && !args.hasAutoFinalized && !args.isPending;
}
