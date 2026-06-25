
---
## [linear.app](https://linear.app/)
**Folder:** `1_top_quality_benchmarks`
**Screenshots:** `linear_top_1.png`, `linear_top_2.png`, `linear_scroll_1.png`, `linear_scroll_2.png`

**Palette:** Pure dark theme — body `rgb(8,9,10)`, text `rgb(247,248,248)`. Single amber/orange accent used only on status dots; everything else greyscale. Customer logos rendered muted, not highlighted.

**Type:** Inter Variable only, full stack. H1 at ~72px / 700–800 weight with tight letter-spacing (~1.0 line-height). Body 16–18px regular. No display face anywhere.

**Animation:** Pure CSS keyframes using `steps(1)` timing — a dot-grid that blinks/pulses at 3200ms to suggest AI agent activity. No GSAP, no canvas, no Three.js. Hero app mock is a static DOM render, not video or canvas.

**Layout:** Asymmetric hero — headline left ~60%, right column empty above the fold. ~200px breathing room below nav. Inline product UI (3-panel: sidebar / content / detail) is the hero visual; no stock imagery. Below fold: muted-grey customer logo strip, then two-weight single-colour section headline (bold + regular Inter, all white) for rhythm without a second colour.

**Key patterns:**
- Ghost nav with single white-pill "Sign up" CTA — only inverted element on the page
- Product mock as hero eliminates stock-photo layer; AI chat panel overlays bottom-right of mock
- Extreme restraint: one accent colour, one CTA inversion, flat black background

**Takeaway:** Linear's design thesis is that the product itself is beautiful enough to be the marketing asset. Maximum restraint — no gradients, no glassmorphism, no colour beyond one accent — lets the UI chrome speak.

---
## [anthropic.com](https://www.anthropic.com/)
**Folder:** `1_top_quality_benchmarks`
**Screenshots:** `anthropic_top_1.png`, `anthropic_top_2.png`, `anthropic_scroll_1.png`, `anthropic_scroll_2.png`

**Palette:** Warm cream body `rgb(250,249,245)` — not white, a parchment tone that reads editorial and grounded. Text near-black `rgb(20,20,19)`. The hero splits into a dark right panel (near-black with a natural/organic photographic texture) creating a high-contrast diptych. No colour accents — the sole CTA "Try Claude" uses the same dark near-black as a pill button. Colour vocabulary is deliberately restricted to two tones.

**Type:** Proprietary typefaces — "Anthropic Serif" and "Anthropic Sans" — both custom-commissioned. The hero H1 uses Anthropic Serif at large scale with selective underline emphasis on key nouns ("research", "products"). Body copy and nav in Anthropic Sans. The serif/sans split maps to editorial weight vs. functional clarity. Using a named proprietary face is a strong brand trust signal.

**Animation:** GSAP present; keyframes include `marquee` (scrolling text strip) and `fadein`. The hero appears static between 2s and 7s captures — GSAP likely drives scroll-triggered reveals further down the page. No canvas, no Three.js, no SVG animation.

**Layout:** Split-screen hero at 1440px — left ~55% on the warm cream with headline + two-line subhead, right ~45% a full-bleed dark editorial panel ("Project Glasswing") with a large organic geometric photograph (wing/web structure). Below fold: standard 3-column card grid ("Latest releases") on the cream background with minimal dividers.

**Key patterns:**
- Proprietary typeface as brand identity anchor — the serif alone signals "serious institution"
- Light/dark diptych hero communicates dual nature: warm/human (left) + precise/technical (right)
- Zero colour accents — restraint as sophistication signal
- Editorial magazine structure: feature panel + article cards, not SaaS product grid

**Takeaway:** Anthropic positions as an institution, not a startup — the design language borrows from scientific publishing and longform journalism rather than B2B SaaS conventions.

---
## [raycast.com](https://www.raycast.com/)
**Folder:** `1_top_quality_benchmarks`
**Screenshots:** `raycast_top_1.png`, `raycast_top_2.png`, `raycast_scroll_1.png`, `raycast_scroll_2.png`

**Palette:** True dark — body `rgb(7,8,10)`, near-absolute black. The entire above-fold is dominated by a large abstract light-beam graphic: deep red/coral diagonal rays against the black, creating a visceral energy without a UI element in sight. Text is white. The orange/red Raycast logo mark is the only colour in the nav. CTA buttons use a dark pill ("Download") with an orange dot accent.

**Type:** Inter for all body and nav; GeistMono for code/technical snippets (seen in install instructions). H1 is large-scale white, loose-weight, centre-aligned. Subhead in muted grey-white, smaller and tighter — creating a clear hierarchy without a second typeface.

**Animation:** Pure CSS keyframes — 15 named animations including `blink`, `loadingSweep`, `progress`, `fade-in-up`, and notably `nightRider` (likely the diagonal beam sweep on the hero). One canvas element present (probably powering the animated beam). No GSAP, no Three.js — impressive visual weight achieved without heavy JS libs.

**Layout:** Full-bleed dark hero, abstract graphic fills the entire viewport with text centred over it. Below fold: sticky nav slides in with the Raycast app screenshot emerging from the bottom of the screen — a macOS menubar mockup that reveals itself as you scroll. Large centred section headline ("Take shortcuts, not detours.") with minimal subtext, followed by the app UI demo.

**Key patterns:**
- Abstract light-beam hero — communicates speed/energy without a literal product screenshot at first glance
- Dual download CTAs (Mac + Windows) with version/homebrew install line beneath — signals developer audience
- "Introducing Glaze" pill announcement — same pattern as Linear's micro-banner (product news as nav-adjacent badge)
- macOS-native app mockup scrolls up from below fold — product reveal as scroll reward

**Takeaway:** Raycast leads with pure visual drama — the beam graphic is emotional, not informational — then rewards scroll with practical product demonstration. Dark + vivid accent is the signature of Mac productivity tools targeting developers.

---
## [stripe.com](https://stripe.com/au)
**Folder:** `1_top_quality_benchmarks`
**Screenshots:** `stripe_top_1.png`, `stripe_top_2.png`, `stripe_scroll_1.png`, `stripe_scroll_2.png`

**Palette:** White/near-white body background with a dramatic multicolour gradient wave hero graphic (pink → orange → purple → teal → yellow) bleeding off the right edge. Body text dark near-black; hero subhead text in violet/indigo — the gradient palette bleeds into the type. Below fold sections use a very light lavender-grey panel background. CTA is a vivid purple pill ("Get started"), complemented by a ghost "Sign up with Google" button.

**Type:** Söhne Variable (`sohne-var`) — a humanist sans, warm and authoritative. H1 is large, dark, left-aligned. Subhead text inherits the violet from the hero gradient — elegant two-tone effect using a single typeface. Customer logo strip uses the brands' own identity fonts/logos in natural colour.

**Animation:** One canvas element drives the flowing gradient wave — likely a WebGL or 2D canvas gradient animation. No GSAP, no keyframe names extracted (animations are canvas-native). The logo strip between 2s and 7s screenshots shows different logos cycling — a marquee/carousel.

**Layout:** Left-text hero (~55%) with the gradient wave filling the right ~45% and spilling off-screen. Below fold: full-width marquee logo strip (Amazon, NVIDIA, Google, Ford etc.), then white-background section heading with a two-column card grid. Each card contains a real product UI mockup (payment form, billing dashboard) — the actual Stripe interface as the visual proof point, not illustrations.

**Key patterns:**
- Gradient wave as brand signature — organic, flowing, unmistakably Stripe at a glance
- Violet/indigo body copy inherits the brand gradient palette rather than using a flat grey
- Real product UI inside rounded cards with a light box shadow — tactile, trustworthy
- The scroll-animated product demos rotate between different languages/currencies — signals global reach

**Takeaway:** Stripe uses its gradient as a recognisable brand asset the way other companies use logos — the wave IS the identity — while the actual product UI does the trust-building work in the content sections below.

---
## [vercel.com](https://vercel.com/)
**Folder:** `1_top_quality_benchmarks`
**Screenshots:** `vercel_top_1.png`, `vercel_top_2.png`, `vercel_scroll_1.png`, `vercel_scroll_2.png`

**Palette:** Near-white body `rgb(250,250,250)`. The hero graphic is a wide gradient rectangle (gold/amber → white → mint/teal) displayed in a grid-divided panel, with a wireframe triangle (Vercel's logo form) centred over it. Text is near-black `rgb(23,23,23)`. CTA uses a solid black pill ("Start Deploying") + ghost "Get a Demo". Below fold, "Pro" links appear in blue, "Enterprise" in purple — the only in-body colour accents.

**Type:** Geist and Geist Mono — Vercel's own open-source typefaces. Clean, geometric, developer-native. H1 is bold centred, large but not oversized. The content section uses inline icon glyphs (`>_`, globe emoji, git branch symbol) woven into the headline text — communicating developer culture at the typography level.

**Animation:** No GSAP, no canvas, no Three.js. CSS keyframes include `drawAndErase` animations for SVG path drawing (the "v0 avatar" — likely an animated SVG logo), `fadeIn`/`fadeOut` for dialogs, and grid `Disappear` animations for responsive breakpoints. Very lightweight animation footprint for a top-tier design site.

**Layout:** Centred single-column hero with the gradient panel sitting below the headline/CTA as a contained graphic block, not a full-bleed background. The grid overlay on the hero panel (visible column/row lines) references a technical/structured aesthetic. Below fold: full-width gradient strip peeks at top, then centred large-text sections with minimal content density — lots of whitespace, each concept gets its own full-width zone.

**Key patterns:**
- Vercel's own typeface (Geist) as brand signal — uses the marketing site to demonstrate the product
- Inline developer icons embedded in headline copy (`>_`, git symbol) — speaks directly to engineers
- Gradient as contained graphic element, not a full-bleed takeover
- "Scale your [Enterprise] without compromising [Security]" — rotating pill-badge inline text pattern

**Takeaway:** Vercel designs for developers who will notice the typeface is Geist and respect it — the self-referential move of building your marketing site in your own tools is the brand statement.

---
## [anduril.com](https://www.anduril.com/)
**Folder:** `2_deep_tech_aesthetics`
**Screenshots:** `anduril_top_1.png`, `anduril_top_2.png`, `anduril_scroll_1.png`, `anduril_scroll_2.png`

**Palette:** Pure black body. The hero is a full-bleed cinematic photograph — military silhouettes against a deep amber/orange dusk sky — occupying the left ~55% of the viewport with the right side pure black. Below fold: a grid of dark editorial product cards (each a high-quality photograph of an Anduril product — drone, fighter jet, sensor hardware) on black. No colour accents; the photography provides all colour.

**Type:** Three typefaces — `HelveticaNowDisplay` (headline weight, modern grotesque), a serif (`Times New Roman` or similar — used for editorial body text), and `Elios` (possibly a custom/display face). The serif/grotesque pairing in a defence context feels intentionally serious and institutional, not tech-startup.

**Animation:** Theatre.js present (a timeline-based JS animation library used for complex scroll choreography), Lenis for smooth scroll, and one canvas element. CSS keyframes are minimal (`inView`, `bar`, `slider`). The heavy lifting is Theatre.js — likely driving cinematic scroll-linked transitions between product sections.

**Layout:** Full-viewport hero image left-anchored on pure black, with no text or headline at first scroll position — the entire above-fold is pure cinematic image + logo + nav. No CTA visible above fold. Below: product grid using a mosaic/asymmetric card layout with products named in white text over their photographs (Ghost, Barracuda, Lattice).

**Key patterns:**
- Zero above-fold copy — the image alone is the message (confidence signal)
- Theatre.js for high-production scroll choreography — uncommon, signals bespoke creative investment
- Product nav by domain (Sea / Land / Air / Space) rather than by use case or feature — military domain language
- Mosaic photo grid as product catalogue — each product gets editorial photography treatment

**Takeaway:** Anduril rejects SaaS design conventions entirely — no hero text, no CTA, no feature grid. The aesthetic is cinematic defence editorial, closer to a prestige film production house than a technology company.

---
## [psiquantum.com](https://psiquantum.com/)
**Folder:** `2_deep_tech_aesthetics`
**Screenshots:** `psiquantum_top_1.png`, `psiquantum_scroll_1.png`

**Palette:** Pure black body. Hero text is white on black. A right-aligned panel in the hero introduces a violet/purple gradient block — this is the only colour on the page, used to contain the explanatory body copy alongside the main headline. Below fold continues on pure black. The purple gradient panel (`pulseGradientVertical` keyframe) is the sole accent; everything else is monochrome.

**Type:** Articulat CF (Medium and Normal weights) for headlines and display text — a geometric grotesque with an industrial, technical character. Inter (Light, Regular, Medium) for body and nav. The pairing is purposeful: Articulat CF reads as serious and engineered, not playful. H1 is large but not oversized, left-aligned, regular weight — restrained for a quantum computing company.

**Animation:** CSS keyframes only — `sweepDirect` and `pulseGradientVertical`. No GSAP, no Three.js, no canvas. One video element present (likely a background video, non-playing in headless). The pulsing gradient on the right panel is the primary animation — a vertical gradient sweep suggesting energy/signal.

**Layout:** Standard single-column left-aligned hero with a right-side explanatory panel (split at ~60/40). Headlines are large and bold, but the page has significant whitespace — "Impossible until it's not" serves as a section bridge headline in huge type, anchoring the scroll transition. Below fold: "Our approach" section continues the sparse, high-contrast layout. No cards, no icon grids — copy and space only.

**Key patterns:**
- Single accent colour (purple gradient panel) does all the visual work on an otherwise monochrome page
- Bridge headline ("Impossible until it's not") used as dramatic section separator — big type as a design element
- Articulat CF signals engineering credibility without being cold or techno-futurist
- Zero decorative elements — the restraint communicates confidence

**Takeaway:** PsiQuantum treats the website like a scientific abstract — sparse, precise, high-contrast, with a single vivid accent. The design says "we don't need to impress you with visuals; the science is enough."

---
## [rigetti.com](https://www.rigetti.com/)
**Folder:** `2_deep_tech_aesthetics`
**Screenshots:** `rigetti_top_1.png`, `rigetti_scroll_1.png`

**Palette:** Bold teal/cyan (`~rgb(0,196,180)`) full-bleed hero — a standout choice in the deep-tech space where black dominates. Hero text white. Below fold switches to white body with navy/dark-indigo text (`rgb(13,13,54)`). Accent teal carries through as the CTA and link colour on the white sections. Numbered interaction points on the scroll section use distinct colours (yellow, navy, pink, blue, teal) — the only multi-colour moment on the page.

**Type:** `objektiv-mk3` (geometric humanist sans) for headlines — rounded, friendly, confident. `GTAmericaMono` for monospace/technical callouts. `IBM Plex Sans` for body copy. Three distinct typefaces serving three registers: brand, technical, and readable prose. H1 ("Think quantum") is extremely large, bold, full-width — close to display advertising in scale.

**Animation:** CSS-only — `pulse` and swiper/lightbox transitions. No GSAP, no canvas. The interaction in the scroll section is click-based (numbered callout points on the quantum hardware photo) — a hotspot explainer pattern rather than passive animation.

**Layout:** Full-viewport teal hero with a detailed illustration of quantum hardware (the dilution refrigerator chandelier) centred behind the oversized headline — text overlaid on the illustration. Below fold: white background, left-aligned editorial copy with the hardware photo right-aligned at large scale with numbered interactive callout points, inviting exploration of the physical product.

**Key patterns:**
- Teal as a brand differentiator — immediately distinctive against the sea of black deep-tech sites
- Hardware illustration/photo as hero — the physical product is the visual, not an abstraction
- Interactive numbered callout diagram (click to learn) — product education embedded in the marketing page
- "GET QUANTUM" CTA in spaced caps on a bordered pill — direct, almost imperious tone

**Takeaway:** Rigetti is the most visually confident of the quantum computing sites — the teal hero is a deliberate break from dark conventions, positioning the company as approachable and commercially ready rather than purely research-stage.

---
## [skild.ai](https://www.skild.ai/)
**Folder:** `2_deep_tech_aesthetics`
**Screenshots:** `skild_top_1.png`, `skild_scroll_1.png`
**Note:** Site is almost entirely video-driven (4 video elements); headless Chromium cannot render video frames. Screenshots show only the static text/nav layer over blank white space.

**Palette:** White background, near-black text. Two-tone headline technique: dark/black for the nouns ("Any", "One"), mid-grey for the descriptive words ("robot.", "task.", "brain.") — creating emphasis through opacity contrast within a single colour. No other colour on the visible page.

**Type:** Geist Sans (Next.js/Vercel's open-source typeface) used via Next.js class names. Headline is very large, centred, light-to-medium weight. The two-tone opacity trick is the only typographic decoration — no bold, no italic, just contrast between `#000` and `~#aaa` within the same size and weight.

**Animation:** CSS `fadeInUp` (likely for the headline entrance) and `spin`. No GSAP, no canvas, no Three.js. The animation work is entirely in the videos.

**Layout:** Extreme minimalism — headline centred in the top third of the viewport with vast empty space below (where videos would render). Nav has only two items (Blogs, Careers) in a single rounded-pill toggle, top-left. No CTA, no subhead, no body copy above the fold. The site appears to be a pure video-showreel experience.

**Key patterns:**
- Two-tone opacity headline as the sole typographic device — elegant and distinctive
- Near-zero nav (2 items) signals early-stage / product-focused company not yet needing deep site architecture
- Entire value proposition delivered through video rather than copy or illustration
- Geist Sans choice suggests a Next.js stack and developer-adjacent sensibility

**Takeaway:** Skild bets everything on the videos — the design chrome is stripped to almost nothing so the robot footage can speak. The two-tone headline is the only design flourish, and it's a clever one.

---
## [pi.website](https://pi.website/) — Physical Intelligence
**Folder:** `2_deep_tech_aesthetics`
**Screenshots:** `pi_top_1.png`, `pi_scroll_1.png`

**Palette:** Warm off-white/parchment `rgb(245,244,239)`. Text near-black. Zero colour accents — no buttons, no CTAs, no brand colour. Highlighted research entries use a thin black border box, nothing more.

**Type:** `Signifier` (a contemporary serif with academic/literary weight) for the company name and section headers. `ui-monospace` for all body copy and paper titles — a deliberate choice that frames research as code, or output as preprints. The monospace body is the most distinctive type decision here.

**Animation:** CSS keyframes suggest interactive micro-animations (`dashed-border`, `prompt-pulse`, `scale-loop`, `shimmer-reverse`) but nothing visible at page-load. No canvas, no video, no GSAP.

**Layout:** The entire page is a reverse-chronological list of research papers — title, one-line abstract, date. Featured papers get a bordered card treatment. No hero image, no product section, no team page link visible above the fold. The company description ("a group of engineers, scientists, roboticists…") reads as a single paragraph, academic bio style. Nav has three links only: Home, Research, Join Us.

**Key patterns:**
- Monospace body copy frames the company as a research lab, not a startup
- Paper list as homepage — content IS the product
- No CTA, no pricing, no sales funnel visible
- Serif + mono pairing signals academic publishing aesthetic

**Takeaway:** pi.website is the most extreme anti-marketing site in this collection — it reads like a university lab homepage. The restraint is the brand statement: "we publish papers, not press releases."

---
## [helionenergy.com](https://www.helionenergy.com/)
**Folder:** `2_deep_tech_aesthetics`
**Screenshots:** `helion_top_1.png`, `helion_scroll_1.png`
**Note:** Hero is video-driven; top screenshot shows only logo and blank white. Scroll screenshot reveals content.

**Palette:** White body. The logo mark is a vivid magenta/pink circle-H glyph — the sole colour on the page. Scroll section reveals a large-format photograph with deep red/crimson industrial lighting (the fusion reactor interior), giving the page its colour story despite the white background.

**Type:** `PilatWide` — an extra-wide geometric grotesque, very distinctive. "Fusion technology" rendered in PilatWide at large scale over the machinery photograph has an industrial-magazine quality. The width of the face creates a commanding, almost monumental presence.

**Animation:** CSS only — `fadeIn`, cookie banner transitions. One video in the hero (non-rendering in headless). No GSAP, no canvas.

**Layout:** Video-full-bleed hero (blank in headless). Scroll reveals a wide-format editorial photograph of the fusion machine with headline overlay, followed by content sections. The photography does all the visual heavy lifting.

**Key patterns:**
- PilatWide as a high-distinctiveness typeface choice — immediately recognisable at any size
- Magenta logo on white is the entire brand colour palette
- Reliance on reactor photography for visual drama rather than illustration or animation

**Takeaway:** Helion's design hinges on two strong choices — an unusually wide typeface and deep-red industrial photography — letting the actual fusion technology provide the spectacle.

---
## [cfs.energy](https://www.cfs.energy/) — Commonwealth Fusion Systems
**Folder:** `2_deep_tech_aesthetics`
**Screenshots:** `cfs_top_1.png`, `cfs_scroll_1.png`

**Palette:** Warm taupe/grey body `rgb(204,200,195)`. Hero is a full-bleed dark atmospheric photograph of superconducting magnet hardware — copper, gold, and gunmetal tones — with white headline overlaid. Below fold transitions to light grey with a warmer tonal palette. No strong accent colour; the metallic copper of the hardware photograph is the brand colour by proxy.

**Type:** NB International (`nbInternational` and `nbInternationalMono`) — a Swiss-influenced grotesque with a technical mono variant. Clean, neutral, authoritative. The headline "The world's largest and leading commercial fusion energy company" is set in regular weight at generous size — confident statement, not a shout.

**Animation:** CSS-only; keyframes are mostly cookie/menu UI interactions. No GSAP, no canvas, no video.

**Layout:** Full-bleed hero photograph with text and three value-proposition columns at the base ("Move fast / Move smart / Move together"). Below fold: large editorial section headline, numbered photography panels side by side. The numbered panel pattern creates a structured editorial feel — research report rather than product landing page.

**Key patterns:**
- Hardware photography as hero — the magnet is the product, and it's visually spectacular
- Warm taupe body background differentiates from the ubiquitous white or black
- Three-column value statement at the bottom of the hero (below the fold break) rewards reading
- Numbered content panels suggest a methodical, structured argument

**Takeaway:** CFS positions through material credibility — the close-up magnet photography conveys engineering scale in a way no illustration could, and the warm taupe palette feels grounded and industrial rather than cold or futuristic.

---
## [astranis.com](https://www.astranis.com/)
**Folder:** `2_deep_tech_aesthetics`
**Screenshots:** `astranis_top_1.png`, `astranis_scroll_1.png`

**Palette:** Very dark navy/space `rgb(10,18,25)`. Hero uses real satellite-in-orbit photography — Earth curvature, deep space, satellite hardware — providing all colour through imagery. Text white. The single standout element is a vivid green "CONTACT" pill CTA — the only colour in the nav.

**Type:** Proxima Nova (humanist sans, widely used but well-executed here) + Eurostile (a geometric grotesque with strongly aerospace/space-age connotations — used in NASA materials, the ISS, countless spacecraft UIs). The Eurostile choice is a direct aesthetic signal: this is a real aerospace company.

**Animation:** Minimal — `spin` and skeleton loader only. No GSAP, no canvas. Two video elements (non-playing in headless); the static orbital photography provides sufficient visual context.

**Layout:** Full-bleed hero with real orbital photography behind centred headline and CTA. Secondary CTA ("OUR SATELLITE FOR TAIWAN") as a prominent pill below the primary. Scroll reveals dark-background editorial with large left-aligned headline and a split: long-form text left, full-height photograph right (satellite hardware + American flag — deliberately patriotic framing).

**Key patterns:**
- Eurostile as a deliberate aerospace heritage signal — instantly readable as "space industry"
- Real satellite photography in orbit rather than renders or illustrations
- Green CTA is the only chromatic element in an otherwise monochrome nav — makes it impossible to miss
- American flag in the scroll section — explicit positioning for US government/defence customers

**Takeaway:** Astranis uses classic aerospace typographic language (Eurostile) and real mission photography to communicate operational credibility — they have satellites in orbit, and every design choice reinforces that.

---
## [varda.com](https://www.varda.com/)
**Folder:** `2_deep_tech_aesthetics`
**Screenshots:** `varda_top_1.png`, `varda_scroll_1.png`

**Palette:** Deep navy blue `rgb(10,48,101)` body with vivid orange/amber headlines and accents — a high-contrast complementary pair. The hero background appears to be a satellite photograph of terrain or an abstract orange landscape texture, reinforcing the space/earth duality. The orange-on-navy scheme carries through all sections and card elements.

**Type:** MT Everyday Sans — a contemporary, slightly rounded grotesque. Used at bold weight for the large orange headlines. Readable, approachable, not trying to signal aerospace heritage. Contrasts with the Eurostile/Proxima choices of peers.

**Animation:** GSAP present + extensive marquee CSS keyframes (`marquee-scroll-left/right/up/down`). Suggests animated scrolling text strips as a design pattern. The marquee animations likely run product category names or mission types on a ticker.

**Layout:** Full-bleed hero with textured satellite-imagery background, large orange left-aligned headline ("Space born, Earth bound"), brief descriptor right, and three category links below (Government, Biopharma, Microgravity Research). Scroll reveals a platform section with orange headline + card grid of mission categories, each with category label and arrow link.

**Key patterns:**
- Orange on navy as brand signature — immediately distinctive, warm and energetic vs. cold space aesthetic
- Three-category homepage navigation (Government / Biopharma / Microgravity) signals a multi-market company
- GSAP + marquee animations suggest kinetic, editorial scroll experience
- "Space born, Earth bound" is a memorable two-word contrast headline structure

**Takeaway:** Varda is the most visually energetic deep-tech site in this set — the orange/navy palette and bold type reject the cold-space aesthetic entirely in favour of warmth and commercial confidence.

---
## [datadoghq.com](https://www.datadoghq.com/)
**Folder:** `3_b2b_infra_companies`
**Screenshots:** `datadog_top_1.png`, `datadog_scroll_1.png`
**Note:** Hero is video-driven (11 video elements); top screenshot captured the static UI layer only.

**Palette:** White body. Datadog purple (`~#632CA6`) as the primary brand accent — used for nav, CTAs, and highlights. The hero product screenshot introduces a wide colour palette (orange, red, green, purple — observability dashboard colours). Below fold: a vibrant purple/magenta event card for the DASH conference, introducing an energetic secondary colour moment.

**Type:** NationalWeb (a humanist sans with warmth) for headlines and UI. Helvetica as fallback. The type is utilitarian and clear — this is a data-dense product, so readability over expression.

**Animation:** 11 video elements (entirely non-rendering in headless). CSS keyframes minimal. The product experience is communicated through dashboard screenshots rather than live demos.

**Layout:** Standard centred hero: headline + one-line subhead + two CTAs ("Free Trial" + "See the Platform") + product dashboard screenshot below. Below fold: customer logo strip (Samsung, Nasdaq, Korean Air, Shell, HashiCorp, SNCF), then an event promotion card. Conventional, conversion-optimised B2B structure.

**Key patterns:**
- Dense product dashboard screenshot as hero — shows the actual monitoring UI, signals data richness
- Two-CTA pattern (free trial + demo) — industry standard for developer-first with enterprise sales
- Customer logo strip with recognisable enterprise names — trust establishment
- Purple as a strong brand colour differentiator in the observability space

**Takeaway:** Datadog is a polished, conversion-optimised B2B marketing site — every element is tested and deliberate. The design is in service of the funnel, not the aesthetic.

---
## [cloudflare.com](https://www.cloudflare.com/en-au/)
**Folder:** `3_b2b_infra_companies`
**Screenshots:** `cloudflare_top_1.png`, `cloudflare_scroll_1.png`

**Palette:** White body. Cloudflare orange as the dominant brand accent (logo, CTAs, decorative geometric shape — a large orange hemisphere/circle in the hero right side). Text dark near-black. Below fold: orange inline link highlights carry the brand colour into body copy.

**Type:** Inter and system `ui-sans-serif`. Clean, neutral, highly legible. No brand typeface — the orange does the identity work. Headlines are bold, left-aligned. The word "everywhere" in the hero H1 is orange — a single-word colour accent technique.

**Animation:** One canvas element (likely powering an animated network globe or particle effect). CSS keyframes minimal. The hero feels energetic despite the simple type through the geometric orange shape and canvas animation.

**Layout:** Left-text hero with large orange decorative hemisphere right. Below fold: two editorial feature cards (Connect SF conference, Security Signals report) side by side. Second scroll section: full-width centred headline with orange keyword highlight + left-column copy + right-column diagram illustration. Clean two-column content rhythm throughout.

**Key patterns:**
- Single orange keyword highlight within the H1 — creates visual emphasis without changing font weight
- Large geometric shape (orange hemisphere) as hero decoration — instantly recognisable brand element
- Canvas globe animation signals global network scale without text
- Two-column feature cards give the page an editorial/news feel beneath the hero

**Takeaway:** Cloudflare's design centres on a single strong brand asset — the orange — and uses it precisely: one word, one shape, one CTA. The restraint makes the orange feel premium rather than loud.

---
## [fly.io](https://fly.io/)
**Folder:** `3_b2b_infra_companies`
**Screenshots:** `fly_top_1.png`, `fly_scroll_1.png`

**Palette:** Very light lavender/lilac body (near-white with a purple tint). The entire hero is dominated by a large custom illustration — a richly detailed, cartoon-surrealist landscape in purple, teal, coral, and blue pastels. Text is dark navy/indigo. CTA is a vivid purple pill.

**Type:** Fricolage Grotesque (a high-personality display grotesque with quirky letterforms) for the headline — "Build fast. Run any code *fearlessly.*" with "fearlessly" in italic. Mackinac (a contemporary slab serif) for body. The Fricolage/Mackinac pairing is unusual and distinctive — personality-forward, deliberately non-corporate.

**Animation:** CSS keyframes include `fpFadeInDown`, `ping-badge`, `dot-one/two/three` (a typing/loading dot indicator). No GSAP, no canvas. The page relies on the illustration for visual energy, not code-driven animation.

**Layout:** Wide centred hero with the illustration spanning the full width behind and beside the headline/CTA. The illustration is not a background — it IS the hero, with text floating over the left portion. Scroll reveals a white section with a smaller illustration character (a pink creature with legs) beside copy — the illustration language continues throughout.

**Key patterns:**
- Custom illustration as the primary brand asset — entirely unique visual identity, no stock or generic art
- Fricolage Grotesque signals "developer tool with personality" — targets builders who are bored of soulless SaaS design
- Illustration characters carry into scroll sections — world-building, not just a one-off hero splash
- "fearlessly" in italic within the headline — adds rhythm and emphasis at the word level

**Takeaway:** Fly.io deliberately rejects the dark/monochrome developer-tool aesthetic and instead builds a whimsical illustrated world — the design says "we're technical but we have a sense of humour about it."

---
## [planetscale.com](https://planetscale.com/)
**Folder:** `3_b2b_infra_companies`
**Screenshots:** `planetscale_top_1.png`, `planetscale_scroll_1.png`

**Palette:** Off-white/light grey body. Dark near-black text. Orange (`~#F97316`) used for CTA ("Get in touch"), inline keyword links ("fastest databases", "NVMe drives"), and the announcement banner CTA. A left-side vertical orange bar accents the hero subheadline. The orange is precisely deployed — functional, not decorative.

**Type:** `ui-monospace` exclusively — the entire page, headline included, is set in a monospace font. "The world's fastest and most scalable cloud databases" in monospace at a small-medium size is an extreme choice — it reads like a terminal, not a marketing headline. This is a database company talking directly to engineers who write SQL.

**Animation:** Near-zero — only the traffic-light CSS keyframes (`banner-red/yellow/green-light`) suggesting a small status indicator. No GSAP, no canvas, no video.

**Layout:** Minimal left-aligned layout with a thin left vertical bar accent on the opening statement. Below: dense prose paragraphs with orange inline links, followed by a large 5-column logo grid of customer companies (Block, Etsy, Intercom, Cursor, Slack, etc.) rendered in their full brand colours on white — striking and colourful compared to the sparse page above. A testimonial quote then a product-tab section (Vitess / Postgres / Neki).

**Key patterns:**
- Full monospace type stack — the most engineer-targeted typographic choice in this collection
- Customer logo grid in full brand colours — vivid, credibility-dense, visually striking contrast to the sparse page
- Prose-first layout — no icons, no feature bullets above the logo grid
- Orange vertical bar accent on the headline — a single restrained graphic element

**Takeaway:** PlanetScale writes for the DBA and senior engineer who will read every word — the monospace body and prose-first layout signal "we take performance seriously and so do you."

---
## [supabase.com](https://supabase.com/)
**Folder:** `3_b2b_infra_companies`
**Screenshots:** `supabase_top_1.png`, `supabase_scroll_1.png`

**Palette:** Very dark body `rgb(18,18,18)` — near-black with a very slight warmth. The accent is Supabase green (`~#3ECF8E`) — used for the secondary headline line ("Scale to millions"), the primary CTA ("Start your project"), the logo mark, and the GitHub star count badge. Text white. Everything else is neutral dark.

**Type:** Circular (a geometric sans with warm rounded letterforms) throughout. The two-line hero headline — "Build in a weekend" (white) / "Scale to millions" (green) — is the page's defining typographic moment. Large, centred, high contrast between the two lines.

**Animation:** Minimal CSS (`sonner` toast animations). No GSAP, no canvas, no video. The scroll section uses dark card components with subtle icon illustrations to explain each product area.

**Layout:** Centred hero on dark background: announcement pill at top, two-line headline, descriptive paragraph, two CTAs. GitHub star count (101.6K) displayed in the nav — the open-source social proof is right in the header. Below fold: customer logos (Submagic, Mozilla, GitHub, 1Password, PwC), then a 3×2 dark card grid listing product pillars (Postgres DB, Auth, Edge Functions, Storage, Realtime, Vector, Data APIs) with icon + name + one-line description + mini UI demo per card.

**Key patterns:**
- GitHub star count in the nav — open-source credibility as primary trust signal
- Two-colour two-line headline (white + green) — clean, memorable, encodes the value proposition
- Dark card grid showing all product areas — comprehensive product map without requiring scroll
- "Start your project" as primary CTA (not "Sign up") — action-forward framing

**Takeaway:** Supabase's design is disciplined dark-theme developer-tool — the green accent does exactly one job (highlight the key value), and the GitHub star count in the nav tells you immediately who this is for.

---
## [render.com](https://render.com/)
**Folder:** `3_b2b_infra_companies`
**Screenshots:** `render_top_1.png`, `render_scroll_1.png`

**Palette:** White body. Render purple (`~#6B3FA0`) as primary brand colour — vivid, used for the "Get Started" nav CTA (black background), numbered step indicators (purple squares), and the coloured text highlight in the hero ("apps & agents" in pink-to-amber gradient). The announcement banner uses a purple-to-amber gradient. The overall palette is white + black + purple + gradient accent.

**Type:** PP Neue Montreal (a clean contemporary grotesque, widely used in modern SaaS) for body and nav. Roobert (a geometric humanist sans) for the headline. H1 is very large and loose — "Your fastest path to production for" in black, then "apps & agents" in a pink-to-amber gradient. Gradient text used as a highlight technique.

**Animation:** CSS only. The hero right side shows an animated deployment dashboard mock — a `$ git push` terminal command connected to a production dashboard grid, with coloured status blocks.

**Layout:** Left-text hero with a right-side animated product mock (deployment dashboard, service status cards). Below fold: customer logo strip (Base44, Fortune, Shopify, Cognition, Tripadvisor, McKinsey), then "Click, click, done." section with three numbered steps (purple square numbers) — a numbered how-it-works sequence.

**Key patterns:**
- Gradient text on the hero headline keyword — contemporary web technique, adds colour without a separate block
- Animated `git push` → dashboard deployment mock — shows the dev workflow as the hero visual
- Three-step numbered sequence with coloured number markers — simplifies a technical product
- "Changelog" in the nav — signals active development and developer transparency

**Takeaway:** Render positions as the frictionless path from code to production — the `git push` hero visual, three-step how-it-works, and "Changelog" in the nav all reinforce a developer-friendly, deployment-focused identity.

---
## [hex.tech](https://hex.tech/)
**Folder:** `4_adj_inspo`
**Screenshots:** `hex_top_1.png`, `hex_scroll_1.png`

**Palette:** Off-white/cream body `rgb(255,252,252)`. Dark navy/charcoal text. The hero is split: left third plain with headline, right two-thirds a dense mosaic of product UI screenshots (notebooks, charts, AI chat panels) arranged in overlapping, slightly rotated columns — all rendered on light grey cards. The product screenshots introduce a full data-vis colour palette (blues, purples, teals) through the UI itself. No strong brand accent beyond the product UI colours.

**Type:** Cinetype and Cinetype Mono (distinctive geometric sans with a technical/editorial quality) for headlines. PP Formula and PP Formula SemiExtended for subheadings. IBM Plex Sans for body. Lato as fallback. A rich multi-typeface system — Cinetype as the brand face, PP Formula as the structural face, IBM Plex as the readable workhorse.

**Animation:** CSS `ticker` keyframe (scrolling customer logo strip) and `noise` (likely a texture overlay animation). One canvas element. No GSAP.

**Layout:** Left-text hero (~35%) with a right-side product mosaic that extends beyond the viewport edge. The mosaic density communicates product richness without requiring the user to read anything. Below fold: the mosaic continues into a customer logo ticker. The entire above-fold reads as "look at how much this product can do."

**Key patterns:**
- Product screenshot mosaic as hero — density communicates capability at a glance
- Multiple premium typefaces (Cinetype, PP Formula) signal design-forward brand positioning
- `noise` texture animation on the background adds subtle tactility
- Customer logo ticker strip immediately below fold: Reddit, AWS, Anthropic, Figma, Vercel, Brex

**Takeaway:** Hex leads with visual proof-of-work — the overwhelming product mosaic says "this does everything" before a word is read. The typeface investment signals that design matters to this team as much as capability.

---
## [modal.com](https://modal.com/)
**Folder:** `4_adj_inspo`
**Screenshots:** `modal_top_1.png`, `modal_scroll_1.png`

**Palette:** True black body. Vivid lime/neon green accent (`~#A8FF3E`) — used for "AI infrastructure" in the hero H1, the "Get Started" CTA, the logo mark, and subtle dot scatter across the hero background. Text white. Customer logo strip at the bottom of the hero uses a dark tile grid, logos in white/muted. Scroll section introduces green-to-black gradient panels for feature areas.

**Type:** Inter Variable for all UI and body text. Goga (a contemporary display grotesque with personality) for the hero headline. "AI infrastructure that developers love" — "AI infrastructure" in lime green, "that developers love" in white. Clean two-weight, two-colour headline with maximum contrast.

**Animation:** One canvas element (likely the dot/particle scatter in the hero background). Six video elements (non-rendering in headless). CSS includes shimmer, pulse, and Svelte-generated animation names — a Svelte-built frontend.

**Layout:** Full-viewport black hero, centred headline + subhead + two CTAs, with a subtle dot scatter background animation. Below the fold: dense horizontal customer logo grid (Achira, Ramp, Ai2, Harvey, you.com, Cognition, Decagon, Codegen). Scroll reveals a section navigation sidebar on the left with four feature areas, and a code editor mock + green gradient panel on the right.

**Key patterns:**
- Neon green on black — the highest-contrast accent colour in this collection, unmissable
- Dot scatter background on the hero — technical/spatial feel, suggests distributed infrastructure
- Left sidebar feature navigation on scroll — product education via a structured outline
- Svelte frontend (unusual for a marketing site at this scale) — signals technical culture

**Takeaway:** Modal's green-on-black is the boldest colour choice in the developer-tool space — it's energetic, confident, and immediately distinctive. The design bets that developers respond to strong personality over conventional SaaS restraint.

---
## [wandb.ai](https://wandb.ai/site/) — Weights & Biases
**Folder:** `4_adj_inspo`
**Screenshots:** `wandb_top_1.png`, `wandb_scroll_1.png`

**Palette:** Dark charcoal body `rgb(26,28,31)`. Gold/amber yellow (`~#F5C842`) as the primary brand accent — used for the "SIGN UP" CTA, the logo mark dot-grid, inline link highlights, and the product feature card backgrounds. Text white. The yellow-on-dark pairing is warm and distinctive, avoiding the cold blue/purple/green patterns common in ML tooling.

**Type:** Source Serif 4 for the hero headline — a contemporary serif with academic credibility. Source Sans Pro and Source Sans 3 for body and UI. The Source family pairing (serif headline + sans body) is a classic editorial approach, here signalling "research platform" rather than "startup tool." The hero headline uses a strikethrough on "hard" with "easy" handwritten above it — a typographic editorial joke.

**Animation:** No GSAP, no canvas. The strikethrough/handwriting effect is static SVG or CSS — the "editorial joke" is the animation substitute.

**Layout:** Centred dark hero with the headline typographic gag ("AI is ~~hard~~ easy to productionize") and two side-by-side code terminal panels for W&B Weave and W&B Models, each with a distinct CTA. Below fold: wide customer logo strip (AstraZeneca, BMW Group, Canva, Meta, Microsoft, NVIDIA) in muted white on dark. Then a four-column yellow card grid for product areas (Models, Training, Inference, Weave).

**Key patterns:**
- Serif headline in an ML tool — repositions the product as a research-grade platform, not a dashboarding toy
- Handwritten "easy" striking through "hard" — editorial wit, humanises a technical product
- Yellow product cards on dark background — warm, energetic contrast to the cold-dark ML aesthetic
- Two terminal panels side-by-side — shows both products simultaneously without forcing a choice

**Takeaway:** W&B uses editorial warmth (serif type, the handwriting gag, yellow accents) to differentiate from every other cold-dark ML tool — the design says "serious researchers, but not humourless ones."

---
## [observablehq.com](https://observablehq.com/)
**Folder:** `4_adj_inspo`
**Screenshots:** `observable_top_1.png`, `observable_scroll_1.png`

**Palette:** Dark navy/charcoal body (near-black with a cool tint). The hero is a split layout: left dark with white headline text, right filled with a dense live mosaic of actual notebook visualisations (charts, tables, Sankey diagrams, maps) — the product rendering itself as the hero art. Purple (`~#7B5EA7`) as the accent for CTAs, borders on feature cards, and the "O" logo. Text white on dark, dark on light in scroll sections.

**Type:** Spline Sans Mono and Inter — both loaded as Next.js font variables. Monospace for section headlines in the scroll section ("The shortest path from idea to live code", "Literate programming") — all in monospace, reinforcing the notebook/code identity. Body text in Inter.

**Animation:** CSS keyframes include `scrolling`, `button-clicking`, `cursor-clicking`, `dash`, `yellow-flash` — suggesting animated cursor/interaction demos that walk users through the UI. One video element. A thoughtful set of interaction-mimicking CSS animations.

**Layout:** Split hero: dark left with headline + two CTAs, right filled with live or screenshot notebook content spanning the full right half. Below fold: full-width notebook content panel edge-to-edge, then centred headline + body + three-column feature card grid (purple-cornered cards with monospace feature names).

**Key patterns:**
- Live notebook visualisations as hero art — the product IS the design, shown working in real time
- Full monospace headline in scroll section — section headers look like notebook cells
- `cursor-clicking` CSS animation — simulates user interaction as an educational device
- Purple corner markers on feature cards — a subtle structural detail that frames content like a codeblock

**Takeaway:** Observable dissolves the boundary between marketing site and product — the hero is literally the notebook rendering data visualisations. The design demonstrates capability by showing it, not describing it.

---
## [huggingface.co](https://huggingface.co/)
**Folder:** `4_adj_inspo`
**Screenshots:** `huggingface_top_1.png`, `huggingface_scroll_1.png`

**Palette:** White body with a dark hero panel. The hero splits: left dark with white text and the yellow emoji logo mark, right a full dark product UI screenshot (the HuggingFace hub — model cards, leaderboards, dataset listings). Below fold transitions to white with a "Trending this week" section showing coloured model/space/dataset cards in their natural UI colours. The site functions as its own product demo.

**Type:** Source Sans Pro throughout — clean, neutral, highly readable. No display typeface. The emoji logo (🤗) does the brand personality work that typography doesn't — HuggingFace's identity is the emoji, not a typeface.

**Animation:** CSS `spin`, `ping`, `pulse` — minimal. No GSAP, no canvas. The page is static-first with the trending content doing the live-data work.

**Layout:** Dark hero split: left with headline ("The AI community building the future.") + two CTAs ("Explore AI Apps" + "Browse 1M+ models"), right with a live screenshot of the platform UI. Below fold: white section with "Trending 🔥 this week" — a three-column live grid (Models / Spaces / Datasets) showing real trending content with download counts, coloured category tags, and actual model names.

**Key patterns:**
- Emoji as primary brand identity element — uniquely approachable in a technical space
- Live trending content on the homepage — the site is a window into the community, not a brochure
- Platform UI screenshot as hero right-panel — shows the depth of the repository without copy
- "Browse 1M+ models" as a CTA — the scale number is the value proposition

**Takeaway:** HuggingFace's design is community-first — the trending grid replaces the typical feature section, making the homepage feel like a living community hub rather than a static marketing page.

---
## [palantir.com](https://www.palantir.com/)
**Folder:** `5_enterprise_refs`
**Screenshots:** `palantir_top_1.png`, `palantir_scroll_1.png`
**Note:** 6 video elements — hero is likely video-driven; screenshots show only the static layer.

**Palette:** White body background. The hero is dominated by a full-screen dark laptop mockup displaying their AIP dashboard — a dense, colourful dark-mode UI (purple, blue, yellow data panels). The stark contrast of the white page with the dark laptop device create a product-as-hero approach. No brand accent colour in the chrome — the UI colours inside the mock do all the visual work.

**Type:** Alliance No.1 and Alliance No.2 — a pair of custom/exclusive grotesque typefaces (used by Palantir across all brand touchpoints). Clean, authoritative, slightly condensed. The headline "AI-Powered Automation for Every Decision" is set in white directly over the laptop screen at a readable scale. Very minimal typographic hierarchy.

**Animation:** 6 video elements (likely platform capability demos cycling in the background). CSS only otherwise. No GSAP, no canvas.

**Layout:** Near-full-viewport laptop mockup hero with minimal surrounding chrome — wordmark top-left, single "Get Started" CTA top-right, no nav links. The product UI IS the page. Scroll reveals a horizontal tab strip of use-case categories (ShipOS, Systems Migration, DevCon, Chain Reaction etc. — all US defence/government programme names), then a full-bleed editorial card: "SHIPOS — Rebuilding American Sea Power" over aerial naval photography.

**Key patterns:**
- Wordmark-only nav with a single CTA — maximum confidence, no feature menu needed
- Government programme names as product navigation — direct targeting of defence buyers
- Full-bleed programme photography (naval vessels) as content cards — cinematic, not corporate
- Alliance typeface as locked brand asset across all touchpoints

**Takeaway:** Palantir's site is built for a specific audience (defence/government decision-makers) and makes zero concessions to general accessibility — the programme-name navigation and naval photography are deliberate insider signals.

---
## [databricks.com](https://www.databricks.com/)
**Folder:** `5_enterprise_refs`
**Screenshots:** `databricks_top_1.png`, `databricks_scroll_1.png`

**Palette:** White/transparent body. Red (`~#FF3621`) as the primary brand accent — used for the "Try Databricks" CTA, the conference branding (Data+AI Summit), and inline highlights. Text dark near-black. The scroll section introduces a deep teal/dark navy background for the platform overview. The red-on-white then white-on-teal palette is decisive and enterprise-standard.

**Type:** DM Sans (a clean, contemporary humanist sans with wide adoption in enterprise SaaS) and DM Mono for code snippets. DM Sans is neutral and highly readable at all sizes — no personality trade-offs. Section labels appear in spaced monospace caps ("THE DATABRICKS PLATFORM").

**Animation:** No GSAP, no canvas, no video — a notably lightweight site for an enterprise platform of this scale. CSS-only.

**Layout:** Split hero: left white with left-aligned headline ("The database your AI agents deserve" — a Lakebase product focus) + two CTAs, right a product UI panel (the Databricks dashboard). Below fold: horizontal customer logo strip with "TRUSTED BY DATA + AI TEAMS" label, then a large dark teal section promoting the Data+AI Summit conference with bold red graphic branding. Then a product platform overview section with rounded pill navigation tabs.

**Key patterns:**
- Product-specific hero (Lakebase) rather than the full platform — targets a current campaign priority
- Conference promotion given equal visual weight to the hero — ecosystem signal
- Pill-shaped tab navigation for platform overview — keeps the page scannable across multiple products
- DM Sans + red across the enterprise signals competence without flair

**Takeaway:** Databricks is enterprise-conventional — clean DM Sans, red accent, trust strips, conference promotions. The design is in service of sales motion, not aesthetic differentiation.

---
## [snowflake.com](https://www.snowflake.com/en/)
**Folder:** `5_enterprise_refs`
**Screenshots:** `snowflake_top_1.png`, `snowflake_scroll_1.png`

**Palette:** Dark-ish body with a white upper section and near-black lower hero panel. Snowflake teal/cyan (`~#29B5E8`) as the brand accent — used for the "+" in "CODE + WORK", CTA buttons, and inline links. Text dark on white sections, white on dark. The teal is distinctive in the enterprise space — cool and technical.

**Type:** Texta (a rounded geometric display sans, proprietary feel) for the large "CODE • WORK" hero type — set at extreme scale. Lato for body and nav. The "CODE + WORK" headline uses the teal "+" as a brand accent embedded in the type itself. Below fold, a section uses "SIMPLIFY ENTERPRISE DATA AND AI" in wide-tracked spaced caps with a muted background.

**Animation:** GSAP present — likely powering scroll-linked transitions. Mapbox GL integration (`mapboxgl-spin` keyframe) suggests a world map component somewhere on the page. The `slow-scroll` keyframe suggests parallax. No canvas visible in the initial viewport.

**Layout:** Top announcement bar, then light-background nav, then dark hero with the "CODE + WORK" large type + subheadline + two CTAs, with a dark terminal/IDE product mock below showing Cortex Code agent. Scroll reveals a light grey section with an event promotion card and then a platform overview section with a split layout and pill tabs.

**Key patterns:**
- "CODE + WORK" headline at display scale — the "+" creates a visual pause and brand moment in the type
- Dark product mock in a dark hero section — product-as-hero without contrast confusion
- GSAP + Mapbox suggests a world map or network visualisation deeper in the page
- Teal "+" embedded in display type — brand colour used as a typographic element

**Takeaway:** Snowflake's "CODE + WORK" hero demonstrates how a single typographic device (the coloured operator) can carry an entire brand moment — simple, memorable, and instantly reusable across materials.

---
## [scale.com](https://scale.com/)
**Folder:** `5_enterprise_refs`
**Screenshots:** `scale_top_1.png`, `scale_scroll_1.png`

**Palette:** True near-black body `rgb(2,2,2)`. Text in muted grey-white — not pure white, which would be harsh. The sole decorative element is a 3D abstract geometric composition (overlapping triangular planes in muted purple, slate, and teal gradients) floating on the right side of the hero — the only colour on the page. CTAs are ghost pills (dark border, transparent fill). No vivid brand accent colour at all.

**Type:** Aeonik (a clean contemporary geometric grotesque, premium-feeling) for the headline, with Geist and Inter for body and UI. The hero headline "Breakthrough AI from Data to Deployment" is very large and set in muted grey-white — deliberately low contrast on black, creating an understated, confident effect. It reads as a whisper at scale rather than a shout.

**Animation:** Canvas element + 3 video elements (non-rendering in headless). The geometric shape is likely animated or rotating. CSS includes `fadeIn/Out` and dialog animations.

**Layout:** Pure black full-viewport hero with left-aligned large headline, two-line subhead, ghost CTA buttons, and the geometric shape right. Vast empty space — the black is the design. Scroll reveals more black with a spaced centred attribution line ("Scale works with Generative AI Companies, U.S. Government Agencies & Enterprises") then a four-logo strip: US Army, US Air Force, Defense Innovation Unit, CDAO — heavy government/defence customer signal. Then a centred section: "AI FOR THE ENTERPRISE — Full-Stack AI Solutions."

**Key patterns:**
- Muted grey-white headline on black — confidence through near-invisibility; legible but not screaming
- Abstract 3D geometric shape as the only colour — decorative without being representational
- Defence customer logos (Army, Air Force, DIU, CDAO) as the first trust strip — targets the same buyers as Palantir
- Ghost pill CTAs on black — consistent with the "we don't need to convince you" tone

**Takeaway:** Scale's design is the quietest in this collection — near-invisible type on black, ghost buttons, abstract geometry. The restraint is a deliberate signal of institutional gravity: companies that work with the US military don't need to shout.
