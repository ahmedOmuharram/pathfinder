FROM node:24-alpine AS base

# Install dependencies only when needed
FROM base AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app

# Copy package files
COPY apps/web/package*.json ./apps/web/
COPY packages/shared-ts/package*.json ./packages/shared-ts/

# Install dependencies
WORKDIR /app/apps/web
RUN npm ci

# Install shared-ts deps too (Next imports from this path in the image)
WORKDIR /app/packages/shared-ts
RUN npm ci

# Rebuild the source code only when needed
FROM base AS builder
WORKDIR /app

COPY --from=deps /app/apps/web/node_modules ./apps/web/node_modules
COPY --from=deps /app/packages/shared-ts/node_modules ./packages/shared-ts/node_modules
COPY apps/web ./apps/web
COPY packages/shared-ts ./packages/shared-ts

WORKDIR /app/apps/web

# Set environment variables
ENV NEXT_TELEMETRY_DISABLED=1
ENV NODE_ENV=production

# The rewrite destinations in next.config.js are evaluated at build time.
# Inside Docker the API lives at http://api:8000 (Docker DNS), so we inject
# the correct URL as a build arg.  Local (non-Docker) builds keep the default.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

# Production image, copy all the files and run next
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/apps/web/public ./apps/web/public

# Set the correct permission for prerender cache
RUN mkdir -p /app/apps/web/.next
RUN chown nextjs:nodejs /app/apps/web/.next

# Automatically leverage output traces to reduce image size
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/static ./apps/web/.next/static

USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "apps/web/server.js"]

