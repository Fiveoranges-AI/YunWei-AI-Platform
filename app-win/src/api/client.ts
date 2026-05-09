// Backend API client for /win/api/.
// Falls back to MOCK data when backend is unreachable (useful for local dev
// before WP1/WP2 are wired up).

import { MOCK_ASK_SEED, MOCK_CUSTOMERS, MOCK_REVIEW } from "../data/mock";
import type { AskSeed, CustomerDetail, Review } from "../data/types";

const API_BASE = "/win/api";
const MOCK_DELAY_MS = 200;

async function fetchOrMock<T>(path: string, fallback: T): Promise<T> {
  try {
    const res = await fetch(`${API_BASE}${path}`, { credentials: "include" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as T;
  } catch {
    await new Promise((r) => setTimeout(r, MOCK_DELAY_MS));
    return fallback;
  }
}

export async function listCustomers(): Promise<CustomerDetail[]> {
  return fetchOrMock("/customers", MOCK_CUSTOMERS);
}

export async function getCustomer(id: string): Promise<CustomerDetail | undefined> {
  const fallback = MOCK_CUSTOMERS.find((c) => c.id === id);
  return fetchOrMock(`/customers/${id}`, fallback as CustomerDetail);
}

export async function getReview(_uploadId: string): Promise<Review> {
  return fetchOrMock("/review/last", MOCK_REVIEW);
}

export async function getAskSeed(customerId: string): Promise<AskSeed> {
  return fetchOrMock(`/customers/${customerId}/ask/seed`, MOCK_ASK_SEED);
}
