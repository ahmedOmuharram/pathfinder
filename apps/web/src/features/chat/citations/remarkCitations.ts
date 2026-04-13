/**
 * Remark plugin that rewrites `[@sourceId]` tokens in text nodes into numbered
 * citation links.
 *
 * Usage: pass the output of `createCitationRemarkPlugin(index)` into
 * `Streamdown`'s `remarkPlugins` prop. The plugin walks text nodes via
 * `mdast-util-find-and-replace`; each match is replaced with a link node
 * that points at `#cite-{N}` on the host page. Unmatched tags (e.g. a
 * `[@unknown]` whose sourceId is not in the index) are left untouched so the
 * raw text survives.
 *
 * The matched number is carried in both the link text (`[N]`) and a
 * `data-citation-number` attribute, which lets CSS style it as a superscript
 * without producing a different mdast node shape.
 */

import type { Root } from "mdast";
import { findAndReplace } from "mdast-util-find-and-replace";
import type { Plugin } from "unified";

import type { CitationIndex } from "./types";

const CITATION_TOKEN_REGEX = /\[@([A-Za-z0-9_-]+)\]/g;

export function createCitationRemarkPlugin(
  index: CitationIndex,
): Plugin<[], Root> {
  return function remarkCitations() {
    return (tree: Root): undefined => {
      findAndReplace(tree, [
        [
          CITATION_TOKEN_REGEX,
          (_match: string, tag: string) => {
            const number = index.bySourceId.get(tag);
            if (number === undefined) return false;
            return {
              type: "link",
              url: `#cite-${String(number)}`,
              data: {
                hProperties: {
                  className: "citation-link",
                  "data-citation-number": String(number),
                },
              },
              children: [{ type: "text", value: `[${String(number)}]` }],
            };
          },
        ],
      ]);
      return undefined;
    };
  };
}
