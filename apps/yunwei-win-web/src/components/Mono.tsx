type Props = {
  text: string;
  color?: string;
  size?: number;
  radius?: number;
  fontSize?: number;
};

export function Mono({ text, color = "#1f6c8a", size = 44, radius = 12, fontSize }: Props) {
  const fs = fontSize ?? (text.length > 2 ? 14 : 16);
  return (
    <div
      className="mono"
      style={{
        width: size,
        height: size,
        borderRadius: radius,
        background: color,
        fontSize: fs,
        letterSpacing: "0.02em",
      }}
    >
      {text}
    </div>
  );
}
