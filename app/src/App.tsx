export function App() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="text-center">
        <h1
          className="text-4xl font-semibold"
          style={{ color: "var(--brand-blue)" }}
        >
          运帷 AI · 平台 chat UI · Phase 1 scaffold
        </h1>
        <p className="mt-3 text-sm text-gray-500">
          tenant routing active — Phase 3 wires chat
        </p>
        <p className="mt-8 font-mono text-xs text-gray-400">
          build mode: {import.meta.env.MODE}
        </p>
      </div>
    </div>
  );
}
