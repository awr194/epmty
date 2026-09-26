"""Data sources for the Czech Business Model Radar.

Two kinds of entries:
  * CURATED  - 500 proven small-business / micro-SaaS models from 60+ countries.
               The first 100 (this file + curated_more.py) carry hand-written Czech
               segments and competitors; the 400 in catalog/ carry Czech ratings
               and, where known, Czech competitors - otherwise a category-level
               Czech landscape is filled in and labelled as such.
  * LIVE     - fetched on demand from Hacker News "Show HN" (Algolia API) and
               the Product Hunt RSS feed. These get heuristic Czech hints.

Revenue figures are approximate, publicly self-reported numbers (founder
posts, open dashboards, interviews). They change often - treat them as an
order-of-magnitude signal of traction, not as audited data.
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from typing import Literal, Optional

import pandas as pd
import requests
from pydantic import BaseModel, Field

from catalog import GLOBAL_MODELS
from cz_enrichment import Incumbent, ModelType, Seasonality, apply_cz_defaults
from curated_more import MORE_MODELS

# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #

CATEGORIES = [
    "Dev & Productivity Tools",
    "Marketing & Growth",
    "E-commerce Add-ons",
    "Creator Economy",
    "Local Services",
    "AI Tools",
    "Finance & Admin",
    "Hospitality & Gastro",
    "Communities & Marketplaces",
    "D2C & Subscriptions",
    "Health & Wellness",
    "Education & EdTech",
]


class Competitor(BaseModel):
    name: str
    url: str = ""
    note: str = ""
    local: bool = True  # Czech/CEE player vs. international


class BusinessModel(BaseModel):
    id: str
    name: str
    url: str
    category: str
    niche: str
    revenue_model: str
    mrr_usd: Optional[int] = None  # approx. self-reported MRR, None if unknown
    revenue_note: str = ""
    problem: str
    tech_stack: list[str] = Field(default_factory=list)
    source: str = "Curated"
    country: str = "Unknown"  # country of origin of the proven model

    # --- Czech adaptation hints (drive the offline engine) --------------- #
    audience: str = "B2B"  # "B2B" | "B2C"
    price_usd: float = 29.0  # typical international monthly price point
    price_czk_override: Optional[int] = None  # use when the local price is known
    cz_sam: int = 5000  # rough serviceable market in CZ (number of customers)
    demand: int = 3  # 1-5 local demand
    competition: int = 3  # 1-5 intensity of local competition
    complexity: int = 3  # 1-5 build/ops complexity
    regulatory: int = 1  # 1-5 regulatory burden in CZ
    moat: int = 3  # 1-5 advantage from Czech-specific localisation
    cogs_pct: float = 0.0  # variable cost share of revenue (food, GPU, SMS...)
    cz_segments: list[str] = Field(default_factory=list)
    cz_competitors: list[Competitor] = Field(default_factory=list)
    cz_notes: str = ""

    # --- Czech enrichment (cz_enrichment.py; overlay data/cz_enrichment.json) --- #
    # All optional with defaults so older records and saved objects keep working.
    model_type: Optional[ModelType] = None
    local_incumbents: list[Incumbent] = Field(default_factory=list)
    legal_complexity: Optional[int] = None  # 1-5; falls back to `regulatory`
    required_integrations: list[str] = Field(default_factory=list)
    seasonality: Seasonality = Field(default_factory=Seasonality)
    czech_support_required: Optional[bool] = None
    price_includes_vat: Optional[bool] = None  # B2C prices incl. 21% DPH, B2B excl.
    target_nace: list[str] = Field(default_factory=list)  # CZ-NACE codes for SAM sizing
    sam_estimate: Optional[int] = None  # firms/households in CZ
    sam_source: str = ""
    sam_segment: str = "total"  # NACE segment: total | natural_persons | legal_entities | with_employees
    take_rate: Optional[float] = None  # marketplaces: share of GMV kept
    gmv_estimate: Optional[int] = None  # marketplaces: monthly GMV at month 12, CZK
    needs_rethink_for_cz: bool = False
    # Is the original product already offered in Czechia? yes | likely | no | unknown (step 10.1)
    original_available_in_cz: Literal["yes", "likely", "no", "unknown"] = "unknown"
    original_cz_evidence: list[dict] = Field(default_factory=list)  # {"signal": code, "value": found text}
    original_cz_source: str = ""  # "site check YYYY-MM-DD" or the manual source
    inferred_fields: list[str] = Field(default_factory=list)  # fields filled by rules, not verified


def _id(name: str, source: str) -> str:
    return hashlib.md5(f"{source}:{name}".encode()).hexdigest()[:10]


def _c(name: str, url: str = "", note: str = "", local: bool = True) -> Competitor:
    return Competitor(name=name, url=url, note=note, local=local)


# --------------------------------------------------------------------------- #
# Curated database (first 30 models; 70 more live in curated_more.py)
# --------------------------------------------------------------------------- #

_RAW: list[dict] = [
    dict(
        name="Plausible Analytics", url="https://plausible.io", category="Dev & Productivity Tools",
        niche="Privacy-first, cookie-less web analytics", revenue_model="Subscription SaaS (tiered by pageviews)",
        mrr_usd=250_000, revenue_note="~$3M ARR per founders' public posts",
        problem="Google Analytics is complex and needs cookie consent; site owners want simple GDPR-friendly stats.",
        tech_stack=["Elixir", "Phoenix", "ClickHouse", "PostgreSQL"],
        audience="B2B", price_usd=14, cz_sam=60_000, demand=3, competition=3, complexity=4, regulatory=1, moat=3,
        cz_segments=["Czech web agencies", "Shoptet & Upgates merchants", "Municipal & public-sector websites"],
        cz_competitors=[_c("Google Analytics 4", "https://analytics.google.com", "Free default everywhere", False),
                        _c("Smartlook", "https://www.smartlook.com", "Czech-founded session-recording analytics"),
                        _c("Matomo", "https://matomo.org", "Self-hosted option used by public sector", False)],
        cz_notes="Czech cookie law is opt-in since 2022, so cookie-less analytics has a real compliance angle.",
    ),
    dict(
        name="Carrd", url="https://carrd.co", category="Creator Economy",
        niche="One-page website builder", revenue_model="Annual subscription ($19-49/yr)",
        mrr_usd=150_000, revenue_note="Founder reported $1M+ ARR; figure approximate",
        problem="People need a simple landing page / link-in-bio without learning a full website builder.",
        tech_stack=["PHP", "Vanilla JS", "Custom hosting"],
        audience="B2C", price_usd=2, cz_sam=80_000, demand=2, competition=5, complexity=3, regulatory=1, moat=1,
        cz_segments=["Czech freelancers (OSVČ) needing a vizitka web", "Event organisers", "Students & creators"],
        cz_competitors=[_c("Webnode", "https://www.webnode.cz", "Brno-based builder, strong CZ brand"),
                        _c("Mioweb", "https://www.mioweb.cz", "Czech builder popular with coaches & course creators"),
                        _c("Wix", "https://www.wix.com", "Localised in Czech", False)],
    ),
    dict(
        name="Nomad List", url="https://nomadlist.com", category="Communities & Marketplaces",
        niche="Paid community & city data for remote workers", revenue_model="One-time / annual membership",
        mrr_usd=45_000, revenue_note="Approximate, from founder's open revenue posts",
        problem="Remote workers need trusted info on cities (cost, internet, safety) and a community to meet people.",
        tech_stack=["PHP", "jQuery", "SQLite"],
        audience="B2C", price_usd=10, cz_sam=40_000, demand=3, competition=3, complexity=2, regulatory=1, moat=3,
        cz_segments=["Prague expats & digital nomads", "Relocating IT specialists", "Erasmus/international students"],
        cz_competitors=[_c("Expats.cz", "https://www.expats.cz", "Established Prague expat portal"),
                        _c("InterNations", "https://www.internations.org", "Global expat network", False),
                        _c("Facebook expat groups", "", "Free, fragmented, noisy")],
        cz_notes="Czechia runs a digital-nomad scheme for selected IT professionals (verify current terms).",
    ),
    dict(
        name="Photo AI", url="https://photoai.com", category="AI Tools",
        niche="AI-generated photos of yourself / models", revenue_model="Monthly subscription",
        mrr_usd=130_000, revenue_note="Founder's open dashboard, fluctuates",
        problem="Getting professional photos requires a photographer, studio and time.",
        tech_stack=["PHP", "Replicate", "Stable Diffusion / Flux"],
        audience="B2B", price_usd=19, cz_sam=25_000, demand=3, competition=3, complexity=4, cogs_pct=0.2, regulatory=2, moat=2,
        cz_segments=["Shoptet fashion e-shops needing model photos", "Small influencers", "Real-estate agents"],
        cz_competitors=[_c("Photo AI / Aragon / similar", "", "Global tools already usable from CZ", False),
                        _c("Local photo studios", "", "Human alternative, 3-10k CZK per shoot")],
        cz_notes="Angle: product-on-model photos for Czech fashion e-shops, invoiced in CZK with VAT.",
    ),
    dict(
        name="HeadshotPro", url="https://www.headshotpro.com", category="AI Tools",
        niche="AI professional headshots", revenue_model="One-time purchase ($29-59)",
        mrr_usd=300_000, revenue_note="Founder-reported peak; approximate",
        problem="Professional headshots for LinkedIn/CVs are expensive and inconvenient.",
        tech_stack=["Next.js", "Python", "Fine-tuned diffusion models"],
        audience="B2C", price_usd=10, cz_sam=60_000, demand=3, competition=3, complexity=3, cogs_pct=0.15, regulatory=2, moat=2,
        cz_segments=["Job seekers on Jobs.cz / LinkedIn", "Corporate HR teams (team pages)", "Realitní makléři"],
        cz_competitors=[_c("HeadshotPro / Aragon", "", "English-only global players", False),
                        _c("Local photographers", "", "1.5-4k CZK per session")],
        cz_notes="Monthly figure models a steady flow of one-time purchases. B2B team packages for Czech HR are the stronger play.",
    ),
    dict(
        name="Bannerbear", url="https://www.bannerbear.com", category="Marketing & Growth",
        niche="API for auto-generating images & videos", revenue_model="Subscription SaaS (API credits)",
        mrr_usd=50_000, revenue_note="Founder's public revenue updates",
        problem="Marketing teams need hundreds of on-brand image variants (social, ads, product feeds).",
        tech_stack=["Ruby on Rails", "Headless Chrome", "AWS"],
        audience="B2B", price_usd=49, cz_sam=6_000, demand=2, competition=3, complexity=4, cogs_pct=0.1, regulatory=1, moat=2,
        cz_segments=["Performance agencies running Sklik & Meta ads", "E-shops with Heureka/Zboží feeds"],
        cz_competitors=[_c("Canva", "https://www.canva.com", "Localised, huge brand", False),
                        _c("Placid", "https://placid.app", "Direct competitor", False)],
    ),
    dict(
        name="Senja", url="https://senja.io", category="Marketing & Growth",
        niche="Collect & display customer testimonials", revenue_model="Subscription SaaS",
        mrr_usd=80_000, revenue_note="~$1M ARR reported by founders",
        problem="Businesses struggle to collect social proof and show it on their site.",
        tech_stack=["Next.js", "Supabase", "Vercel"],
        audience="B2B", price_usd=29, cz_sam=30_000, demand=3, competition=4, complexity=2, regulatory=1, moat=2,
        cz_segments=["Coaches & course creators", "Service businesses (clinics, studios)", "B2B agencies"],
        cz_competitors=[_c("Heureka Ověřeno zákazníky", "https://www.heureka.cz", "Dominant e-shop review badge"),
                        _c("Firmy.cz reviews", "https://www.firmy.cz", "Seznam's business directory reviews"),
                        _c("Google Reviews", "", "Free default", False)],
    ),
    dict(
        name="Tally", url="https://tally.so", category="Dev & Productivity Tools",
        niche="Free-first form builder", revenue_model="Freemium subscription",
        mrr_usd=150_000, revenue_note="Belgian bootstrapped team; ARR publicly shared, approximate",
        problem="Typeform is expensive; Google Forms looks bad and is limited.",
        tech_stack=["React", "Node.js", "PostgreSQL"],
        audience="B2B", price_usd=29, cz_sam=40_000, demand=2, competition=4, complexity=3, regulatory=1, moat=1,
        cz_segments=["Schools & NGOs", "Event organisers", "HR teams"],
        cz_competitors=[_c("Survio", "https://www.survio.com", "Brno-based survey tool"),
                        _c("Google Forms", "", "Free default", False),
                        _c("Typeform", "https://www.typeform.com", "", False)],
    ),
    dict(
        name="Transistor.fm", url="https://transistor.fm", category="Creator Economy",
        niche="Podcast hosting & analytics", revenue_model="Subscription SaaS",
        mrr_usd=250_000, revenue_note="~$3M ARR per open founder posts",
        problem="Podcasters and companies need reliable hosting, private podcasts and stats.",
        tech_stack=["Ruby on Rails", "PostgreSQL", "CDN"],
        audience="B2B", price_usd=19, cz_sam=4_000, demand=2, competition=4, complexity=4, regulatory=1, moat=2,
        cz_segments=["Czech independent podcasters", "Companies running internal podcasts", "Media houses"],
        cz_competitors=[_c("Spotify for Creators", "", "Free hosting", False),
                        _c("Buzzsprout", "https://www.buzzsprout.com", "", False)],
    ),
    dict(
        name="Typefully", url="https://typefully.com", category="Creator Economy",
        niche="Writing & scheduling for X / LinkedIn", revenue_model="Subscription SaaS",
        mrr_usd=60_000, revenue_note="Estimate; not officially disclosed",
        problem="Writing and scheduling high-performing social posts is slow.",
        tech_stack=["React", "Python", "OpenAI API"],
        audience="B2B", price_usd=12, cz_sam=15_000, demand=2, competition=4, complexity=2, regulatory=1, moat=2,
        cz_segments=["Czech B2B founders on LinkedIn", "Personal-brand consultants", "Recruiters"],
        cz_competitors=[_c("Buffer / Hootsuite", "", "Localised schedulers", False),
                        _c("Taplio", "https://taplio.com", "LinkedIn-focused", False)],
        cz_notes="LinkedIn is the dominant B2B channel in CZ; X is small. Czech-language AI tone tuning is the moat.",
    ),
    dict(
        name="Judge.me", url="https://judge.me", category="E-commerce Add-ons",
        niche="Product reviews app for Shopify", revenue_model="Freemium app subscription",
        mrr_usd=None, revenue_note="Reported multi-million ARR; exact MRR not public",
        problem="E-shops need photo reviews, review requests and rich snippets.",
        tech_stack=["Ruby on Rails", "Shopify API"],
        audience="B2B", price_usd=15, cz_sam=40_000, demand=3, competition=5, complexity=2, regulatory=1, moat=2,
        cz_segments=["Shoptet merchants", "Upgates merchants", "WooCommerce shops"],
        cz_competitors=[_c("Heureka Ověřeno zákazníky", "https://www.heureka.cz", "De-facto standard trust badge"),
                        _c("Zboží.cz reviews", "https://www.zbozi.cz", "Seznam's comparison engine"),
                        _c("Shoptet built-in reviews", "https://www.shoptet.cz", "Native feature")],
    ),
    dict(
        name="Back-in-Stock Alerts (Shopify app archetype)", url="https://apps.shopify.com/search?q=back%20in%20stock",
        category="E-commerce Add-ons", niche="Out-of-stock notifications & pre-orders",
        revenue_model="App subscription by volume", mrr_usd=30_000,
        revenue_note="Typical for a top-10 app in this Shopify category; archetype estimate",
        problem="Shops lose sales when items are out of stock; no way to capture intent.",
        tech_stack=["Node.js", "Platform API", "Email/SMS gateway"],
        audience="B2B", price_usd=19, cz_sam=40_000, demand=3, competition=2, complexity=2, regulatory=1, moat=3,
        cz_segments=["Shoptet merchants (fashion, cosmetics, supplements)", "Upgates merchants"],
        cz_competitors=[_c("Shoptet Addons marketplace", "https://doplnky.shoptet.cz", "Check existing watchdog add-ons"),
                        _c("Heureka hlídací pes", "https://www.heureka.cz", "Price watchdog on comparison site")],
        cz_notes="Shoptet runs an add-on marketplace with tens of thousands of stores - a ready distribution channel.",
    ),
    dict(
        name="SMS/WhatsApp Cart Recovery (Postscript archetype)", url="https://postscript.io",
        category="E-commerce Add-ons", niche="Abandoned-cart recovery via SMS", revenue_model="Subscription + usage",
        mrr_usd=None, revenue_note="Postscript is VC-backed; many bootstrapped clones earn $10-50k MRR",
        problem="Email recovery open rates are falling; SMS gets read.",
        tech_stack=["Node.js", "SMS gateway API", "Shop webhooks"],
        audience="B2B", price_usd=39, cz_sam=25_000, demand=3, competition=3, complexity=3, cogs_pct=0.25, regulatory=3, moat=3,
        cz_segments=["Shoptet merchants", "Czech D2C brands"],
        cz_competitors=[_c("Ecomail", "https://ecomail.cz", "Czech email + automation, adding SMS"),
                        _c("SmartEmailing", "https://www.smartemailing.cz", "Czech marketing automation"),
                        _c("Czech SMS gateway providers", "", "Commodity sending")],
        cz_notes="Marketing SMS need prior consent under Czech/GDPR rules - build consent capture into checkout.",
    ),
    dict(
        name="Oh Dear", url="https://ohdear.app", category="Dev & Productivity Tools",
        niche="Website uptime, SSL & broken-link monitoring", revenue_model="Subscription SaaS",
        mrr_usd=None, revenue_note="Bootstrapped Belgian duo; revenue not public",
        problem="Agencies need to know before clients do when sites break.",
        tech_stack=["Laravel", "PHP", "Redis"],
        audience="B2B", price_usd=15, cz_sam=5_000, demand=2, competition=4, complexity=3, regulatory=1, moat=1,
        cz_segments=["Czech web agencies", "Shoptet/WordPress freelancers"],
        cz_competitors=[_c("UptimeRobot", "https://uptimerobot.com", "Generous free tier", False),
                        _c("Better Stack", "https://betterstack.com", "", False),
                        _c("Hosting providers (WEDOS, Forpsi)", "", "Bundled basic monitoring")],
    ),
    dict(
        name="Freelancer Invoicing (Invoice Ninja archetype)", url="https://invoiceninja.com",
        category="Finance & Admin", niche="Invoicing & payment reminders for freelancers",
        revenue_model="Freemium subscription", mrr_usd=None, revenue_note="Open-source + hosted; revenue not public",
        problem="Freelancers waste time on invoices and chasing late payments.",
        tech_stack=["Laravel", "Flutter"],
        audience="B2B", price_usd=10, cz_sam=300_000, demand=4, competition=5, complexity=3, regulatory=3, moat=2,
        cz_segments=["Czech OSVČ", "Small s.r.o. companies"],
        cz_competitors=[_c("Fakturoid", "https://www.fakturoid.cz", "Czech market leader for freelancers"),
                        _c("iDoklad", "https://www.idoklad.cz", "Free tier, backed by Solitea"),
                        _c("Vyfakturuj.cz", "https://www.vyfakturuj.cz", "Czech invoicing tool")],
        cz_notes="Saturated locally - only viable with a sharp niche (e.g., English-speaking foreign OSVČ in Prague).",
    ),
    dict(
        name="Receipt & Expense Capture (Dext archetype)", url="https://dext.com",
        category="Finance & Admin", niche="OCR receipts & supplier invoices into accounting",
        revenue_model="Subscription per client/company", mrr_usd=None, revenue_note="Dext is large; niche clones earn $10-100k MRR",
        problem="Collecting receipts and retyping invoices into accounting software is tedious.",
        tech_stack=["Python", "OCR / LLM extraction", "Accounting APIs"],
        audience="B2B", price_usd=25, cz_sam=80_000, demand=3, competition=4, complexity=4, regulatory=2, moat=3,
        cz_segments=["Small s.r.o. companies", "Czech accounting firms (účetní)", "OSVČ with real expenses"],
        cz_competitors=[_c("Digitoo", "https://www.digitoo.cz", "Czech AI invoice extraction"),
                        _c("Rossum", "https://rossum.ai", "Prague-founded enterprise document AI"),
                        _c("Pohoda / Money S3 add-ons", "", "Incumbent accounting software ecosystems")],
        cz_notes="OSVČ on paušální daň don't track expenses - target s.r.o. and accountants instead.",
    ),
    dict(
        name="Salon Booking with No-show Deposits (Fresha archetype)", url="https://www.fresha.com",
        category="Local Services", niche="Online booking for hair/beauty salons", revenue_model="Subscription + payment fees",
        mrr_usd=None, revenue_note="Category proven by Fresha/Booksy; bootstrapped niche tools at $10-50k MRR",
        problem="Salons lose money on no-shows and spend hours on phone bookings.",
        tech_stack=["React Native", "Node.js", "Stripe"],
        audience="B2B", price_usd=30, cz_sam=30_000, demand=4, competition=5, complexity=3, regulatory=1, moat=2,
        cz_segments=["Hair & beauty salons", "Barbershops", "Physiotherapists & massage studios"],
        cz_competitors=[_c("Reservio", "https://www.reservio.cz", "Brno-based booking leader"),
                        _c("Reservanto", "https://www.reservanto.cz", "Czech booking system"),
                        _c("Bookio", "https://www.bookio.com", "Slovak, active in CZ"),
                        _c("Booksy", "https://booksy.com", "", False)],
    ),
    dict(
        name="QR Table Ordering & Pay (Sunday/Mr Yum archetype)", url="https://sundayapp.com",
        category="Hospitality & Gastro", niche="Scan-to-order and pay at the table", revenue_model="Per-transaction fee + SaaS",
        mrr_usd=None, revenue_note="VC-backed category leaders; proven willingness to pay",
        problem="Guests wait for the bill; restaurants are understaffed.",
        tech_stack=["Next.js", "POS integrations", "Payment gateway"],
        audience="B2B", price_usd=60, cz_sam=12_000, demand=3, competition=4, complexity=4, regulatory=2, moat=2,
        cz_segments=["Prague restaurants & cafés", "Beer gardens & festivals", "Hotel bars"],
        cz_competitors=[_c("Qerko", "https://www.qerko.com", "Czech pay-at-table leader"),
                        _c("Storyous", "https://www.storyous.com", "Czech POS"),
                        _c("Dotykačka", "https://www.dotykacka.cz", "Czech POS with ordering modules")],
    ),
    dict(
        name="AI Multilingual Menu & Allergen Labels", url="https://www.menutiger.com",
        category="Hospitality & Gastro", niche="Translated digital menus with EU allergen coding",
        revenue_model="Subscription per venue", mrr_usd=20_000, revenue_note="Archetype estimate based on QR-menu tools",
        problem="Tourist-heavy restaurants need accurate menus in 5+ languages and legally required allergen info.",
        tech_stack=["Next.js", "LLM translation", "QR codes"],
        audience="B2B", price_usd=25, cz_sam=15_000, demand=4, competition=2, complexity=2, regulatory=2, moat=4,
        cz_segments=["Prague 1 & 2 restaurants", "Český Krumlov / Karlovy Vary tourist venues", "Hotel restaurants"],
        cz_competitors=[_c("Printed menus via local print shops", "", "Status quo"),
                        _c("POS menu modules (Dotykačka, Storyous)", "", "Basic, rarely multilingual"),
                        _c("Generic QR menu tools", "", "Weak Czech allergen handling", False)],
        cz_notes="EU Reg. 1169/2011 requires the 14 allergens to be declared; Prague has millions of foreign visitors yearly.",
    ),
    dict(
        name="Short-term Rental Host Automation (Hospitable archetype)", url="https://hospitable.com",
        category="Hospitality & Gastro", niche="Guest messaging, cleaning & pricing automation for Airbnb hosts",
        revenue_model="Subscription per listing", mrr_usd=None, revenue_note="Hospitable reported 8-figure ARR; niche clones smaller",
        problem="Hosts juggling several listings drown in guest messages and turnover logistics.",
        tech_stack=["Node.js", "Airbnb/Booking APIs", "LLM messaging"],
        audience="B2B", price_usd=40, cz_sam=8_000, demand=4, competition=3, complexity=4, regulatory=4, moat=3,
        cz_segments=["Prague Airbnb hosts & co-hosts", "Small apartment-management companies"],
        cz_competitors=[_c("Smoobu", "https://www.smoobu.com", "German channel manager, strong in CEE", False),
                        _c("Hostaway", "https://www.hostaway.com", "", False),
                        _c("Local property managers", "", "Full-service alternative")],
        cz_notes="Short-term rentals face new registration & reporting obligations (eTurista, city fees) - verify current rules; compliance automation is the local wedge.",
    ),
    dict(
        name="Meal-Prep Subscription (krabičková dieta)", url="https://www.factor75.com",
        category="Local Services", niche="Daily delivered calorie-counted meal boxes", revenue_model="Weekly/monthly subscription",
        mrr_usd=None, revenue_note="Factor/HelloFresh prove demand; local boutiques run 1-10M CZK/month",
        problem="Busy professionals want healthy portion-controlled food without cooking.",
        tech_stack=["Shoptet/WooCommerce", "Route planning", "Kitchen ops"],
        audience="B2C", price_usd=500, price_czk_override=11_000, cz_sam=6_000, demand=4, competition=5, complexity=5,
        cogs_pct=0.6, regulatory=3, moat=3,
        cz_segments=["Prague professionals", "Fitness enthusiasts", "Parents on maternity leave"],
        cz_competitors=[_c("Nutric", "https://www.nutric.cz", "Large krabičková dieta brand"),
                        _c("Zdravé stravování", "https://www.zdravestravovani.cz", "Established national player"),
                        _c("Dozens of local kitchens", "", "Very crowded, price-competitive")],
        cz_notes="Czechia is one of Europe's biggest meal-box markets. Needs a hygiene-approved kitchen (KHS).",
    ),
    dict(
        name="Pet Sitting & Dog Walking Marketplace (Rover archetype)", url="https://www.rover.com",
        category="Communities & Marketplaces", niche="Trusted local pet sitters", revenue_model="Commission 15-20% per booking",
        mrr_usd=None, revenue_note="Rover proved the model; local marketplaces start at a few $k MRR",
        problem="Pet owners can't find vetted, insured sitters on short notice.",
        tech_stack=["Next.js", "Stripe Connect", "Maps API"],
        audience="B2C", price_usd=20, price_czk_override=450, cz_sam=60_000, demand=3, competition=2, complexity=3,
        regulatory=2, moat=3,
        cz_segments=["Prague dog owners", "Expats travelling home", "Students as sitters"],
        cz_competitors=[_c("Bazoš / Facebook groups", "https://www.bazos.cz", "Informal, no trust layer"),
                        _c("Hotels for dogs / psí hotely", "", "Offline alternative"),
                        _c("Rover", "https://www.rover.com", "Not operating in CZ (verify)", False)],
        cz_notes="Price shown is commission per booking-month per active owner. Czechia has one of the highest dog-ownership rates in the EU.",
    ),
    dict(
        name="RemoteOK", url="https://remoteok.com", category="Communities & Marketplaces",
        niche="Niche job board", revenue_model="Pay-per-job-post",
        mrr_usd=40_000, revenue_note="Founder's open revenue, fluctuates with hiring market",
        problem="Companies want targeted candidates; generic boards are noisy.",
        tech_stack=["PHP", "jQuery", "SQLite"],
        audience="B2B", price_usd=150, cz_sam=3_000, demand=3, competition=4, complexity=2, regulatory=1, moat=3,
        cz_segments=["Companies hiring English-speakers in Prague", "Startups", "Shared-service centres"],
        cz_competitors=[_c("Jobs.cz", "https://www.jobs.cz", "Market leader (Alma Career)"),
                        _c("StartupJobs.cz", "https://www.startupjobs.cz", "Startup niche"),
                        _c("LinkedIn Jobs", "", "", False)],
        cz_notes="Price is per job post; a niche angle (English-only jobs, Ukrainian-speaking roles, gastro) is required.",
    ),
    dict(
        name="Chatbase", url="https://www.chatbase.co", category="AI Tools",
        niche="AI support chatbot trained on your docs", revenue_model="Subscription SaaS",
        mrr_usd=400_000, revenue_note="Founder-reported; grew very fast, approximate",
        problem="Small businesses can't staff 24/7 support; FAQs go unread.",
        tech_stack=["Next.js", "Supabase", "LLM APIs", "Vector search"],
        audience="B2B", price_usd=40, cz_sam=30_000, demand=4, competition=3, complexity=3, cogs_pct=0.15, regulatory=2, moat=3,
        cz_segments=["Shoptet e-shops", "Clinics & service businesses", "Municipal offices"],
        cz_competitors=[_c("Smartsupp", "https://www.smartsupp.com", "Brno-based live chat, adding AI"),
                        _c("Daktela", "https://www.daktela.com", "Czech contact-centre software"),
                        _c("Intercom / Tidio", "", "", False)],
        cz_notes="Native-quality Czech replies and Shoptet order-status integration are the differentiators.",
    ),
    dict(
        name="ScreenshotOne", url="https://screenshotone.com", category="Dev & Productivity Tools",
        niche="Screenshot & HTML-to-image API", revenue_model="Usage-based subscription",
        mrr_usd=25_000, revenue_note="Solo founder's public updates, approximate",
        problem="Developers need reliable headless-browser rendering without running infra.",
        tech_stack=["Go", "Headless Chrome", "Kubernetes"],
        audience="B2B", price_usd=17, cz_sam=1_500, demand=1, competition=4, complexity=4, cogs_pct=0.1, regulatory=1, moat=1,
        cz_segments=["Czech dev agencies", "SaaS startups"],
        cz_competitors=[_c("Global API vendors", "", "Location-independent market", False)],
        cz_notes="Global product - build from Prague, sell worldwide; Czech market alone is tiny.",
    ),
    dict(
        name="Newsletter Sponsorship Marketplace (Paved archetype)", url="https://www.paved.com",
        category="Marketing & Growth", niche="Connect advertisers with newsletters", revenue_model="Commission on sponsorships",
        mrr_usd=None, revenue_note="Paved acquired; category proven in US",
        problem="Newsletter owners struggle to find sponsors; brands struggle to buy newsletter ads.",
        tech_stack=["Rails", "Stripe Connect"],
        audience="B2B", price_usd=100, cz_sam=500, demand=1, competition=2, complexity=3, regulatory=1, moat=2,
        cz_segments=["Czech newsletter creators", "B2B brands"],
        cz_competitors=[_c("Direct deals / agencies", "", "Market too small for marketplace dynamics")],
    ),
    dict(
        name="Podia", url="https://www.podia.com", category="Creator Economy",
        niche="All-in-one courses, memberships & downloads", revenue_model="Subscription SaaS",
        mrr_usd=None, revenue_note="Bootstrapped to multi-million ARR per founder interviews",
        problem="Creators stitch together 5 tools to sell courses and memberships.",
        tech_stack=["Ruby on Rails", "Stripe"],
        audience="B2B", price_usd=39, cz_sam=8_000, demand=3, competition=4, complexity=3, regulatory=2, moat=3,
        cz_segments=["Czech coaches & trainers", "Yoga/fitness instructors", "Language teachers"],
        cz_competitors=[_c("Mioweb", "https://www.mioweb.cz", "Czech builder with membership features"),
                        _c("Seduo", "https://www.seduo.cz", "Czech e-learning marketplace"),
                        _c("Kajabi", "https://kajabi.com", "", False)],
        cz_notes="Must issue Czech invoices (IČO/DIČ), handle VAT OSS for EU buyers, and integrate GoPay/Comgate.",
    ),
    dict(
        name="Wedding Website & RSVP (Joy archetype)", url="https://withjoy.com",
        category="Creator Economy", niche="Wedding sites, RSVP and gift registry", revenue_model="Freemium + registry commission",
        mrr_usd=None, revenue_note="VC-backed category; bootstrapped regional clones common",
        problem="Couples juggle spreadsheets for RSVPs, dietary needs and seating.",
        tech_stack=["Next.js", "Firebase"],
        audience="B2C", price_usd=15, price_czk_override=390, cz_sam=45_000, demand=2, competition=3, complexity=2,
        regulatory=1, moat=3,
        cz_segments=["Czech couples (~45k weddings/yr)", "Wedding planners", "Wedding venues"],
        cz_competitors=[_c("Mojesvatba.cz", "https://www.mojesvatba.cz", "Czech wedding portal"),
                        _c("Webnode templates", "https://www.webnode.cz", "DIY option")],
        cz_notes="Monthly figure assumes ~5-month usage per couple; seasonal (May-September peak).",
    ),
    dict(
        name="Public Tender Alerts for SMEs (GovSpend archetype)", url="https://govspend.com",
        category="Finance & Admin", niche="Matching public-procurement tenders to small suppliers",
        revenue_model="Subscription SaaS", mrr_usd=None, revenue_note="US category leader is PE-backed; EU clones bootstrapped",
        problem="SMEs miss relevant public tenders buried in procurement portals.",
        tech_stack=["Python", "Scrapers", "LLM classification", "PostgreSQL"],
        audience="B2B", price_usd=60, cz_sam=15_000, demand=4, competition=3, complexity=3, regulatory=1, moat=5,
        cz_segments=["Construction & facility SMEs", "IT suppliers to municipalities", "Consultancies"],
        cz_competitors=[_c("Hlídač státu", "https://www.hlidacstatu.cz", "Free transparency data (non-commercial focus)"),
                        _c("NEN / ISVZ", "https://nen.nipez.cz", "Official procurement portals - raw data"),
                        _c("Existing paid tender-alert services", "", "Several exist - verify features & pricing")],
        cz_notes="Czech public procurement data is open; LLM matching + Czech-language summaries is a genuine local moat.",
    ),
    dict(
        name="Accountant-Client Document Portal (TaxDome archetype)", url="https://taxdome.com",
        category="Finance & Admin", niche="Client portal, document requests & reminders for accounting firms",
        revenue_model="Subscription per seat", mrr_usd=None, revenue_note="TaxDome scaled quickly; small-firm niche is underserved in CEE",
        problem="Accountants chase clients by email for bank statements and receipts every month.",
        tech_stack=["Laravel", "Vue", "S3", "Bank APIs"],
        audience="B2B", price_usd=35, cz_sam=12_000, demand=4, competition=3, complexity=3, regulatory=2, moat=4,
        cz_segments=["Small accounting firms (1-10 účetní)", "Tax advisers", "Payroll bureaus"],
        cz_competitors=[_c("Pohoda / Money S3 ecosystems", "", "Core accounting, weak client portals"),
                        _c("Fakturoid / iDoklad accountant access", "", "Partial overlap"),
                        _c("Email + Google Drive", "", "Status quo")],
        cz_notes="Monthly DPH (VAT) and kontrolní hlášení deadlines create recurring document-chasing pain.",
    ),
]


def _from_compact(row: dict) -> dict:
    """curated_more.py stores competitors as (name, url, note, local) tuples."""
    row = dict(row)
    row["cz_competitors"] = [_c(*c) for c in row.get("cz_competitors", [])]
    return row


# Country of origin for the first 100 hand-curated models ("Global / remote" when a
# company is remote-first or its home base is ambiguous).
_ORIGIN = {
    "Plausible Analytics": "Estonia", "Carrd": "USA", "Nomad List": "Netherlands", "Photo AI": "Netherlands",
    "HeadshotPro": "Netherlands", "Bannerbear": "Global / remote", "Senja": "Global / remote", "Tally": "Belgium",
    "Transistor.fm": "USA", "Typefully": "Italy", "Judge.me": "Global / remote",
    "Back-in-Stock Alerts (Shopify app archetype)": "Global / remote",
    "SMS/WhatsApp Cart Recovery (Postscript archetype)": "USA", "Oh Dear": "Belgium",
    "Freelancer Invoicing (Invoice Ninja archetype)": "Israel", "Receipt & Expense Capture (Dext archetype)": "UK",
    "Salon Booking with No-show Deposits (Fresha archetype)": "UK",
    "QR Table Ordering & Pay (Sunday/Mr Yum archetype)": "France",
    "AI Multilingual Menu & Allergen Labels": "Global / remote",
    "Short-term Rental Host Automation (Hospitable archetype)": "USA",
    "Meal-Prep Subscription (krabičková dieta)": "USA",
    "Pet Sitting & Dog Walking Marketplace (Rover archetype)": "USA", "RemoteOK": "Netherlands",
    "Chatbase": "Global / remote", "ScreenshotOne": "Ukraine",
    "Newsletter Sponsorship Marketplace (Paved archetype)": "USA", "Podia": "USA",
    "Wedding Website & RSVP (Joy archetype)": "USA", "Public Tender Alerts for SMEs (GovSpend archetype)": "USA",
    "Accountant-Client Document Portal (TaxDome archetype)": "USA",
    "Cookie Consent Manager (Cookiebot archetype)": "Denmark",
    "GDPR & Legal Docs Generator (iubenda archetype)": "Italy",
    "E-signature with Bank Identity (DocuSign archetype)": "USA", "Web Accessibility Checker (EAA compliance)": "UK",
    "Website Translation Layer (Weglot archetype)": "France",
    "Agency Time Tracking & Profitability (Toggl archetype)": "Estonia",
    "Shift Scheduling for Hourly Staff (Deputy archetype)": "Australia", "Instatus": "Global / remote",
    "Kit (formerly ConvertKit)": "USA", "Buffer": "USA", "Review Request Automation (NiceJob archetype)": "Canada",
    "Local SEO for Google & Seznam (BrightLocal archetype)": "UK",
    "Sklik + Google Ads Client Reporting (AgencyAnalytics archetype)": "Canada",
    "Influencer Marketplace (Collabstr archetype)": "North America",
    "AI SEO Content Writer in Czech (Surfer archetype)": "Poland",
    "Product Feed Manager (DataFeedWatch archetype)": "Global / remote",
    "Post-purchase Upsell App (ReConvert archetype)": "Global / remote",
    "Subscriptions for E-shops (Recharge archetype)": "USA",
    "Returns & Complaints Portal (Loop Returns archetype)": "USA",
    "Shipping Label & Carrier Hub (ShipStation archetype)": "USA",
    "Marketplace Connector: Allegro, Kaufland, eMAG (ChannelEngine archetype)": "Netherlands",
    "Competitor Price Monitoring (Prisync archetype)": "Turkey",
    "Gift Cards & Vouchers for E-shops (Rise.ai archetype)": "Israel",
    "B2B Wholesale Portal for Small Brands (Faire/SparkLayer archetype)": "UK",
    "Paid Memberships for Creators (Patreon archetype)": "USA",
    "Digital Product Storefront (Gumroad archetype)": "USA",
    "Paid Community Platform (Skool archetype)": "USA",
    "Czech Transcription & Subtitles (Descript/Rev archetype)": "USA",
    "Event Ticketing for Small Organisers (Eventbrite archetype)": "USA",
    "Client Galleries for Photographers (Pixieset archetype)": "Canada",
    "AI Phone Receptionist in Czech (Smith.ai archetype)": "USA",
    "AI Meeting Notes (Otter/Fireflies archetype)": "USA",
    "AI Legal Research Assistant for Czech Law (Harvey archetype)": "USA",
    "AI Product Descriptions for E-shops (Hypotenuse archetype)": "Singapore",
    "AI Grant & Subsidy Finder (Instrumentl archetype)": "USA", "Interior AI": "Netherlands",
    "AI CV & Cover Letter Builder (Kickresume archetype)": "Slovakia",
    "AI Tutor for Přijímačky & Maturita (Khanmigo archetype)": "USA",
    "Cash-flow Forecasting for SMEs (Float archetype)": "UK",
    "Automated Payment Reminders & Collections (Chaser archetype)": "UK",
    "Payroll for Micro-businesses (Gusto archetype)": "USA",
    "English Tax Returns for Expats in Czechia (TaxScouts archetype)": "UK",
    "Landlord Toolkit (Landlord Studio archetype)": "New Zealand",
    "SVJ Building Management Portal (Buildium archetype)": "USA",
    "Supplier Risk & VAT-Reliability Monitoring (Creditsafe archetype)": "UK",
    "Online s.r.o. Formation & Virtual Office (Stripe Atlas archetype)": "USA",
    "Home Cleaning Marketplace (Helpling archetype)": "Germany",
    "Tradesperson Quote Marketplace (Checkatrade archetype)": "UK",
    "Driving School Management & Theory App": "Global / remote",
    "Kids' Clubs & Camps Booking (ActivityHero archetype)": "USA",
    "Fitness & Yoga Studio Software (Mindbody archetype)": "USA",
    "Tutoring Marketplace (Preply archetype)": "Ukraine",
    "Home-care & Senior Companion Matching (Honor archetype)": "USA", "Mobile Car Detailing Booking": "USA",
    "Laundry Pickup & Delivery (Rinse archetype)": "USA",
    "Restaurant Inventory & Food-cost Control (MarketMan archetype)": "Israel",
    "Online Table Reservations (OpenTable archetype)": "USA",
    "Guesthouse Booking Engine & Channel Manager (Little Hotelier archetype)": "Australia",
    "Office Catering Marketplace (ezCater archetype)": "USA",
    "Airbnb Cleaning Turnover Marketplace (Turno archetype)": "USA",
    "Digital Loyalty Cards for Cafés (Stamp Me archetype)": "Australia",
    "Surplus Food Marketplace (Too Good To Go archetype)": "Denmark", "Craft Beer Subscription Box": "UK",
    "Coworking Day-pass Marketplace (Deskpass archetype)": "USA", "Vinted": "Lithuania",
    "Peer-to-peer Equipment Rental (Fat Llama archetype)": "UK",
    "Private Parking Space Sharing (JustPark archetype)": "UK",
    "Local Freelance Marketplace (Upwork archetype)": "USA",
    "Czech for Foreigners: Exam-prep Marketplace": "Hong Kong",
    "Mid-term Rentals for Students & Expats (HousingAnywhere archetype)": "Netherlands",
}

# Typical Czech players per category, used when a catalogue row has no model-specific
# competitor list. Marked in the note so reports don't present them as verified.
_LANDSCAPE_NOTE = "Category landscape - check relevance for this model"
_CATEGORY_CZ_LANDSCAPE: dict[str, list[tuple]] = {
    "Dev & Productivity Tools": [("Global SaaS alternatives", "", "Dev tools compete globally; few Czech-specific players",
                                  False)],
    "Marketing & Growth": [("Ecomail", "https://ecomail.cz", "", True),
                           ("SmartEmailing", "https://www.smartemailing.cz", "", True),
                           ("Collabim / Marketing Miner", "", "Czech SEO tools", True)],
    "E-commerce Add-ons": [("Shoptet Addons marketplace", "https://doplnky.shoptet.cz", "", True),
                           ("Mergado", "https://www.mergado.com", "", True),
                           ("Heureka", "https://www.heureka.cz", "", True)],
    "Creator Economy": [("HeroHero", "https://herohero.co", "", True),
                        ("Forendors", "https://www.forendors.cz", "", True),
                        ("Mioweb", "https://www.mioweb.cz", "", True)],
    "Local Services": [("Reservio", "https://www.reservio.cz", "", True),
                       ("Firmy.cz", "https://www.firmy.cz", "", True),
                       ("Bazoš", "https://www.bazos.cz", "", True)],
    "AI Tools": [("ChatGPT / Gemini / Claude used directly", "", "General-purpose AI is the main substitute", False)],
    "Finance & Admin": [("Fakturoid", "https://www.fakturoid.cz", "", True),
                        ("iDoklad", "https://www.idoklad.cz", "", True),
                        ("Pohoda (Stormware)", "https://www.stormware.cz", "", True)],
    "Hospitality & Gastro": [("Dotykačka", "https://www.dotykacka.cz", "", True),
                             ("Storyous", "https://www.storyous.com", "", True),
                             ("Qerko", "https://www.qerko.com", "", True),
                             ("Previo", "https://www.previo.cz", "", True)],
    "Communities & Marketplaces": [("Bazoš", "https://www.bazos.cz", "", True),
                                   ("Facebook groups", "", "", False),
                                   ("Expats.cz", "https://www.expats.cz", "", True)],
    "D2C & Subscriptions": [("Rohlík.cz", "https://www.rohlik.cz", "", True),
                            ("Notino", "https://www.notino.cz", "", True),
                            ("Shoptet-based D2C brands", "", "", True)],
    "Health & Wellness": [("Private clinics & health insurers' wellness programmes", "", "", True),
                          ("Global wellness apps", "", "", False)],
    "Education & EdTech": [("Umíme to", "https://www.umimeto.org", "", True),
                           ("Scio", "https://www.scio.cz", "", True),
                           ("Seduo", "https://www.seduo.cz", "", True)],
}


def _with_landscape(row: dict) -> dict:
    row = _from_compact(row)
    if not row["cz_competitors"]:
        row["cz_competitors"] = [_c(n, u, f"{note + ' - ' if note else ''}{_LANDSCAPE_NOTE}", loc)
                                 for n, u, note, loc in _CATEGORY_CZ_LANDSCAPE.get(row["category"], [])]
    if not row["cz_segments"]:
        row["cz_segments"] = list(_CATEGORY_DEFAULT_SEGMENTS.get(row["category"], []))
    return row


def load_curated() -> list[BusinessModel]:
    rows = [dict(r, country=_ORIGIN.get(r["name"], "Unknown")) for r in _RAW + [_from_compact(r) for r in MORE_MODELS]]
    rows += [_with_landscape(r) for r in GLOBAL_MODELS]
    return [BusinessModel(id=_id(r["name"], "Curated"), **apply_cz_defaults(r)) for r in rows]


def with_cz_defaults(m: BusinessModel) -> BusinessModel:
    """Enrich a model built elsewhere (live feeds, user-added ideas)."""
    return BusinessModel(**apply_cz_defaults(m.model_dump()))


# --------------------------------------------------------------------------- #
# Live sources
# --------------------------------------------------------------------------- #

HTTP_TIMEOUT = 8
_HEADERS = {"User-Agent": "CzechBizRadar/1.0 (+streamlit app)"}

# keyword -> category, first match wins
_CATEGORY_KEYWORDS: list[tuple[str, str]] = [
    (r"\b(ai|gpt|llm|agent|diffusion|chatbot)\b", "AI Tools"),
    (r"\b(shop|shopify|e-?commerce|store|cart|checkout)\b", "E-commerce Add-ons"),
    (r"\b(invoice|invoic|tax|accounting|expense|payroll|finance|bank)\b", "Finance & Admin"),
    (r"\b(restaurant|menu|food|hotel|airbnb|travel|booking)\b", "Hospitality & Gastro"),
    (r"\b(marketing|seo|email|newsletter|ads|social|leads?)\b", "Marketing & Growth"),
    (r"\b(creator|podcast|video|course|writer|blog|youtube)\b", "Creator Economy"),
    (r"\b(community|marketplace|job|network|dating)\b", "Communities & Marketplaces"),
    (r"\b(health|medical|doctor|therapy|wellness|fitness|gym|sleep)\b", "Health & Wellness"),
    (r"\b(learn|learning|course|school|student|tutor|education|exam)\b", "Education & EdTech"),
    (r"\b(subscription box|d2c|coffee|snack|cosmetics|skincare)\b", "D2C & Subscriptions"),
    (r"\b(salon|clinic|cleaning|pet|plumber|repair)\b", "Local Services"),
]


def guess_category(text: str) -> str:
    t = text.lower()
    for pattern, cat in _CATEGORY_KEYWORDS:
        if re.search(pattern, t):
            return cat
    return "Dev & Productivity Tools"


_CATEGORY_DEFAULT_SEGMENTS = {
    "AI Tools": ["Czech SMEs adopting AI", "Shoptet merchants"],
    "E-commerce Add-ons": ["Shoptet merchants", "Upgates merchants"],
    "Finance & Admin": ["Czech OSVČ", "Small accounting firms"],
    "Hospitality & Gastro": ["Prague restaurants & cafés", "Short-term rental hosts"],
    "Marketing & Growth": ["Czech digital agencies", "SME marketing teams"],
    "Creator Economy": ["Czech creators & coaches"],
    "Communities & Marketplaces": ["Prague expats", "Local niche communities"],
    "Local Services": ["Prague service businesses"],
    "Dev & Productivity Tools": ["Czech dev agencies", "SaaS startups", "SMB teams"],
    "D2C & Subscriptions": ["Prague & Brno urban consumers", "Online shoppers 25-45", "Gift buyers"],
    "Health & Wellness": ["Health-conscious urban professionals", "Private clinics & therapists", "Employers (wellness benefits)"],
    "Education & EdTech": ["Parents of school pupils", "Students before exams", "Adult learners"],
}


def _live_entry(name: str, url: str, desc: str, source: str, points: int = 0) -> BusinessModel:
    cat = guess_category(f"{name} {desc}")
    local_heavy = cat in {"Hospitality & Gastro", "Local Services", "Finance & Admin"}
    return with_cz_defaults(BusinessModel(
        id=_id(name, source), name=name[:80], url=url, category=cat,
        niche=desc[:120] or "Newly launched product", revenue_model="Unknown (early-stage launch)",
        mrr_usd=None, revenue_note=f"Live launch signal ({points} upvotes)" if points else "Live launch signal",
        problem=desc or "See product page.", tech_stack=[], source=source,
        audience="B2B", price_usd=20, cz_sam=5_000,
        demand=3 if local_heavy else 2, competition=3, complexity=3, regulatory=1,
        moat=3 if local_heavy else 2,
        cz_segments=_CATEGORY_DEFAULT_SEGMENTS.get(cat, []),
        cz_notes="Auto-classified from a live feed - run a Deep-Dive for a proper assessment.",
    ))


def fetch_show_hn(limit: int = 20, min_points: int = 50) -> list[BusinessModel]:
    """Popular recent 'Show HN' launches via the free HN Algolia API."""
    resp = requests.get(
        "https://hn.algolia.com/api/v1/search_by_date",
        params={"tags": "show_hn", "numericFilters": f"points>{min_points}", "hitsPerPage": limit},
        headers=_HEADERS, timeout=HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    out = []
    for hit in resp.json().get("hits", []):
        title = re.sub(r"^Show HN:\s*", "", hit.get("title") or "", flags=re.I)
        parts = re.split(r"\s[–—:-]\s", title, maxsplit=1)
        name, desc = parts[0], (parts[1] if len(parts) > 1 else "")
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        out.append(_live_entry(name.strip(), url, desc.strip(), "Hacker News (Show HN)", hit.get("points") or 0))
    return out


def fetch_product_hunt(limit: int = 20) -> list[BusinessModel]:
    """Latest launches from the public Product Hunt Atom feed."""
    resp = requests.get("https://www.producthunt.com/feed", headers=_HEADERS, timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    for entry in root.findall("a:entry", ns)[:limit]:
        name = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
        link_el = entry.find("a:link", ns)
        url = link_el.get("href", "") if link_el is not None else ""
        raw = entry.findtext("a:content", default="", namespaces=ns) or ""
        desc = re.sub(r"<[^>]+>", " ", raw)
        desc = re.sub(r"\s+", " ", desc).strip()
        desc = re.split(r"\s*Discussion\s*\|", desc)[0][:200]
        if name:
            out.append(_live_entry(name, url, desc, "Product Hunt"))
    return out


# Indie Hackers has no public API; its best-known revenue-transparent products
# (Plausible, Carrd, Senja, Typefully, ScreenshotOne ...) live in the curated set.
LIVE_SOURCES = {
    "Hacker News (Show HN)": fetch_show_hn,
    "Product Hunt": fetch_product_hunt,
}

# Global tech-launch feeds: useful for spotting trends, but their launches are mostly dev tools and
# consumer apps with no traction data - not representative of the Czech SMB segment. The app hides
# them from the radar unless the user opts in.
LOW_CZ_RELEVANCE_SOURCES = {
    "Hacker News (Show HN)": "Global developer launches; rarely relevant to Czech SMB demand",
    "Product Hunt": "Global consumer/SaaS launches without traction data; low relevance to Czech SMBs",
}


def to_dataframe(models: list[BusinessModel]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "id": m.id, "Name": m.name, "Category": m.category, "Niche": m.niche,
                "Revenue model": m.revenue_model, "Intl. MRR (USD)": m.mrr_usd,
                "Problem": m.problem, "Tech stack": ", ".join(m.tech_stack),
                "Source": m.source, "Country": m.country, "URL": m.url,
            }
            for m in models
        ]
    )
