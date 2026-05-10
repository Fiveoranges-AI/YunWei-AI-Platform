import type { ReactNode } from "react";

type Props = {
  title: string;
  count?: number;
  trailing?: ReactNode;
  children: ReactNode;
};

export function Section({ title, count, trailing, children }: Props) {
  return (
    <div style={{ marginBottom: 18 }}>
      <div className="sec-h" style={{ paddingLeft: 4 }}>
        <h3>
          {title}
          {count !== undefined && (
            <span style={{ marginLeft: 6, fontSize: 11, color: "var(--ink-400)", fontWeight: 500 }}>
              {count}
            </span>
          )}
        </h3>
        {trailing}
      </div>
      {children}
    </div>
  );
}
