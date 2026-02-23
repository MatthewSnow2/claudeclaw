/**
 * Linear project and label conventions for Data <-> Chad coordination.
 *
 * No runtime logic — just constants. Phases 7c-7e will add polling,
 * handoff, and safety logic that references these.
 */

export const COORDINATION = {
  PROJECT_NAME: 'Bot Ops',
  LABELS: { DATA: 'data', CHAD: 'chad' },
  META_ISSUE_PREFIX: '[META]',
  META_ISSUE_IDENTIFIER: 'M2A-122',
} as const;
