import type { BuildingType, StateResponse } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000";

export class ApiRequestError extends Error {
  retryAfterSeconds?: number;
  status: number;

  constructor(message: string, status: number, retryAfterSeconds?: number) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);

  if (!response.ok) {
    let detail = `API request failed: ${response.status}`;
    let retryAfterSeconds: number | undefined;
    try {
      const body = (await response.json()) as {
        detail?: string | { message?: string; retryAfterSeconds?: number };
      };
      if (typeof body.detail === "string") {
        detail = body.detail;
      } else if (body.detail) {
        detail = body.detail.message ?? detail;
        retryAfterSeconds = body.detail.retryAfterSeconds;
      }
    } catch {
      // Keep the status-based message when the response is not JSON.
    }
    throw new ApiRequestError(detail, response.status, retryAfterSeconds);
  }

  return response.json();
}

async function request(path: string, method = "GET"): Promise<StateResponse> {
  return requestJson<StateResponse>(path, { method });
}

export function fetchState(): Promise<StateResponse> {
  return request("/state");
}

export function tick(): Promise<StateResponse> {
  return request("/tick", "POST");
}

export function reset(): Promise<StateResponse> {
  return request("/reset", "POST");
}

export function approveGovernmentAction(): Promise<StateResponse> {
  return request("/government/approve", "POST");
}

export function rejectGovernmentAction(): Promise<StateResponse> {
  return request("/government/reject", "POST");
}

export function buildStructure(buildingType: BuildingType): Promise<StateResponse> {
  return requestJson<StateResponse>("/build", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ buildingType })
  });
}

export function liveUrl(): string {
  const url = new URL(API_BASE);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/live";
  return url.toString();
}
