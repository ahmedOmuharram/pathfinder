export type Rgb = readonly [number, number, number];

/** CSS Color Level 4 hsl-to-rgb, each channel in 0..1. */
export function hslToRgb(h: number, s: number, l: number): Rgb {
  const sat = s / 100;
  const light = l / 100;
  const amplitude = sat * Math.min(light, 1 - light);
  const channel = (n: number): number => {
    const k = (n + h / 30) % 12;
    return light - amplitude * Math.max(-1, Math.min(k - 3, 9 - k, 1));
  };
  return [channel(0), channel(8), channel(4)];
}

export function relativeLuminance(c: Rgb): number {
  const channel = (v: number): number =>
    v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  return 0.2126 * channel(c[0]) + 0.7152 * channel(c[1]) + 0.0722 * channel(c[2]);
}

export function contrast(a: Rgb, b: Rgb): number {
  const la = relativeLuminance(a);
  const lb = relativeLuminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

export function composite(fg: Rgb, base: Rgb, alpha: number): Rgb {
  return [
    alpha * fg[0] + (1 - alpha) * base[0],
    alpha * fg[1] + (1 - alpha) * base[1],
    alpha * fg[2] + (1 - alpha) * base[2],
  ];
}
