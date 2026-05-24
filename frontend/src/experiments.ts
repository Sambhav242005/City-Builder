export type ExperimentVariant = "control" | "map_focus";

type AssignmentSource = "storage" | "url" | "new";

export type ExperimentAssignment = {
  key: "dashboard-loop-focus";
  variant: ExperimentVariant;
  userId: string;
  source: AssignmentSource;
  assignedAt: string;
};

type ExperimentPayload = Record<string, boolean | number | string | null>;

export type ExperimentEvent = {
  id: string;
  experimentKey: ExperimentAssignment["key"];
  variant: ExperimentVariant;
  name: string;
  timestamp: string;
  payload: ExperimentPayload;
};

const ASSIGNMENT_STORAGE_KEY = "citybuilder.dashboard.experiment.assignment.v1";
const EVENT_STORAGE_KEY = "citybuilder.dashboard.experiment.events.v1";
const USER_STORAGE_KEY = "citybuilder.dashboard.experiment.user.v1";
const EXPERIMENT_KEY = "dashboard-loop-focus";
const VALID_VARIANTS = new Set<ExperimentVariant>(["control", "map_focus"]);
const MAX_STORED_EVENTS = 200;

declare global {
  interface Window {
    cityBuilderExperiments?: {
      assignment: ExperimentAssignment;
      events: () => ExperimentEvent[];
      track: (name: string, payload?: ExperimentPayload) => void;
    };
  }
}

export function resolveExperimentAssignment(): ExperimentAssignment {
  const now = new Date().toISOString();
  const userId = getOrCreateUserId();
  const urlVariant = getUrlVariant();

  if (urlVariant) {
    return persistAssignment({ key: EXPERIMENT_KEY, variant: urlVariant, userId, source: "url", assignedAt: now });
  }

  const storedAssignment = readStoredAssignment();
  if (storedAssignment) {
    return { ...storedAssignment, source: "storage" };
  }

  return persistAssignment({
    key: EXPERIMENT_KEY,
    variant: variantForUser(userId),
    userId,
    source: "new",
    assignedAt: now
  });
}

export function attachExperimentDebugTools(assignment: ExperimentAssignment) {
  window.cityBuilderExperiments = {
    assignment,
    events: readStoredEvents,
    track: (name, payload = {}) => trackExperimentEvent(assignment, name, payload)
  };
}

export function trackExperimentEvent(assignment: ExperimentAssignment, name: string, payload: ExperimentPayload = {}) {
  const event: ExperimentEvent = {
    id: createId(),
    experimentKey: assignment.key,
    variant: assignment.variant,
    name,
    timestamp: new Date().toISOString(),
    payload
  };
  const events = [...readStoredEvents(), event].slice(-MAX_STORED_EVENTS);
  safeLocalStorageSet(EVENT_STORAGE_KEY, JSON.stringify(events));

  if (import.meta.env.DEV) {
    console.debug("[citybuilder:experiment]", event);
  }
}

function getUrlVariant(): ExperimentVariant | null {
  const params = new URLSearchParams(window.location.search);
  const candidate = params.get("ab");
  return isExperimentVariant(candidate) ? candidate : null;
}

function readStoredAssignment(): ExperimentAssignment | null {
  try {
    const raw = safeLocalStorageGet(ASSIGNMENT_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const assignment = JSON.parse(raw) as Partial<ExperimentAssignment>;
    if (
      assignment.key === EXPERIMENT_KEY &&
      isExperimentVariant(assignment.variant) &&
      typeof assignment.userId === "string" &&
      typeof assignment.assignedAt === "string"
    ) {
      return {
        key: EXPERIMENT_KEY,
        variant: assignment.variant,
        userId: assignment.userId,
        assignedAt: assignment.assignedAt,
        source: "storage"
      };
    }
  } catch {
    safeLocalStorageRemove(ASSIGNMENT_STORAGE_KEY);
  }

  return null;
}

function persistAssignment(assignment: ExperimentAssignment) {
  safeLocalStorageSet(ASSIGNMENT_STORAGE_KEY, JSON.stringify(assignment));
  return assignment;
}

function readStoredEvents(): ExperimentEvent[] {
  try {
    const raw = safeLocalStorageGet(EVENT_STORAGE_KEY);
    if (!raw) {
      return [];
    }
    const events = JSON.parse(raw);
    return Array.isArray(events) ? events.slice(-MAX_STORED_EVENTS) : [];
  } catch {
    safeLocalStorageRemove(EVENT_STORAGE_KEY);
    return [];
  }
}

function getOrCreateUserId() {
  const storedId = safeLocalStorageGet(USER_STORAGE_KEY);
  if (storedId) {
    return storedId;
  }

  const userId = createId();
  safeLocalStorageSet(USER_STORAGE_KEY, userId);
  return userId;
}

function variantForUser(userId: string): ExperimentVariant {
  return hashString(userId) % 2 === 0 ? "control" : "map_focus";
}

function hashString(value: string) {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return Math.abs(hash);
}

function isExperimentVariant(value: unknown): value is ExperimentVariant {
  return typeof value === "string" && VALID_VARIANTS.has(value as ExperimentVariant);
}

function createId() {
  return window.crypto?.randomUUID?.() ?? `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

function safeLocalStorageSet(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Local storage can be blocked in some privacy modes; the experiment still works for the current page.
  }
}

function safeLocalStorageGet(key: string) {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeLocalStorageRemove(key: string) {
  try {
    window.localStorage.removeItem(key);
  } catch {
    // Ignore blocked storage cleanup.
  }
}
