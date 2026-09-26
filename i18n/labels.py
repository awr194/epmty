"""Russian labels for fixed vocabularies (categories, model types, countries, statuses, fields)."""

CATEGORY_RU = {
    "Dev & Productivity Tools": "Инструменты для разработки и продуктивности",
    "Marketing & Growth": "Маркетинг и рост",
    "E-commerce Add-ons": "Дополнения для e-commerce",
    "Creator Economy": "Экономика авторов",
    "Local Services": "Локальные услуги",
    "AI Tools": "ИИ-инструменты",
    "Finance & Admin": "Финансы и администрирование",
    "Hospitality & Gastro": "Гостиничный бизнес и общепит",
    "Communities & Marketplaces": "Сообщества и маркетплейсы",
    "D2C & Subscriptions": "D2C и подписки",
    "Health & Wellness": "Здоровье и велнес",
    "Education & EdTech": "Образование и EdTech",
}

MODEL_TYPE_RU = {
    "saas": "SaaS",
    "marketplace": "маркетплейс",
    "d2c_physical": "физический D2C",
    "offline_retail": "офлайн-розница",
    "service": "услуга",
}

MRR_STATUS_RU = {
    "comparable": "Регулярная выручка (сопоставима)",
    "marketplace_gmv": "Маркетплейс: take rate × GMV",
    "marketplace_no_gmv": "Маркетплейс без данных о GMV — MRR не сопоставим",
    "not_recurring": "Продажи физических товаров / розница — не SaaS-MRR",
}

FIELD_RU = {
    "model_type": "тип модели",
    "local_incumbents": "местные конкуренты",
    "legal_complexity": "юридическая сложность",
    "required_integrations": "интеграции",
    "seasonality": "сезонность",
    "czech_support_required": "поддержка на чешском",
    "price_includes_vat": "цена с DPH",
    "target_nace": "коды CZ-NACE",
    "sam_estimate": "размер рынка (SAM)",
    "sam_source": "источник SAM",
}

COUNTRY_RU = {
    "Argentina": "Аргентина", "Armenia": "Армения", "Australia": "Австралия", "Austria": "Австрия",
    "Bangladesh": "Бангладеш", "Belarus": "Беларусь", "Belgium": "Бельгия", "Brazil": "Бразилия",
    "Canada": "Канада", "Chile": "Чили", "China": "Китай", "Colombia": "Колумбия", "Croatia": "Хорватия",
    "Custom": "Своя идея", "Denmark": "Дания", "Egypt": "Египет", "Estonia": "Эстония", "Finland": "Финляндия",
    "France": "Франция", "Germany": "Германия", "Global / remote": "Глобально / удалённо", "Greece": "Греция",
    "Hong Kong": "Гонконг", "Hungary": "Венгрия", "India": "Индия", "Indonesia": "Индонезия", "Ireland": "Ирландия",
    "Israel": "Израиль", "Italy": "Италия", "Japan": "Япония", "Kazakhstan": "Казахстан", "Kenya": "Кения",
    "Latvia": "Латвия", "Lithuania": "Литва", "Malaysia": "Малайзия", "Malta": "Мальта", "Mexico": "Мексика",
    "Morocco": "Марокко", "Netherlands": "Нидерланды", "New Zealand": "Новая Зеландия", "Nigeria": "Нигерия",
    "North America": "Северная Америка", "Norway": "Норвегия", "Peru": "Перу", "Philippines": "Филиппины",
    "Poland": "Польша", "Romania": "Румыния", "Russia": "Россия", "Saudi Arabia": "Саудовская Аравия",
    "Singapore": "Сингапур", "Slovakia": "Словакия", "Slovenia": "Словения", "South Africa": "ЮАР",
    "South Korea": "Южная Корея", "Spain": "Испания", "Sweden": "Швеция", "Switzerland": "Швейцария",
    "Taiwan": "Тайвань", "Thailand": "Таиланд", "Turkey": "Турция", "UAE": "ОАЭ", "UK": "Великобритания",
    "Ukraine": "Украина", "Unknown": "Неизвестно", "USA": "США", "Vietnam": "Вьетнам",
}
