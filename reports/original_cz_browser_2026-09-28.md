# Ручная проверка оригиналов в браузере (2026-09-28)

Встроенный браузер Claude на компьютере пользователя (IP в Праге), страница после выполнения JS.
На каждой главной странице искались: `lang`, `hreflang="cs"`, `og:locale cs_CZ`, ссылки на `.cz` и пути `/cs/`, `/cz/`,
`/cs-cz/`, «Čeština» (с заглавной: в виджете Google Translate слово пишется «čeština» и признаком не считается),
цены в Kč/CZK. Плюс `robots.txt` → `sitemap.xml` (до 4 файлов, включая дочерние из sitemap index) с теми же шаблонами.
Каждое совпадение проверено вручную. Сайты с 403 и запретом в robots.txt браузером не открывались.

Проверено **101** из 433 сайтов со статусом «unknown» (в том числе все финалисты и шортлист);
остальные не успел: оборвалась связь с компьютером. Их закрывает `scripts/check_original_cz.py --recheck-unknown`
с новым чтением sitemap.

## Находки

- **Twinkl**: с чешского IP страница twinkl.co.uk ссылается на **https://www.twinkl.cz/**, это сильный признак
  (собственный .cz-домен). Скрипт этой ссылки не видел: вероятно, блок зависит от гео. Записано в оверлей как `yes`.
- **BetterMe**: в sitemap есть `hreflang="cs"` и `/cs/privacy-policy`, но чешской главной нет (`/cs` отдаёт 404).
  Переведены только юридические страницы. Записано как `likely`.
- **AirDNA**: в sitemap есть страницы данных по чешским городам (`/app/cz/default/prague`). Это охват данных,
  а не чешская версия, статус не менялся.
- **Beekeeper** теперь редиректит на lumapps.com/beekeeper (поглощение LumApps), добавлено в список редиректов.
- Ложные срабатывания, отброшены: ActivityHero (виджет Google Translate), Cars24 (`/cs/` в адресе трекера scorecardresearch).

## Все проверенные

| Модель | Сайт | Результат | Примечание |
|---|---|---|---|
| 2GIS | 2gis.ru | нет признаков | -> 2gis.ru/moscow |
| 6AM City | 6amcity.com | нет признаков |  |
| 7shifts | 7shifts.com | нет признаков |  |
| 99designs | 99designs.com | нет признаков | -> en.99designs.de (geo redirect from CZ) |
| AI CV & Cover Letter Builder (Kickresume archetype) | kickresume.com | нет признаков | -> /en/ |
| AI Legal Research Assistant for Czech Law (Harvey archetype) | harvey.ai | нет признаков |  |
| AI Meeting Notes (Otter/Fireflies archetype) | fireflies.ai | нет признаков |  |
| AI Multilingual Menu & Allergen Labels | menutiger.com | нет признаков |  |
| AI Phone Receptionist in Czech (Smith.ai archetype) | smith.ai | нет признаков |  |
| AI Product Descriptions for E-shops (Hypotenuse archetype) | hypotenuse.ai | нет признаков |  |
| AI SEO Content Writer in Czech (Surfer archetype) | surferseo.com | нет признаков |  |
| AI Tutor for Přijímačky & Maturita (Khanmigo archetype) | khanmigo.ai | нет признаков |  |
| Acuity Scheduling | acuityscheduling.com | нет признаков |  |
| Agency Time Tracking & Profitability (Toggl archetype) | toggl.com | нет признаков |  |
| Agrivi | agrivi.com | нет признаков |  |
| Ahrefs | ahrefs.com | нет признаков |  |
| AirDNA | airdna.co | заметка | sitemap has data pages for Czech cities (/app/cz/default/prague) - covers CZ market data, not a Czech edition |
| Airtasker | airtasker.com | нет признаков | -> /au/ |
| Apna | apna.co | нет признаков |  |
| Asaas | asaas.com | нет признаков |  |
| Aspro | aspro.ru | нет признаков |  |
| Automated Payment Reminders & Collections (Chaser archetype) | chaserhq.com | нет признаков |  |
| Aviasales | aviasales.ru | нет признаков | (departure preset to PRG by geo, not a Czech edition) |
| B2B Wholesale Portal for Small Brands (Faire/SparkLayer archetype) | sparklayer.io | нет признаков |  |
| Babbel | babbel.com | нет признаков |  |
| BambooHR | bamboohr.com | нет признаков |  |
| Banki.ru | banki.ru | не прочитан (похоже на проверку от ботов) | empty title/lang - probably bot challenge page |
| Bannerbear | bannerbear.com | нет признаков |  |
| Baremetrics | baremetrics.com | нет признаков |  |
| BarkBox | barkbox.com | нет признаков | -> bark.co (rebrand) |
| Basecamp | basecamp.com | нет признаков |  |
| Beardbrand | beardbrand.com | нет признаков |  |
| Beauty Pie | beautypie.com | нет признаков |  |
| Beekeeper | beekeeper.io | нет признаков | -> lumapps.com/beekeeper (acquired by LumApps) |
| BetterHelp | betterhelp.com | нет признаков |  |
| BetterMe | betterme.world | likely | sitemap: hreflang="cs" + /cs/privacy-policy; /cs home is 404 - only legal pages in Czech |
| Birdie | birdie.care | нет признаков |  |
| Bitrix24 | bitrix24.ru | нет признаков |  |
| Blinkist | blinkist.com | нет признаков |  |
| Bloom & Wild | bloomandwild.com | нет признаков |  |
| Booksy | booksy.com | нет признаков | -> /en-us/ even from CZ IP |
| Brand24 | brand24.com | нет признаков |  |
| BrowserStack | browserstack.com | нет признаков |  |
| Bubble | bubble.io | нет признаков |  |
| Buffer | buffer.com | нет признаков |  |
| Buildxact | buildxact.com | нет признаков | -> /uk/ |
| Buk | buk.cl | нет признаков |  |
| BukuWarung | bukuwarung.com | нет признаков |  |
| Bumpa | getbumpa.com | нет признаков |  |
| Buttondown | buttondown.com | нет признаков |  |
| CGTrader | cgtrader.com | нет признаков |  |
| Calendly | calendly.com | нет признаков |  |
| Calltouch | calltouch.ru | нет признаков |  |
| Cameo | cameo.com | нет признаков |  |
| Canny | canny.io | нет признаков |  |
| Care.com | care.com | нет признаков |  |
| Carrd | carrd.co | нет признаков | -> carrd.com (same brand) |
| Cars24 | cars24.com | нет признаков | (/cs/ hit was scorecardresearch beacon - false positive) |
| Carwow | carwow.co.uk | нет признаков |  |
| Cash-flow Forecasting for SMEs (Float archetype) | floatapp.com | нет признаков |  |
| Catawiki | catawiki.com | нет признаков | -> /en |
| Chai Point | chaipoint.com | нет признаков |  |
| Channel Talk | channel.io | нет признаков | -> /us |
| Chargebee | chargebee.com | нет признаков |  |
| Chatbase | chatbase.co | нет признаков |  |
| Checkbox | checkbox.ua | нет признаков |  |
| Cheerz | cheerz.com | нет признаков |  |
| Chocolife | chocolife.me | нет признаков |  |
| Class101 | class101.net | нет признаков | -> /en |
| ClassPass | classpass.com | нет признаков |  |
| Classplus | classplusapp.com | нет признаков |  |
| CleanShot X | cleanshot.com | нет признаков |  |
| Cleo | web.meetcleo.com | нет признаков |  |
| Client Galleries for Photographers (Pixieset archetype) | pixieset.com | нет признаков |  |
| Cliniko | cliniko.com | нет признаков |  |
| Clip | clip.mx | нет признаков |  |
| Close | close.com | нет признаков |  |
| Cofix | cofix.co.il | не открылся | navigation fails for both www and bare domain (same as SSLError in script) |
| Competitor Price Monitoring (Prisync archetype) | prisync.com | нет признаков |  |
| Conta Azul | contaazul.com | нет признаков |  |
| Cookie Consent Manager (Cookiebot archetype) | cookiebot.com | нет признаков |  |
| Cookpad | cookpad.com | нет признаков | -> /uk |
| Country Delight | countrydelight.in | нет признаков |  |
| Coworking Day-pass Marketplace (Deskpass archetype) | deskpass.com | нет признаков |  |
| Craft | craft.do | нет признаков |  |
| Craft Beer Subscription Box | beer52.com | нет признаков |  |
| Crehana | crehana.com | нет признаков | (site is now HR software - pivot) |
| Crimson Education | crimsoneducation.org | нет признаков | -> /uk (was 429 for script) |
| Crisp | crisp.chat | нет признаков | -> /en/ |
| Czech Transcription & Subtitles (Descript/Rev archetype) | rev.com | нет признаков |  |
| Czech for Foreigners: Exam-prep Marketplace | italki.com | нет признаков | 18 hreflang, no cs |
| Fixflo | fixflo.com | нет признаков |  |
| Interior AI | interiorai.com | нет признаков |  |
| Kids' Clubs & Camps Booking (ActivityHero archetype) | activityhero.com | нет признаков | čeština only in Google Translate widget (false positive) |
| Outschool | outschool.com | нет признаков |  |
| Public Tender Alerts for SMEs (GovSpend archetype) | govspend.com | нет признаков |  |
| Review Request Automation (NiceJob archetype) | get.nicejob.com | нет признаков |  |
| Sklik + Google Ads Client Reporting (AgencyAnalytics archetype) | agencyanalytics.com | нет признаков |  |
| Spond | spond.com | нет признаков |  |
| Timeleft | timeleft.com | нет признаков |  |
| Twinkl | twinkl.co.uk | **yes** | link to https://www.twinkl.cz/ (seen from CZ IP) |
