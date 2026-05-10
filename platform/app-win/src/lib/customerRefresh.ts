const CUSTOMER_REFRESH_EVENT = "win:customers-changed";

let revision = 0;

export function markCustomersChanged(): void {
  revision += 1;
  window.dispatchEvent(new CustomEvent(CUSTOMER_REFRESH_EVENT, { detail: { revision } }));
}

export function onCustomersChanged(listener: () => void): () => void {
  const handler = () => listener();
  window.addEventListener(CUSTOMER_REFRESH_EVENT, handler);
  return () => window.removeEventListener(CUSTOMER_REFRESH_EVENT, handler);
}
