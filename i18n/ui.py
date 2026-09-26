"""Interface strings. Keys are stable identifiers; each entry has 'ru' and 'en'."""

UI: dict[str, dict[str, str]] = {
    # ---------------------------------------------------------------- page & navigation
    "page_title": {"ru": "Радар бизнес-моделей для Чехии", "en": "Czech Business Model Radar"},
    "app_title": {"ru": "🇨🇿 Радар бизнес-моделей для Чехии", "en": "🇨🇿 Czech Business Model Radar"},
    "app_caption": {"ru": "Находите проверенные в мире модели малого бизнеса и микро-SaaS и адаптируйте их "
                          "для Праги и чешского рынка.",
                    "en": "Discover proven small-business & micro-SaaS models worldwide and adapt them for "
                          "Prague and the Czech market."},
    "view_radar": {"ru": "📡 Радар", "en": "📡 Radar"},
    "view_deep": {"ru": "🔬 Разбор", "en": "🔬 Deep-Dive"},
    "view_table": {"ru": "📊 Таблица", "en": "📊 Data table"},
    "view_method": {"ru": "ℹ️ Методология", "en": "ℹ️ Methodology"},
    "language": {"ru": "Язык / Language", "en": "Language / Язык"},

    # ---------------------------------------------------------------- sidebar: engine
    "engine_header": {"ru": "⚙️ Движок анализа", "en": "⚙️ Analysis engine"},
    "api_keys": {"ru": "🔑 API-ключи", "en": "🔑 API keys"},
    "anthropic_key": {"ru": "API-ключ Anthropic", "en": "Anthropic API key"},
    "anthropic_key_help": {"ru": "Хранится только в этой сессии браузера. Либо задайте ANTHROPIC_API_KEY в "
                                 "секретах / переменных окружения.",
                           "en": "Kept only in this browser session. Or set ANTHROPIC_API_KEY as a secret / env var."},
    "gemini_key": {"ru": "API-ключ Gemini", "en": "Gemini API key"},
    "gemini_key_help": {"ru": "Бесплатный ключ: aistudio.google.com/apikey. Хранится только в этой сессии браузера. "
                              "Либо задайте GEMINI_API_KEY в секретах / переменных окружения.",
                        "en": "Free key at aistudio.google.com/apikey. Kept only in this browser session. "
                              "Or set GEMINI_API_KEY as a secret / env var."},
    "engine": {"ru": "Движок", "en": "Engine"},
    "engine_help": {"ru": "Авто: Claude, если задан его ключ, иначе Gemini, иначе мгновенный офлайн-движок.",
                    "en": "Auto: Claude if its key is set, otherwise Gemini, otherwise the instant offline engine."},
    "engine_auto": {"ru": "Авто", "en": "Auto"},
    "engine_offline": {"ru": "Офлайн", "en": "Offline"},
    "claude_model": {"ru": "Модель Claude", "en": "Claude model"},
    "gemini_model": {"ru": "Модель Gemini", "en": "Gemini model"},
    "gemini_model_help": {"ru": "Выберите из списка или впишите любой другой идентификатор модели Gemini.",
                          "en": "Pick one or type any other Gemini model id."},
    "keys_detected": {"ru": "Найдены ключи: Anthropic {a} · Gemini {g}", "en": "Keys detected: Anthropic {a} · Gemini {g}"},
    "offline_mode": {"ru": "Офлайн-режим: мгновенные эвристические отчёты.",
                     "en": "Offline demo mode - instant heuristic reports."},
    "engine_enabled": {"ru": "{engine} включён ({model})", "en": "{engine} enabled ({model})"},
    "no_key": {"ru": "Не найден API-ключ {engine} — отчёты будут строиться офлайн.",
               "en": "No {engine} API key found - reports will fall back to offline mode."},

    # ---------------------------------------------------------------- sidebar: assumptions & weights
    "assumptions": {"ru": "🇨🇿 Рыночные допущения", "en": "🇨🇿 Market assumptions"},
    "usd_czk": {"ru": "Курс USD / CZK", "en": "USD / CZK"},
    "ppp_b2b": {"ru": "Цена B2B относительно США", "en": "B2B price vs. US"},
    "ppp_b2c": {"ru": "Цена B2C относительно США", "en": "B2C price vs. US"},
    "pausal1": {"ru": "Paušální daň, уровень 1 (CZK/мес.)", "en": "Paušální daň band 1 (CZK/month)"},
    "pausal1_help": {"ru": "Округлённая оценка на 2026 год — проверьте на financnisprava.cz",
                     "en": "Rounded 2026 figure - verify on financnisprava.cz"},
    "pausal2": {"ru": "Paušální daň, уровень 2 (CZK/мес.)", "en": "Paušální daň band 2 (CZK/month)"},
    "pausal3": {"ru": "Paušální daň, уровень 3 (CZK/мес.)", "en": "Paušální daň band 3 (CZK/month)"},
    "sro_accounting": {"ru": "Бухгалтер для s.r.o. (CZK/мес.)", "en": "s.r.o. accountant (CZK/month)"},
    "weights_header": {"ru": "**Веса чешского скора**", "en": "**Czech score weights**"},
    "w_incumbent": {"ru": "Баллов за единицу силы конкурента", "en": "Points per incumbent strength"},
    "w_incumbent_cap": {"ru": "Максимальный штраф за конкурентов", "en": "Max incumbent penalty"},
    "w_sam_soft": {"ru": "Доля рынка: штраф начинается с", "en": "SAM share: penalty starts at"},
    "w_sam_hard": {"ru": "Доля рынка: резкий штраф с", "en": "SAM share: steep penalty from"},
    "w_sam_step": {"ru": "Скачок штрафа сразу за порогом доли", "en": "Penalty step right above the share threshold"},
    "w_sam_conf": {"ru": "Уверенность в эвристическом SAM (множитель штрафа)",
                   "en": "Confidence in a heuristic SAM (penalty multiplier)"},
    "w_sam_soft_pen": {"ru": "Штраф за долю рынка до резкого порога", "en": "SAM penalty up to the steep threshold"},
    "w_sam_hard_pen": {"ru": "Дополнительный штраф за порогом", "en": "Extra SAM penalty beyond it"},
    "w_legal": {"ru": "Баллов за уровень юр. сложности", "en": "Points per legal-complexity level"},
    "w_integration": {"ru": "Баллов за сложную интеграцию", "en": "Points per complex integration"},
    "w_solo": {"ru": "Соло-основатель (поддержка на чешском дорога)", "en": "Solo founder (Czech support is costly)"},
    "w_support": {"ru": "Штраф за поддержку на чешском (B2C и локальные категории)",
                  "en": "Czech-support penalty (B2C and local categories)"},
    "w_support_other": {"ru": "Штраф за поддержку на чешском (прочий B2B)",
                        "en": "Czech-support penalty (other B2B)"},

    "w_original": {"ru": "Штраф, если оригинал уже в Чехии", "en": "Penalty if the original is already in Czechia"},

    # ---------------------------------------------------------------- sidebar: live sources
    "live_header": {"ru": "🌐 Живые источники", "en": "🌐 Live sources"},
    "live_from": {"ru": "Загружать свежие запуски из", "en": "Fetch fresh launches from"},
    "live_items": {"ru": "Записей на источник", "en": "Items per source"},
    "live_show": {"ru": "Показывать ленты запусков на радаре", "en": "Show launch feeds in the radar"},
    "live_show_help": {"ru": "Hacker News и Product Hunt — глобальные ленты запусков, не репрезентативные для "
                             "чешского SMB-сегмента, поэтому по умолчанию скрыты.",
                       "en": "Hacker News and Product Hunt are global launch feeds - not representative of the "
                             "Czech SMB segment, so they are hidden by default."},
    "live_fetch": {"ru": "Загрузить", "en": "Fetch live"},
    "live_clear": {"ru": "Очистить", "en": "Clear live"},
    "live_fetching": {"ru": "Загружаю {name}…", "en": "Fetching {name}..."},
    "live_fetched": {"ru": "Загружено запусков: {n}", "en": "Fetched {n} live launches"},
    "live_fetched_hidden": {"ru": " — включите «Показывать ленты запусков на радаре», чтобы их увидеть",
                            "en": " - turn on 'Show launch feeds in the radar' to see them"},
    "live_caption": {"ru": "⚠️ Глобальные ленты запусков мало релевантны для чешского малого бизнеса. У Indie "
                           "Hackers нет публичного API — его продукты с открытой выручкой уже есть в базе.",
                     "en": "⚠️ Global launch feeds: low relevance for Czech SMBs. Indie Hackers has no public "
                           "API - its revenue-transparent products are in the curated set."},

    # ---------------------------------------------------------------- sidebar: custom model form
    "custom_header": {"ru": "➕ Добавить свою модель", "en": "➕ Add your own model"},
    "f_name": {"ru": "Название *", "en": "Name *"},
    "f_url": {"ru": "Сайт", "en": "URL"},
    "f_category": {"ru": "Категория", "en": "Category"},
    "f_niche": {"ru": "Ниша", "en": "Niche"},
    "f_problem": {"ru": "Какую проблему решает", "en": "Problem solved"},
    "f_revenue_model": {"ru": "Модель выручки", "en": "Revenue model"},
    "f_revenue_model_default": {"ru": "Подписка SaaS", "en": "Subscription SaaS"},
    "f_mrr": {"ru": "Известный MRR (USD, 0 = неизвестно)", "en": "Known MRR (USD, 0 = unknown)"},
    "f_price": {"ru": "Типичная цена (USD/мес.)", "en": "Typical price (USD/month)"},
    "f_audience": {"ru": "Аудитория", "en": "Audience"},
    "f_sam": {"ru": "Потенциальных клиентов в Чехии", "en": "Serviceable customers in CZ"},
    "f_segments": {"ru": "Чешские сегменты (через запятую)", "en": "Czech segments (comma separated)"},
    "f_demand": {"ru": "Местный спрос", "en": "Local demand"},
    "f_competition": {"ru": "Местная конкуренция", "en": "Local competition"},
    "f_complexity": {"ru": "Сложность разработки", "en": "Build complexity"},
    "f_add": {"ru": "Добавить", "en": "Add"},
    "f_added": {"ru": "Добавлено: {name}", "en": "Added {name}"},
    "f_user_supplied": {"ru": "Указано пользователем", "en": "User-supplied"},

    # ---------------------------------------------------------------- filters & KPIs
    "search": {"ru": "🔎 Поиск", "en": "🔎 Search"},
    "search_ph": {"ru": "например, Shoptet, ресторан, AI", "en": "e.g. Shoptet, restaurant, AI"},
    "category": {"ru": "Категория", "en": "Category"},
    "score": {"ru": "Скор", "en": "Score"},
    "score_czech": {"ru": "🇨🇿 Чешский скор", "en": "🇨🇿 Czech score"},
    "score_orig": {"ru": "Исходный скор", "en": "Original score"},
    "score_help": {"ru": "Чешский скор = исходная оценка выполнимости минус чешские трудности (конкуренты, доля "
                         "рынка, юридическая сложность, интеграции, поддержка на чешском). Веса — в боковой панели.",
                   "en": "Czech score = original feasibility minus Czech frictions (incumbents, SAM share, legal "
                         "complexity, integrations, Czech support). Weights: sidebar."},
    "col_czech_score": {"ru": "Чешский скор", "en": "Czech score"},
    "col_score": {"ru": "Исходный скор", "en": "Original score"},
    "sort_by": {"ru": "Сортировка", "en": "Sort by"},
    "min_score": {"ru": "Мин. значение: {score}", "en": "Min. {score}"},
    "model_type": {"ru": "Тип модели", "en": "Model type"},
    "model_type_help": {"ru": "Физический D2C и офлайн-розница скрыты по умолчанию: их выручка — это продажи, а не "
                              "MRR, сопоставимый с SaaS.",
                        "en": "Physical D2C and offline retail are hidden by default: their revenue is sales, not "
                              "SaaS-comparable MRR."},
    "hide_rethink": {"ru": "Скрыть «пересмотр»", "en": "Hide 'rethink'"},
    "hide_rethink_help": {"ru": "Модели, завязанные на фискальные системы, ЭДО или платформы, которых нет в Чехии "
                                "(флаг ставит проверенный патч данных).",
                          "en": "Models tied to fiscal / e-document / platform systems that don't exist in Czechia "
                                "(flag set by the reviewed data patch)."},
    "only_saas": {"ru": "Только SaaS", "en": "Only SaaS / add-ons"},
    "potential": {"ru": "Оценка потенциала в CZK (MRR на 12-й месяц)", "en": "Estimated CZK potential (month-12 MRR)"},
    "country": {"ru": "Страна происхождения", "en": "Country of origin"},
    "source": {"ru": "Источник", "en": "Source"},
    "kpi_shown": {"ru": "Показано моделей", "en": "Models shown"},
    "kpi_countries": {"ru": "Стран", "en": "Countries"},
    "kpi_avg": {"ru": "Средний: {score}", "en": "Avg. {score}"},
    "kpi_median_pot": {"ru": "Медиана потенциала", "en": "Median CZK potential"},
    "kpi_top": {"ru": "Лидер", "en": "Top pick"},

    # ---------------------------------------------------------------- radar & cards
    "no_match": {"ru": "Ни одна модель не подходит под фильтры.", "en": "No models match the filters."},
    "colour": {"ru": "Цвет", "en": "Colour"},
    "colour_category": {"ru": "Категория", "en": "Category"},
    "colour_incumbents": {"ru": "Местные конкуренты", "en": "Local incumbents"},
    "map_title": {"ru": "Карта возможностей — лучшие справа вверху; размер = SAM; ◆ = MRR не сопоставим",
                  "en": "Opportunity map - top-right is best; size = SAM; ◆ = MRR not comparable"},
    "axis_mrr": {"ru": "Потенциал MRR на 12-й месяц (CZK)", "en": "Month-12 MRR potential (CZK)"},
    "mrr_comparable": {"ru": "сопоставим", "en": "comparable"},
    "mrr_not_comparable": {"ru": "не сопоставим", "en": "not comparable"},
    "page": {"ru": "Страница", "en": "Page"},
    "showing": {"ru": "Показаны {a}–{b} из {n}", "en": "Showing {a}-{b} of {n} models"},
    "badge_rethink": {"ru": "переосмыслить для CZ", "en": "needs rethink for CZ"},
    "incumbents_list": {"ru": "Местные конкуренты", "en": "Local incumbents"},
    "not_verified": {"ru": "не проверено", "en": "not verified"},
    "strength": {"ru": "сила", "en": "strength"},
    "badge_orig_yes": {"ru": "оригинал уже в CZ", "en": "original already in CZ"},
    "badge_orig_likely": {"ru": "оригинал, возможно, в CZ", "en": "original possibly in CZ"},
    "badge_feed": {"ru": "лента запусков — мало релевантно для CZ", "en": "launch feed - low CZ SMB relevance"},
    "czech_vs_orig": {"ru": "🇨🇿 {cz} против исходного {base} ({delta:+d})", "en": "🇨🇿 {cz} vs. original {base} ({delta:+d})"},
    "customers_needed": {"ru": "Нужно клиентов", "en": "Customers needed"},
    "of_sam": {"ru": "{share} рынка", "en": "{share} of SAM"},
    "no_sam": {"ru": "нет SAM", "en": "no SAM"},
    "intl_mrr": {"ru": "MRR в мире", "en": "Intl. MRR"},
    "czk_month": {"ru": "CZK / мес. (12-й мес.)", "en": "CZK / month (M12)"},
    "breakdown": {"ru": "Разбор чешского скора", "en": "Czech score breakdown"},
    "no_deductions": {"ru": "Чешских вычетов нет.", "en": "No Czech deductions."},
    "legal_complexity": {"ru": "Юридическая сложность", "en": "Legal complexity"},
    "integrations": {"ru": "Интеграции", "en": "Integrations"},
    "sam_line": {"ru": "SAM {sam} — {source}", "en": "SAM {sam} - {source}"},
    "no_sam_estimate": {"ru": "Нет оценки размера рынка", "en": "No SAM estimate"},
    "inferred": {"ru": "Выведено правилами (не проверено): {fields}", "en": "Inferred by rules (unverified): {fields}"},
    "details": {"ru": "Подробности", "en": "Details"},
    "problem": {"ru": "Проблема", "en": "Problem"},
    "revenue_model": {"ru": "Модель выручки", "en": "Revenue model"},
    "tech_stack": {"ru": "Технологии", "en": "Tech stack"},
    "czech_segments": {"ru": "Чешские сегменты", "en": "Czech segments"},
    "llm_assessment": {"ru": "**🤖 Оценка LLM** ({engine}, {date}): выполнимость {f}, чешский скор {cz}, "
                             "уверенность **{conf}**",
                       "en": "**🤖 LLM assessment** ({engine}, {date}): feasibility {f}, Czech {cz}, "
                             "confidence **{conf}**"},
    "no_llm": {"ru": "Скоры рассчитаны эвристикой по правилам — оценки LLM ещё нет (запустите разбор через "
                     "Claude или Gemini).",
               "en": "Scores are rule-based heuristics - no LLM assessment yet (run a Deep-Dive with Claude or "
                     "Gemini)."},
    "dd_button": {"ru": "🔬 Разбор для Чехии", "en": "🔬 Deep-Dive Czech Report"},

    # ---------------------------------------------------------------- deep-dive
    "spinner_llm": {"ru": "Запрашиваю разбор для Чехии у {model} (может занять минуту)…",
                    "en": "Asking {model} for a Czech deep-dive (can take a minute)..."},
    "spinner_offline": {"ru": "Запускаю движок адаптации для Чехии…", "en": "Running the Czech adaptation engine..."},
    "business_model": {"ru": "Бизнес-модель", "en": "Business model"},
    "regenerate": {"ru": "🔄 Пересоздать", "en": "🔄 Regenerate"},
    "generate": {"ru": "🔬 Создать отчёт", "en": "🔬 Generate report"},
    "click_generate": {"ru": "Нажмите **Создать отчёт**, чтобы запустить анализ локализации для Чехии.",
                       "en": "Click **Generate report** to run the Czech localisation analysis."},
    "generated_by": {"ru": "🤖 Сгенерировано: {engine}", "en": "🤖 Generated by {engine}"},
    "offline_engine": {"ru": "⚡ Офлайн-движок (эвристика)", "en": "⚡ Offline heuristic engine"},
    "confidence": {"ru": "Уверенность", "en": "Confidence"},
    "conf_low": {"ru": "низкая", "en": "low"},
    "conf_medium": {"ru": "средняя", "en": "medium"},
    "conf_high": {"ru": "высокая", "en": "high"},
    "k_feasibility": {"ru": "Выполнимость в Чехии", "en": "Czech Feasibility Score"},
    "k_mrr": {"ru": "MRR на 12-й месяц", "en": "Month-12 MRR"},
    "k_customers": {"ru": "{n} клиентов", "en": "{n} customers"},
    "k_profit": {"ru": "Чистая прибыль / мес. (12-й мес.)", "en": "Net profit / month (M12)"},
    "k_breakeven": {"ru": "Точка безубыточности", "en": "Break-even"},
    "tab_score": {"ru": "🎯 Скор", "en": "🎯 Score"},
    "tab_audience": {"ru": "👥 Аудитория", "en": "👥 Audience"},
    "tab_economics": {"ru": "💰 Юнит-экономика", "en": "💰 Unit economics"},
    "tab_competition": {"ru": "🏁 Конкуренция", "en": "🏁 Competition"},
    "tab_roadmap": {"ru": "🗺️ План на 14 дней", "en": "🗺️ 14-day roadmap"},
    "tab_risks": {"ru": "⚠️ Риски и чек-лист", "en": "⚠️ Risks & checklist"},
    "tab_verify": {"ru": "✅ Проверить перед запуском", "en": "✅ Verify before launch"},
    "verify_intro": {"ru": "Факты, на которые опирается отчёт и которые могут устареть или оказаться неверными. "
                           "«Актуально на» — дата, которую отражает утверждение.",
                     "en": "Facts this report relies on that may be outdated or wrong. "
                           "'As of' is the date the claim reflects."},
    "verify_none": {"ru": "Отчёт сохранён до появления этого блока — запустите разбор заново.",
                    "en": "This report predates this section - run the deep-dive again."},
    "v_claim": {"ru": "Утверждение", "en": "Claim"},
    "v_topic": {"ru": "Тема", "en": "Topic"},
    "v_as_of": {"ru": "Актуально на", "en": "As of"},
    "v_where": {"ru": "Где проверить", "en": "Where to check"},
    "vt_tax": {"ru": "налоги", "en": "tax"},
    "vt_legal": {"ru": "право", "en": "legal"},
    "vt_competitor": {"ru": "конкуренты", "en": "competitor"},
    "vt_price": {"ru": "цена", "en": "price"},
    "vt_market": {"ru": "рынок", "en": "market"},
    "vt_integration": {"ru": "интеграции", "en": "integration"},
    "vt_other": {"ru": "другое", "en": "other"},
    "competitor_urls_note": {"ru": "Ссылки от LLM не проверены; сомнительные ссылки убраны автоматически.",
                             "en": "LLM links are not verified; doubtful links are removed automatically."},
    "czech_adjusted": {"ru": "**🇨🇿 Скор с поправками для Чехии: {cz}/100** (выполнимость {f})",
                       "en": "**🇨🇿 Czech-adjusted score: {cz}/100** (feasibility {f})"},
    "col_factor": {"ru": "Фактор", "en": "Factor"},
    "col_weight": {"ru": "Вес", "en": "Weight"},
    "col_rationale": {"ru": "Обоснование", "en": "Rationale"},
    "pain": {"ru": "Боль: {x}", "en": "Pain: {x}"},
    "wtp": {"ru": "Готовность платить: {x}", "en": "Willingness to pay: {x}"},
    "pricing": {"ru": "**Цены (CZK)**", "en": "**Pricing (CZK)**"},
    "col_tier": {"ru": "Тариф", "en": "Tier"},
    "col_price": {"ru": "Цена (CZK)", "en": "Price (CZK)"},
    "col_billing": {"ru": "Оплата", "en": "Billing"},
    "col_includes": {"ru": "Что входит", "en": "Includes"},
    "month": {"ru": "Месяц", "en": "Month"},
    "series": {"ru": "Ряд", "en": "Series"},
    "series_mrr": {"ru": "MRR (CZK)", "en": "MRR (CZK)"},
    "series_costs": {"ru": "Расходы в месяц (CZK)", "en": "Monthly costs (CZK)"},
    "czk_per_month": {"ru": "CZK / мес.", "en": "CZK / month"},
    "ramp_title": {"ru": "Рост выручки против расходов 12-го месяца", "en": "Revenue ramp vs. month-12 cost base"},
    "op_costs": {"ru": "**Операционные расходы в Чехии в месяц (на 12-й месяц)**",
                 "en": "**Monthly operating costs in Czechia (at month 12)**"},
    "col_item": {"ru": "Статья", "en": "Item"},
    "col_note": {"ru": "Примечание", "en": "Note"},
    "legal_form": {"ru": "**Правовая форма:** {x}", "en": "**Legal form:** {x}"},
    "col_name": {"ru": "Название", "en": "Name"},
    "col_kind": {"ru": "Тип", "en": "Type"},
    "col_threat": {"ru": "Угроза", "en": "Threat"},
    "col_gap": {"ru": "Незанятая ниша", "en": "Gap to exploit"},
    "kpi_label": {"ru": "KPI: {x}", "en": "KPI: {x}"},
    "risks": {"ru": "**Риски**", "en": "**Risks**"},
    "assumptions_h": {"ru": "**Допущения**", "en": "**Assumptions**"},
    "checklist": {"ru": "**Чек-лист локализации**", "en": "**Localisation checklist**"},
    "export_md": {"ru": "⬇️ Экспорт в Markdown", "en": "⬇️ Export Markdown"},
    "export_pdf": {"ru": "⬇️ Экспорт в PDF", "en": "⬇️ Export PDF"},
    "pdf_unavailable": {"ru": "Экспорт в PDF недоступен: {e}", "en": "PDF export unavailable: {e}"},

    # ---------------------------------------------------------------- misc
    "na": {"ru": "нет данных", "en": "n/a"},
    "choose": {"ru": "Выберите…", "en": "Choose options"},

    # ---------------------------------------------------------------- table
    "download_csv": {"ru": "⬇️ Скачать CSV", "en": "⬇️ Download CSV"},
}

# Column titles for the data table / chart tooltips (internal column key -> label).
COLUMNS: dict[str, dict[str, str]] = {
    "Name": {"ru": "Название"}, "Category": {"ru": "Категория"}, "Model type": {"ru": "Тип модели"},
    "Source": {"ru": "Источник"}, "Country": {"ru": "Страна"}, "Niche": {"ru": "Ниша"},
    "Score": {"ru": "Исходный скор"}, "Czech score": {"ru": "Чешский скор"}, "Price (CZK)": {"ru": "Цена (CZK)"},
    "CZK potential (M12 MRR)": {"ru": "Потенциал (MRR 12-го мес., CZK)"}, "MRR comparable": {"ru": "MRR сопоставим"},
    "MRR status": {"ru": "Статус MRR"}, "Customers needed": {"ru": "Нужно клиентов"}, "SAM": {"ru": "SAM"},
    "SAM share (12m)": {"ru": "Доля SAM (12 мес.)"}, "SAM source": {"ru": "Источник SAM"},
    "Local incumbents": {"ru": "Местные конкуренты"}, "Legal complexity": {"ru": "Юр. сложность"},
    "Integrations": {"ru": "Интеграции"}, "Launch by": {"ru": "Запустить до"},
    "Needs rethink for CZ": {"ru": "Переосмыслить для CZ"}, "Intl. MRR (USD)": {"ru": "MRR в мире (USD)"},
    "Revenue model": {"ru": "Модель выручки"}, "Problem": {"ru": "Проблема"}, "Tech stack": {"ru": "Технологии"},
    "URL": {"ru": "Сайт"},
}

MONTHS_RU = ["", "янв.", "февр.", "март", "апр.", "май", "июнь", "июль", "авг.", "сент.", "окт.", "нояб.", "дек."]

UI["methodology_md"] = {
    "ru": """
### Как устроен радар

**1. Источники.** База из 500 проверенных моделей из 60+ стран (выручка — приблизительные данные со слов
основателей, это сигнал масштаба, а не аудированные цифры), плюс по желанию живые ленты Hacker News *Show HN*
и Product Hunt. Можно добавить и свои идеи.

**2. Исходный скор.** У каждой модели есть чешские оценки от 1 до 5. Оценка выполнимости — взвешенная сумма:

| Фактор | Вес |
|---|---|
| Местный спрос | 28% |
| Свободная ниша (обратная величина местной конкуренции) | 20% |
| Простота запуска и работы | 14% |
| Регуляторная простота | 10% |
| Преимущество локализации | 14% |
| Доказанный спрос в мире (логарифм MRR) | 14% |

**3. Чешский скор.** Исходный скор минус чешские трудности: местные конкуренты (с учётом их силы), нужная доля
рынка за 12 месяцев (SAM по данным реестра ČSÚ, где он есть), юридическая сложность, сложные интеграции
(Pohoda, Money S3, ABRA, Bank iD, ISDOC) и стоимость поддержки на чешском для соло-основателя. Сезонность не
штрафует, а даёт рекомендацию по месяцу запуска. Все веса — в боковой панели.

**4. Потенциал в CZK.** Цена в мире × курс USD/CZK × поправка на покупательную способность (B2B 0,75, B2C 0,60),
округлённая до чешских «ценников», × число клиентов к 12-му месяцу. Для маркетплейсов без данных о GMV и для
физических товаров MRR помечается как несопоставимый.

**5. Разбор.** С ключом Anthropic или Gemini модель ИИ уточняет эвристику до полного отчёта и указывает свою
уверенность. Без ключа офлайн-движок мгновенно строит отчёт той же структуры.

**Оговорки.** Налоговые цифры (уровни paušální daň, порог НДС) — округлённые оценки на 2026 год, проверяйте
у бухгалтера или на *financnisprava.cz*. Списки конкурентов — отправная точка для вашего исследования; поля,
выведенные правилами, в карточках помечены как непроверенные.
""",
    "en": """
### How the radar works

**1. Sources.** A curated database of 500 proven models from 60+ countries (revenue figures are approximate,
self-reported numbers - an order-of-magnitude traction signal, not audited data), plus optional live feeds
from Hacker News *Show HN* and Product Hunt. You can also add your own ideas.

**2. Original score.** Every model carries Czech ratings from 1 to 5. The feasibility score is a weighted mix:

| Factor | Weight |
|---|---|
| Local demand | 28% |
| Competitive whitespace (inverse of local competition) | 20% |
| Build & ops simplicity | 14% |
| Regulatory ease | 10% |
| Localisation moat | 14% |
| Proven international traction (log of MRR) | 14% |

**3. Czech score.** The original score minus Czech frictions: local incumbents (by strength), the share of the
market needed within 12 months (SAM from the ČSÚ register where available), legal complexity, complex
integrations (Pohoda, Money S3, ABRA, Bank iD, ISDOC) and the cost of Czech-language support for a solo founder.
Seasonality adds a launch-month recommendation instead of a penalty. All weights are in the sidebar.

**4. CZK potential.** International price × USD/CZK × purchasing-power factor (B2B 0.75, B2C 0.60), rounded to
Czech price points, × customers at month 12. Marketplaces without GMV data and physical goods are flagged as
not comparable.

**5. Deep-Dive.** With an Anthropic or Gemini key, the LLM refines the heuristic into a full report and states
its confidence. Without a key, the offline engine produces the same structure instantly.

**Caveats.** Tax figures (paušální daň bands, VAT threshold) are rounded 2026 approximations - verify with an
accountant or *financnisprava.cz*. Competitor lists are starting points; rule-inferred fields are marked as
unverified on the cards.
""",
}
