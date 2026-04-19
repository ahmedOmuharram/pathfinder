/**
 * Central URL builders. Site is now carried in the URL path, so every
 * navigation target needs a site id. Never inline
 * ``/${siteId}/conversation/...`` — always go through a helper here so the
 * path format stays in one place.
 */

export function chatRoot(siteId: string): string {
  return `/${siteId}/conversation`;
}

export function chatUrl(siteId: string, conversationId: string): string {
  return `/${siteId}/conversation/${conversationId}`;
}

export function workbenchRoot(siteId: string): string {
  return `/${siteId}/workbench`;
}

export function workbenchGeneSetUrl(siteId: string, geneSetId: string): string {
  return `/${siteId}/workbench/${geneSetId}`;
}
