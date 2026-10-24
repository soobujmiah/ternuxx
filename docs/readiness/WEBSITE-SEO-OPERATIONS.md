# Ternuxx website, SEO, portfolio and release operations

**Reviewed:** 2026-10-17. Website build, account creation, domain purchase and deployment are not authorized or performed.

> **Planning snapshot, not active scope.** No website work was authorized. Ternuxx currently uses Native Termux as host/control plane with optional Debian PRoot workloads. The product direction and supported claims in this older proposal may be stale; use the [current capability matrix](../testing/FEATURE-MATRIX.yaml) and [phase status](../PHASE-STATUS.md).

## Website purpose and truth boundary

The product website should be a product guide and evidence index, not a second source of implementation truth or remote shell installer. Repository source, tagged releases, phase evidence and compatibility records remain authoritative. The site must say when a feature is `planned`, `experimental`, `limited`, or `verified` for an exact profile.

At audit time there is no product-site source in this repository and GitHub Pages is not enabled for it. CLI guide links now point to the canonical repository documentation rather than a nonexistent Pages site. There is no release/download artifact to link. Do not create a download action from a guessed URL.

## Suggested sitemap and page content

| Route | Job and key content | Evidence / CTA | SEO/content gate |
|---|---|---|---|
| `/` | One-sentence product explanation; Native Termux host/control plane with optional Debian PRoot workloads; current phase and limitations; a real owner-approved screenshot only if available | Source, roadmap, docs; CTA: read install status | First screen must say this is in development until a qualified release exists |
| `/product/` | Product boundaries, Native/PRoot execution-provider architecture, CLI/API model | Architecture and ADRs | Distinguish implemented Native and optional PRoot workflows from unimplemented broader orchestration; avoid unsupported “all-in-one” claims |
| `/features/` | Machine-readable free/premium/service catalog rendered into status cards | Canonical [`docs/testing/FEATURE-MATRIX.yaml`](../testing/FEATURE-MATRIX.yaml); each feature has evidence link | No generic CPU/GPU/NPU claim; separate process contexts; commercial class does not imply shipping |
| `/compatibility/` | Tested Native device/runtime matrix, known failures, date, compatibility labels | [`docs/testing/DEVICE-COMPATIBILITY.md`](../testing/DEVICE-COMPATIBILITY.md) and accepted reports | `unknown` remains visible; distinguish silicon detection from workload qualification |
| `/acceleration/` | Filterable CPU/GPU/NPU report index and charts generated only from accepted raw benchmark records | Canonical reports under [`docs/testing/reports/`](../testing/reports/README.md) and linked methodology | No zero-filled “not tested” points, synthetic device charts, upstream numbers presented as Ternuxx results, or chart without report/hash |
| `/install/` | Prerequisites, supported flow, preview/apply, rollback, data scope | Exact tagged docs/release | Hide install command/download CTA until the package workflow is release-qualified |
| `/downloads/` | Latest stable release, version, source commit, assets, checksums/signatures, known issues | GitHub Release API or release manifest | Empty state: “No stable release is available yet”; no fabricated APK |
| `/docs/` | Getting started, provider setup, doctor, troubleshooting, recovery, architecture, security | Canonical repo docs | Generated copy must be versioned/tagged with release and preserve repository links |
| `/services/` | Proposed services only when owner accepts and can deliver them; exact scope/exclusions/contact route | Owner-approved availability and contact | No fake prices/SLAs or “book now” before legal/payment setup |
| `/security/` | Threat boundaries, data collection, reporting method, release provenance | `SECURITY.md` plus operational response route | Do not promise response time until staffed |
| `/about/` | Mission, maintainer, project history, distinction from personal portfolio and Ternux | Verified public biography links | Don't project private device/SKB material |
| `/roadmap/` | Current generated phase status and planned features | `docs/ROADMAP.md`, phase evidence | Never convert roadmap into a feature list presented as shipping |
| `/legal/` | License, third-party notices, privacy, terms, trademark and support conditions once approved | Actual legal files and approvals | No placeholder legal text dressed as final policy |

The current planning source of truth is [`docs/testing/FEATURE-MATRIX.yaml`](../testing/FEATURE-MATRIX.yaml), with stable ID, implementation and validation state, commercial class, provider, requirements, evidence, limitations, security constraints, next action and owner decision. If the website is built in a separate repository, consume this file through a version-pinned export or reviewed generated snapshot; do not create a second manually maintained catalog.

## Editions and package menu

No edition or product package is currently available. Proposed future labels, not commitments:

- **Core:** useful workstation management features, without payment barriers if the owner chooses the recommended route.
- **Assisted setup:** human-delivered, scoped help after a profile is tested and a business process exists.
- **Maintenance/troubleshooting:** time-boxed service after support limits and recovery boundaries are documented.
- **Custom integration/training:** separately scoped statement of work and IP terms.
- **Premium modules:** evaluate later only if customers repeatedly request a technically separate, maintained capability. No core lock, DRM, entitlement check or payment enforcement is proposed now.

For any eventual package page, show exact inclusions/exclusions, provider/device prerequisites, update term, support boundary, customer data handled, refund/cancellation policy, compatible license, and final owner-approved BDT price. Avoid subscription language unless recurring value is demonstrated.

## Hosting recommendation

| Option | Cost/fit at review | Important limit | Recommendation |
|---|---|---|---|
| GitHub Pages | Simple, static and familiar; owner already has a portfolio there | GitHub's current Pages rules say it is not intended/allowed as free hosting for a site primarily facilitating commercial transactions or commercial SaaS ([official limit](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)). A commercial service/product site should not depend on it without confirming policy applicability. | Keep the existing personal portfolio there; avoid making it the commercial product host. |
| Cloudflare Pages | Free plan currently supports up to 500 builds/month, one concurrent build, 20,000 files per site and 25 MiB per file; static content avoids a dynamic backend. Pages Functions consume Workers quota. [Official limits](https://developers.cloudflare.com/pages/platform/limits/) | Provider account, terms, build integration and brand/domain configuration need approval. Any form/backend expands data/security obligations. Limits/prices change. | Smallest viable future product site for static docs and a brochure, pending account/terms review. Use static assets only at first. |
| Netlify | Current pricing lists $0 Free plan with 300 monthly credits and deploy previews; production deploys consume credits and sites may pause at limits ([official pricing](https://www.netlify.com/pricing/)). | Credit changes and account ownership; potential paid usage if scaling. | Good alternative if Next.js workflow fits better; set hard spend limits and recheck current terms before use. |
| Self-hosted/VPS | Full control over headers/forms/server | Recurring operations, patching, backup, incident response and bandwidth cost | Not justified for the first static product site. |

**Recommendation:** defer hosting implementation. When approved, build a static preview in an isolated `ternexx-site` repository or a clearly separated `/website` project, then publish to Cloudflare Pages free static hosting with no form, user account, payment, API or analytics. A `*.pages.dev` preview is not a permanent brand/domain decision. Check domain ownership/availability and trademark clearance before purchase; no domain has been verified or bought. Keep hosting source portable so export can move providers.

### Deployment design

- Public product source remains GitHub canonical. Website repo uses branch protection/review; production deploy from protected `main` or a tagged release, preview deploys from PRs.
- Pin Actions by full commit SHA, use minimal `contents:read`/deployment permissions, use provider OIDC/deploy token with narrow site scope, and never place secrets in client bundles or logs.
- Build deterministic static output from tagged documentation and current feature catalog. Fail the build if a “verified” page has no evidence link/date, a download URL is not in release metadata, or a legal page is marked draft.
- Production rollback = redeploy last known-good immutable deployment and record incident; preserve previous website artifacts. Keep export/source in Git to allow host migration.
- Review dependencies monthly; set a no-spend alert/hard cap where host billing supports it. Document owner recovery/access and a second trusted recovery method before production.
- Static security headers should use a reviewed CSP, `X-Content-Type-Options`, `Referrer-Policy`, restrictive `Permissions-Policy`, and HSTS only after HTTPS/domain behavior is verified. Avoid embedding inline scripts that force an unsafe CSP.

## Personal portfolio integration

The existing `https://soobujmiah.github.io/` portfolio is public, active and separately maintained. Local Git remote is `soobujmiah/soobujmiah.github.io`; it is a Next.js static export with a detailed bilingual SEO/accessibility/evidence workflow. Preserve its routes, content, visual system, claims verification and deployment workflow.

Recommended brand graph after approval:

- Personal portfolio = the person, experience, broader services, selected projects.
- Ternuxx product site = product, release, supported features, installation, evidence, security, service terms.
- GitHub Ternuxx repo = source, issues, releases and development history.

The acceleration portfolio should include the methodology, backend-specific pages, compatibility table and accepted report index from `docs/testing/`. Charts and filters are derived from accepted machine-readable reports; the report files remain canonical. With no accepted measurements, show a clear empty state and statuses such as `Not Tested`, `Blocked`, or `Unknown` instead of synthetic/zero values.

Add one portfolio project card linking to the product site/repository only after a site exists and product facts are verified. Add a “maintainer / more projects” link from the product site back to the portfolio. Do not edit the portfolio in this initiative's audit. The site already has a bilingual SEO and route-validation system; follow its page-level metadata/content gates if the owner later authorizes a portfolio change.

## SEO strategy

No website exists, so this is a target keyword-to-page map, not search-volume research or a ranking claim. Search volume, clicks and impressions remain unknown until a public site exists and owner-approved measurement is configured.

| Page | Search intent / keyword candidates | Differentiating content required | CTA / links | Update cadence |
|---|---|---|---|---|
| Home | “Termux mobile workstation”, “Ternuxx Android workstation” | Honest current status, provider architecture and actual supported workflow | Start here → current install status | Each release |
| Install | “Termux XFCE install”, “Termux:X11 desktop setup” | Reproducible, versioned steps, preview and exact failure recovery | Supported release only | Each package/runtime change |
| Compatibility | “Linux desktop on Android”, “Termux GPU Adreno” | Exact device, Android/Termux/driver/workload, result and limitation | Evidence and issue form | Each new test; stale evidence flagged |
| Native workstation | “Termux mobile workstation”, “Termux:X11 XFCE on Android” | Show the exact supported Native profile and verified workflows | Architecture/docs | Each release |
| Local AI | “local AI on Android Termux”, “NPU Termux” | Explain bounded CPU/Vulkan/experimental HTP evidence and remaining limits | Evidence only | On runtime/model research change |
| Bangla guide | “Termux e Linux desktop”, “Android phone e Debian PRoot” | Natural Bangla instructions, same technical truth as English | Install/docs | Match English release |
| Services | “Termux setup help Bangladesh”, “Linux on Android support” | Real service scope, location/timezone, exclusions and confirmed availability | Minimal contact route | Monthly after launch |

Content must answer the user's real task, not repeat keywords. Do not create mass-generated near-duplicate “best distro/device” pages. Google Search Central says SEO should help users/search engines understand the site; sitemap submission does not guarantee indexing, and structured data does not guarantee rich results ([SEO Starter Guide](https://developers.google.com/search/docs/fundamentals/seo-starter-guide), [sitemap guidance](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap)).

### Technical SEO launch checklist

- Server-render meaningful page text (static generation is fine); every page has a unique useful `<title>` and meta description.
- Canonical URL for each page; XML sitemap contains only canonical, indexable, live pages; `robots.txt` allows public docs and points to sitemap.
- Descriptive stable paths; 404 and redirects tested; no indexable preview/staging pages or internal/private docs.
- Logical heading structure, crawlable anchors, breadcrumbs, internal links and accessible labels.
- English and Bangla pages get accurate `lang`, `hreflang` alternates and self-canonical URLs only when equivalent pages exist; do not machine-translate legal text without review.
- Compress responsive screenshots, include real alt text and rights/source metadata; respect reduced motion, keyboard, contrast, zoom and touch targets.
- Open Graph/Twitter metadata points to an owned, licensed image; no borrowed competitor imagery.
- Schema: `WebSite`, `Organization` or `Person`, `BreadcrumbList`, and `SoftwareApplication` only when it truthfully describes an actual released application. Never add fabricated ratings, reviews, offers or price. Rich result eligibility is not a promise.
- Monitor crawl/index errors, sitemap fetch, broken links, Core Web Vitals and route parity after each release. No score/rank guarantee.

### Measurement and privacy

Default: **no analytics and no form backend at first launch**. Use a visible contact email or GitHub issues only after owner selection and clear spam/data boundaries. Search Console can be considered later for query/crawl data; it transfers data to Google and requires account/access review. Privacy-focused hosted Plausible or self-hosted Umami are candidates, not selected; hosted pricing, data processing, cookie/local-storage behavior, hosting location and retention must be rechecked. Do not introduce Google Analytics/advertising cookies by default.

Measure qualified outcomes rather than raw pageviews: visits to install/compatibility pages, real release asset downloads, issue-to-solved ratio, support inquiry completion and pilot conversion. Use aggregate counts; no advertising profile. Retention and opt-out must be documented if measurement is enabled.

## Release/download architecture

At audit time there are zero GitHub Releases and zero built artifacts. GitHub's auto-generated source archive is not a supported installer.

Future source of truth: GitHub Release metadata for a tagged, reviewed commit. An automated site build may query the official GitHub API and show release version, commit, asset name, OS/ABI, SHA-256, signature/provenance, installation docs, known issues and rollback. If no stable release exists, show “not available yet.”

Release gates should include reproducible build where possible, SBOM, dependency notices, checksum, signed provenance (or a documented alternative), source tag, changelog, tested install/upgrade/rollback, and owner-reviewed device matrix. Never link to arbitrary Actions artifacts as public stable downloads. Do not publish APKs, rootfs archives, third-party binaries or package mirrors until component redistribution licenses are cleared.
