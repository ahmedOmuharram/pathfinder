import type { Classification } from "@pathfinder/shared";
import { Badge } from "@/lib/components/ui/Badge";
import type { WdkRecord } from "../../../api";

export const PAGE_SIZE_OPTIONS = [10, 25, 50, 100];

export const CLASSIFICATION_STYLES: Record<
  Classification,
  {
    label: string;
    variant: "success" | "destructive" | "warning" | "default";
    className?: string;
  }
> = {
  TP: { label: "True Positive", variant: "success" },
  FP: { label: "False Positive", variant: "destructive" },
  FN: { label: "False Negative", variant: "warning" },
  TN: {
    label: "True Negative",
    variant: "default",
    className: "bg-blue-500/15 text-blue-600 border-transparent",
  },
};

export function getPrimaryKey(record: WdkRecord): string {
  if (!Array.isArray(record.id) || record.id.length === 0) {
    return String(record.id ?? "unknown");
  }
  return record.id.map((k) => k.value).join("/");
}

export function ClassificationBadge({ value }: { value: Classification | null }) {
  if (!value) return null;
  const style = CLASSIFICATION_STYLES[value];
  return (
    <Badge variant={style.variant} className={style.className}>
      {style.label}
    </Badge>
  );
}

const HTML_TAG_RE = /<[^>]+>/;

function stripHtml(html: string): string {
  const doc = new DOMParser().parseFromString(html, "text/html");
  return doc.body.textContent ?? "";
}

/** Allow only safe inline tags; strip everything else. */
function sanitizeHtml(html: string): string {
  const doc = new DOMParser().parseFromString(html, "text/html");
  const ALLOWED_TAGS = new Set([
    "a",
    "b",
    "i",
    "em",
    "strong",
    "span",
    "br",
    "sub",
    "sup",
  ]);
  function walk(node: Node) {
    const children = Array.from(node.childNodes);
    for (const child of children) {
      if (child.nodeType === Node.ELEMENT_NODE) {
        const el = child as Element;
        if (!ALLOWED_TAGS.has(el.tagName.toLowerCase())) {
          el.replaceWith(...Array.from(el.childNodes));
        } else {
          // Remove event handler attributes
          for (const attr of Array.from(el.attributes)) {
            if (attr.name.startsWith("on") || attr.name === "style") {
              el.removeAttribute(attr.name);
            }
          }
          if (el.tagName === "A") {
            el.setAttribute("target", "_blank");
            el.setAttribute("rel", "noopener noreferrer");
          }
          walk(el);
        }
      }
    }
  }
  walk(doc.body);
  return doc.body.innerHTML;
}

function tryParseJsonLink(raw: string): { text: string; url: string } | null {
  if (!raw.startsWith("{")) return null;
  try {
    const obj = JSON.parse(raw) as Record<string, unknown>;
    const url = obj.url ?? obj.href;
    if (typeof url === "string") {
      const text = typeof obj.displayText === "string" ? obj.displayText : "Link";
      return { text, url };
    }
  } catch {
    /* not JSON */
  }
  return null;
}

export function AttributeValue({ value }: { value: string | null | undefined }) {
  if (value == null) return <span className="text-muted-foreground">—</span>;

  const str = typeof value === "object" ? JSON.stringify(value) : String(value);

  const link = tryParseJsonLink(str);
  if (link) {
    return (
      <a
        href={link.url}
        target="_blank"
        rel="noopener noreferrer"
        onClick={(e) => e.stopPropagation()}
        className="text-primary underline decoration-primary/30 transition hover:decoration-primary"
      >
        {link.text}
      </a>
    );
  }

  if (HTML_TAG_RE.test(str)) return <>{stripHtml(str)}</>;

  return <>{str}</>;
}

export function AttributeValueRich({ value }: { value: unknown }) {
  if (value == null) return <span className="text-muted-foreground">—</span>;

  const str = typeof value === "object" ? JSON.stringify(value) : String(value);

  const link = tryParseJsonLink(str);
  if (link) {
    return (
      <a
        href={link.url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-primary underline decoration-primary/30 transition hover:decoration-primary"
      >
        {link.text}
      </a>
    );
  }

  if (HTML_TAG_RE.test(str)) {
    // sanitizeHtml strips scripts, event handlers, and unsafe tags;
    // only allows a, b, i, em, strong, span, br, sub, sup.
    return (
      <span
        className="[&_a]:text-primary [&_a]:underline"
        dangerouslySetInnerHTML={{ __html: sanitizeHtml(str) }}
      />
    );
  }

  return <>{str}</>;
}
