const LATEX_COMMAND_PATTERN =
  /\\(frac|text|sum|int|prod|sqrt|lim|cdot|times|div|log|ln|sin|cos|tan|alpha|beta|gamma|delta|epsilon|theta|lambda|mu|pi|sigma|phi|omega|mathbb|mathcal|mathrm|mathbf|infty|partial|nabla|cap|cup|in|notin|subset|supset|leq|geq|neq|approx|equiv|rightarrow|leftarrow|leftrightarrow)/;

export function normalizeLatex(text: string): string {
  if (text.length === 0) return text;

  let out = text.replace(/\\\[([\s\S]+?)\\\]/g, (_, inner: string) => `$$${inner}$$`);
  out = out.replace(/\\\(([\s\S]+?)\\\)/g, (_, inner: string) => `$${inner}$`);

  out = out.replace(
    /(^|[^\]\\])\[\s*([^\[\]]+?)\s*\](?!\()/g,
    (match, prefix: string, inner: string) => {
      if (!LATEX_COMMAND_PATTERN.test(inner)) return match;
      return `${prefix}$$${inner}$$`;
    },
  );

  out = out.replace(
    /(^|[^(\\])\(\s*([^()]+?)\s*\)/g,
    (match, prefix: string, inner: string) => {
      if (!LATEX_COMMAND_PATTERN.test(inner)) return match;
      return `${prefix}$${inner}$`;
    },
  );

  return out;
}
