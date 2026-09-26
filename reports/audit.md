# Data audit - 2026-09-26

500 curated models. This report changes nothing; proposed fixes are in `patches/data_fixes.json` and are applied only by `scripts/apply_data_patch.py`.

## 1. Templated Czech segments

12 identical segment lists are shared by 3+ models (380 models). Most come from category defaults filled in when a model had no hand-written segments - they describe the category, not the model.

- **Czech dev agencies; SaaS startups; SMB teams** (68): Aspro, BambooHR, Baremetrics, Basecamp, Beekeeper, Bitrix24, BrowserStack, Bubble, Buildxact, Buk, Calendly, Canny, Canva, Channel Talk, CleanShot X, Craft, Crisp, Crowdin, Doodle, Dorik, Elementor, Factorial, Fastmail, Fathom Analytics, Framer, Freshworks, Help Scout, Hostinger, Hotjar, Huntflow (Хантфлоу), Instabug, Jivo, Jotform, Juro, LiveChat (Text), Livestorm, Loom, MacPaw, Mentimeter, Nicereply, Obsidian, Odoo, PandaDoc, Pipefy, Prezi, Readdle, SafetyCulture, SavvyCal, ShipFast, Simple Analytics, Slido, Smallpdf, SmartHR, Softr, Tailwind Labs (Tailwind UI), Teamleader, Teamwork, Things (Cultured Code), Tilda, Tuple, Typeform, UserGuiding, WeTransfer, Webflow, Workable, Zapier, Zoho, n8n
- **Prague expats; Local niche communities** (44): 2GIS, Apna, Cameo, Cars24, Carwow, Catawiki, Chocolife, Community group-buying (Xingsheng Youxuan archetype), Cookpad, Etsy, Fiverr, Flowwow, Fractory, Grover, Hipcamp, Jooble, Kalibrr, Karrot (Danggeun), Kitabisa, Komoot, Meesho, Meetup, Mercari, Mumsnet, MyGate, Nextdoor, NoBroker, Olio, OpenRent, Outdoorsy, Pinkoi, QuintoAndar, Refurbed, Spacemarket, Strava, Swapfiets, Timee, Timeleft, Toptal, Turo, Vivino, WeBuyAnyCar, Workana, Zenjob
- **Czech OSVČ; Small accounting firms** (40): Asaas, Banki.ru, BukuWarung, Chargebee, Checkbox, Cleo, Clip, Conta Azul, Diadoc (Диадок), Dubsado, Evotor (Эвотор), Farewill, FreeAgent, FreshBooks, GoCardless, Hnry, HoneyBook, Khatabook, Knopka (Кнопка), Kontur.Elba (Контур.Эльба), LegalZoom, Lemon Squeezy, M-KOPA, Money Fellows, MoySklad (МойСклад), Omie, Paddle, PolicyBazaar, Rocket Money, Solar Staff, SuperFaktúra, Swile, Taxfix, Wave, Xero, YNAB, Yoco, freee, inFakt, sevDesk
- **Parents of school pupils; Students before exams; Adult learners** (37): Babbel, Blinkist, Brainly, Class101, Crehana, Crimson Education, Descomplica, Domestika, Duolingo, ELSA Speak, Foxford (Фоксфорд), GetSmarter, Hahow, Kahoot!, Kumon, Laba, Lalilo, Lingokids, Lingvist, OpenClassrooms, Ornikar, Otsimo, Outschool, Photomath, Physics Wallah, Platzi, Scribbr, Scrimba, Seneca Learning, Skyeng, SoloLearn, Studocu, Tandem, Twinkl, Uchi.ru (Учи.ру), Zen Educate, iSpring
- **Prague & Brno urban consumers; Online shoppers 25-45; Gift buyers** (33): BarkBox, Beardbrand, Beauty Pie, Bloom & Wild, Cheerz, Country Delight, Dollar Shave Club, Frank Body, Gymshark, HelloFresh, Huel, Kurly, Lenskart, Liquid Death, Misfits Market, Moo, Moonpig, Ohouse, Pact Coffee, Patch Plants, Pop Mart, Rent the Runway, Smol, Stitch Fix, Tails.com, Tractive, Treedom, Tylko, VkusVill (ВкусВилл), Warby Parker, Who Gives A Crap, Wild, mymuesli
- **Czech digital agencies; SME marketing teams** (31): Ahrefs, Brand24, Close, Databox, Exploding Topics, Hunter, Live-stream shopping for small brands (Taobao Live archetype), Mailchimp, MailerLite, Mangools, Mynewsdesk, Pipedrive, Planable, RD Station, Rewardful, Roistat, Salebot, SendPulse, Sendy, Senler, ShopBack, SleekFlow, Supermetrics, Telega.in, Trustpilot, Unisender, Userlist, VWO, amoCRM (Kommo), lemlist, respond.io
- **Czech creators & coaches** (28): 99designs, Buttondown, CGTrader, Depositphotos, Envato, Epidemic Sound, Fever, GetCourse, Going (Scott's Cheap Flights), Hotmart, Kajabi, Kickstarter, Linktree, LitRes (ЛитРес), Makerist, PicsArt, Pocket FM, Printful, Riverside, Screen Studio, Starter Story, StreamYard, Substack, Taplink, Teachable, Thinkific, Ulule, note
- **Prague restaurants & cafés; Short-term rental hosts** (27): 7shifts, AirDNA, Aviasales, Chai Point, Cofix, Dodo Pizza, Flipdish, Foodics, Guesty, Kitopi, Kopi Kenangan, Kukhnya na Rayone (Кухня на районе), La Belle Assiette, Lodgify, Luckin Coffee, Obilet, Planday, Poster POS, PriceLabs, Rebel Foods, Slice, Toast, Travelline, Withlocals, Wongnai, iCHEF, iiko
- **Shoptet merchants; Upgates merchants** (20): AfterShip, BaseLinker (Base), Bumpa, Ecwid, Gorgias, KeyCRM, Klaviyo, Marketplace fulfilment operator (Wildberries/Ozon sellers), Melhor Envio, Nuvemshop (Tiendanube), Olist, Omnisend, Packhelp, Privy, Raksul, Retail Rocket, Shopify, Smile.io, YouCan, Youzan
- **Health-conscious urban professionals; Private clinics & therapists; Employers (wellness benefits)** (19): BetterHelp, BetterMe, Birdie, ClassPass, Cliniko, Doctolib, Flo, Freeletics, Glofox, Headspace, HealthifyMe, Invitro, Jane App, Lottie, Oura, Thriva, Wellhub (Gympass), Yuka, Zocdoc
- **Prague service businesses** (18): Acuity Scheduling, Airtasker, Bookio, Booksy, Care.com, Eden Life, Justlife, Lalamove, LawnStarter, Profi.ru, Soomgo, SweepSouth, TaskRabbit, Thumbtack, Treatwell, Urban Company, Wecasa, YCLIENTS
- **Czech SMEs adopting AI; Shoptet merchants** (15): DoNotPay, ElevenLabs, Gamma, Grammarly, InVideo, Jasper, Krisp, Lovable, Opus Clip, Spellbook, Synthesia, Tailor Brands, Tidio, TypingMind, remove.bg

## 2. Suspicious metadata

20 models.

| Model | Country | URL | Issues |
|---|---|---|---|
| Bannerbear | Global / remote | https://www.bannerbear.com | origin country is vague ('Global / remote') |
| Senja | Global / remote | https://senja.io | origin country is vague ('Global / remote') |
| Judge.me | Global / remote | https://judge.me | origin country is vague ('Global / remote') |
| Back-in-Stock Alerts (Shopify app archetype) | Global / remote | https://apps.shopify.com/search?q=back%20in%20stock | origin country is vague ('Global / remote') |
| AI Multilingual Menu & Allergen Labels | Global / remote | https://www.menutiger.com | origin country is vague ('Global / remote') |
| Meal-Prep Subscription (krabičková dieta) | USA | https://www.factor75.com | URL host 'factor75.com' doesn't match the model name |
| Chatbase | Global / remote | https://www.chatbase.co | origin country is vague ('Global / remote') |
| Web Accessibility Checker (EAA compliance) | UK | https://www.silktide.com | URL host 'silktide.com' doesn't match the model name |
| Instatus | Global / remote | https://instatus.com | origin country is vague ('Global / remote') |
| Influencer Marketplace (Collabstr archetype) | North America | https://collabstr.com | origin country is vague ('North America') |
| Product Feed Manager (DataFeedWatch archetype) | Global / remote | https://www.datafeedwatch.com | origin country is vague ('Global / remote') |
| Post-purchase Upsell App (ReConvert archetype) | Global / remote | https://www.reconvert.io | origin country is vague ('Global / remote') |
| Driving School Management & Theory App | Global / remote | https://www.drivingschoolsoftware.com | origin country is vague ('Global / remote') |
| Mobile Car Detailing Booking | USA | https://www.getspiffy.com | URL host 'getspiffy.com' doesn't match the model name |
| Czech for Foreigners: Exam-prep Marketplace | Hong Kong | https://www.italki.com | URL host 'italki.com' doesn't match the model name; Czech-specific idea attributed to origin 'Hong Kong' - origin should describe the reference model, not the Czech idea |
| Marketplace fulfilment operator (Wildberries/Ozon sellers) | Russia | - | no URL |
| Kukhnya na Rayone (Кухня на районе) | Russia | - | no URL |
| Physics Wallah | India | https://www.pw.live | URL host 'pw.live' doesn't match the model name |
| Community group-buying (Xingsheng Youxuan archetype) | China | - | no URL |
| Live-stream shopping for small brands (Taobao Live archetype) | China | - | no URL |

## 3. Tied to a post-Soviet fiscal / e-document / platform ecosystem

Proposed `needs_rethink_for_cz: true` - the model only works on top of systems that do not exist in Czechia. The idea may still transfer, but the product must be rebuilt around Czech equivalents.

| Model | Country | Dependency |
|---|---|---|
| MoySklad (МойСклад) | Russia | Russian marking & fiscal integrations |
| Evotor (Эвотор) | Russia | fiscal / cash-register law |
| iiko | Russia | Russian EGAIS / fiscal integrations |
| Kontur.Elba (Контур.Эльба) | Russia | Russian ИП tax regimes |
| Knopka (Кнопка) | Russia | Russian accounting standards (RSBU) |
| Diadoc (Диадок) | Russia | national e-document (EDO) rules |
| Solar Staff | Russia | Russian self-employed (НПД) regime |
| MPStats | Russia | Wildberries/Ozon marketplaces (absent in CZ) |
| Marketplace fulfilment operator (Wildberries/Ozon sellers) | Russia | Wildberries/Ozon marketplaces (absent in CZ) |
| Telega.in | Russia | Telegram ad market (niche in CZ) |
| Senler | Russia | VK platform (not used in CZ) |
| Checkbox | Ukraine | fiscal / cash-register law |

## 4. Enrichment gaps

- `model_type` only inferred by rules: **492** models (verify in `data/cz_enrichment.json`).
- VAT treatment (`price_includes_vat`) only inferred from B2B/B2C: **500** models.
- SAM is still the unverified heuristic: **442** models.
- MRR not comparable with the model type: **114** models:

  - *Physical / retail sales - not SaaS MRR* (44): BarkBox, Beardbrand, Beauty Pie, Bloom & Wild, Cars24, Chai Point, Cheerz, Cofix, Country Delight, Craft Beer Subscription Box, Dodo Pizza, Dollar Shave Club, Frank Body, Gymshark, HelloFresh, Huel, Kopi Kenangan, Kukhnya na Rayone (Кухня на районе), Kurly, Lenskart, Liquid Death, Luckin Coffee, Meal-Prep Subscription (krabičková dieta), Misfits Market, Moo, Moonpig, Packhelp, Pact Coffee, Patch Plants, Pop Mart, Rebel Foods, Rent the Runway, Smol, Stitch Fix, Tails.com, Tractive, Treedom, Tylko, VkusVill (ВкусВилл), Warby Parker, WeBuyAnyCar, Who Gives A Crap, Wild, mymuesli
  - *Marketplace without GMV data - MRR not comparable* (70): 99designs, Airtasker, Ankorstore, Aviasales, Banki.ru, CGTrader, Cameo, Catawiki, Chocolife, Community group-buying (Xingsheng Youxuan archetype), Czech for Foreigners: Exam-prep Marketplace, Envato, Etsy, Event Ticketing for Small Organisers (Eventbrite archetype), Fever, Fiverr, Flowwow, Fractory, Hipcamp, Home Cleaning Marketplace (Helpling archetype), Home-care & Senior Companion Matching (Honor archetype), Hotmart, Influencer Marketplace (Collabstr archetype), Kitabisa, La Belle Assiette, Lalamove, LawnStarter, Local Freelance Marketplace (Upwork archetype), Lottie, Makerist, Meesho, Mercari, Newsletter Sponsorship Marketplace (Paved archetype), Obilet, Office Catering Marketplace (ezCater archetype), Ohouse, Olist, Outdoorsy, Outschool, Paid Memberships for Creators (Patreon archetype), Peer-to-peer Equipment Rental (Fat Llama archetype), Pet Sitting & Dog Walking Marketplace (Rover archetype), Pinkoi, PolicyBazaar, Private Parking Space Sharing (JustPark archetype), Profi.ru, QuintoAndar, Raksul, Refurbed, ShopBack, Spacemarket, Surplus Food Marketplace (Too Good To Go archetype), SweepSouth, TaskRabbit, Telega.in, Thumbtack, Timee, Tradesperson Quote Marketplace (Checkatrade archetype), Treatwell, Turo, Tutoring Marketplace (Preply archetype), Ulule, Urban Company, Vinted, Vivino, Wecasa, Withlocals, Workana, Zocdoc, note

## Proposed patch

33 changes in `patches/data_fixes.json`:

| Model | Field | New value | Reason |
|---|---|---|---|
| MoySklad (МойСклад) | needs_rethink_for_cz | true | Russian marking & fiscal integrations |
| Evotor (Эвотор) | needs_rethink_for_cz | true | fiscal / cash-register law |
| iiko | needs_rethink_for_cz | true | Russian EGAIS / fiscal integrations |
| Kontur.Elba (Контур.Эльба) | needs_rethink_for_cz | true | Russian ИП tax regimes |
| Knopka (Кнопка) | needs_rethink_for_cz | true | Russian accounting standards (RSBU) |
| Diadoc (Диадок) | needs_rethink_for_cz | true | national e-document (EDO) rules |
| Solar Staff | needs_rethink_for_cz | true | Russian self-employed (НПД) regime |
| MPStats | needs_rethink_for_cz | true | Wildberries/Ozon marketplaces (absent in CZ) |
| Marketplace fulfilment operator (Wildberries/Ozon sellers) | needs_rethink_for_cz | true | Wildberries/Ozon marketplaces (absent in CZ) |
| Telega.in | needs_rethink_for_cz | true | Telegram ad market (niche in CZ) |
| Senler | needs_rethink_for_cz | true | VK platform (not used in CZ) |
| Checkbox | needs_rethink_for_cz | true | fiscal / cash-register law |
| Czech for Foreigners: Exam-prep Marketplace | country | "Global / remote" | Czech-specific idea; italki (Hong Kong) is only the inspiration, not the origin of this model |
| Czech for Foreigners: Exam-prep Marketplace | url | "" | italki.com is a general tutoring marketplace, not a reference for this exam-prep niche |
| AirDNA | cz_segments | ["Short-term rental investors", "Prague Airbnb hosts", "Property-management companies"] | templated gastro/STR segments don't describe this model |
| PriceLabs | cz_segments | ["Prague Airbnb hosts & co-hosts", "Apartment-management companies", "Small hotels & pensions"] | templated gastro/STR segments don't describe this model |
| Guesty | cz_segments | ["Short-term rental management companies", "Prague co-hosting agencies"] | templated gastro/STR segments don't describe this model |
| Lodgify | cz_segments | ["Holiday-home owners (chaty, chalupy)", "Pensions (penziony)", "Apartment managers"] | templated gastro/STR segments don't describe this model |
| Travelline | cz_segments | ["Small hotels", "Pensions (penziony)", "Spa hotels"] | templated gastro/STR segments don't describe this model |
| Aviasales | cz_segments | ["Czech leisure travellers", "Budget travellers & students"] | templated gastro/STR segments don't describe this model |
| La Belle Assiette | cz_segments | ["Private chefs", "Households hosting dinners", "Corporate event organisers"] | templated gastro/STR segments don't describe this model |
| Withlocals | cz_segments | ["Prague tour guides", "Tourists wanting private tours"] | templated gastro/STR segments don't describe this model |
| Kitopi | cz_segments | ["Restaurant brands wanting delivery reach", "Dark-kitchen operators"] | templated gastro/STR segments don't describe this model |
| Luckin Coffee | cz_segments | ["Urban commuters", "Office workers", "Students"] | templated gastro/STR segments don't describe this model |
| Kopi Kenangan | cz_segments | ["Urban commuters", "Office workers", "Students"] | templated gastro/STR segments don't describe this model |
| Cofix | cz_segments | ["Price-sensitive coffee drinkers", "Students", "Office workers"] | templated gastro/STR segments don't describe this model |
| Chai Point | cz_segments | ["Offices wanting hot-drink service", "Commuters"] | templated gastro/STR segments don't describe this model |
| Dodo Pizza | cz_segments | ["Families ordering delivery", "Office lunch orders", "Franchisees"] | templated gastro/STR segments don't describe this model |
| Cleo | cz_segments | ["Young adults 18-30", "Students managing money"] | templated 'OSVČ / accounting firms' segments don't fit a consumer product |
| Farewill | cz_segments | ["Adults 40+ planning inheritance", "Families going through probate (dědické řízení)"] | templated 'OSVČ / accounting firms' segments don't fit a consumer product |
| Banki.ru | cz_segments | ["Consumers comparing loans & deposits", "Banks & lenders buying leads"] | templated 'OSVČ / accounting firms' segments don't fit a consumer product |
| PolicyBazaar | cz_segments | ["Consumers comparing insurance", "Insurers & brokers buying leads"] | templated 'OSVČ / accounting firms' segments don't fit a consumer product |
| Money Fellows | cz_segments | ["Young savers", "Communities saving together"] | templated 'OSVČ / accounting firms' segments don't fit a consumer product |
