# Інструкція та готовий промпт для незалежного аудиту репозиторію

Цей файл містить прямі посилання на актуальний стан кодової бази та готовий промпт для аналізу проєкту зовнішніми ШІ-моделями (Claude, ChatGPT тощо).

---

## Актуальні посилання на GitHub

- **Репозиторій**: [https://github.com/OlehZvenyhorodskiy/promosbot](https://github.com/OlehZvenyhorodskiy/promosbot)
- **Гілка**: `main`
- **Останній стабільний коміт**: `f7688aa` (або актуальний HEAD гілки `main`)
- **Пряме посилання на дерево коду**: [https://github.com/OlehZvenyhorodskiy/promosbot/tree/main](https://github.com/OlehZvenyhorodskiy/promosbot/tree/main)

### Ключові файли для перевірки:
1. [src/scrapers/base.py](https://github.com/OlehZvenyhorodskiy/promosbot/blob/main/src/scrapers/base.py): нормалізація назв та генерація SHA-256 fingerprint (`generate_fingerprint`).
2. [src/scrapers/models.py](https://github.com/OlehZvenyhorodskiy/promosbot/blob/main/src/scrapers/models.py): розширена модель `PromoItem` (включаючи `fingerprint`, `source_type`, `leaflet_id`, `page_number`, `coordinates`, `loyalty_card`).
3. [src/utils/circuit_breaker.py](https://github.com/OlehZvenyhorodskiy/promosbot/blob/main/src/utils/circuit_breaker.py): стан CLOSED/OPEN/HALF_OPEN для захисту від каскадних збоїв скраперів.
4. [src/utils/rate_limiter.py](https://github.com/OlehZvenyhorodskiy/promosbot/blob/main/src/utils/rate_limiter.py): асинхронний Token Bucket RateLimiter та PerDomainRateLimiter для запобігання IP-банам.
5. [src/utils/retry.py](https://github.com/OlehZvenyhorodskiy/promosbot/blob/main/src/utils/retry.py): повторні запити з експоненційним бекофом та джитер-рандомізацією.
6. [src/scrapers/lidl.py](https://github.com/OlehZvenyhorodskiy/promosbot/blob/main/src/scrapers/lidl.py): обхід ліміту заголовків Akamai (`max_field_size=65536`), декомпресія Brotli, фолбек на буклети.
7. [src/scrapers/colruyt.py](https://github.com/OlehZvenyhorodskiy/promosbot/blob/main/src/scrapers/colruyt.py): робота через Colruyt Search API, картка Xtra, фолбек на буклети.
8. [src/scrapers/carrefour.py](https://github.com/OlehZvenyhorodskiy/promosbot/blob/main/src/scrapers/carrefour.py): Client Hints для проходження WAF, парсинг JSON-LD (`Product` та `ItemList`), бонусна картка.
9. [src/scrapers/kruidvat.py](https://github.com/OlehZvenyhorodskiy/promosbot/blob/main/src/scrapers/kruidvat.py): Hybris REST API з пагінацією, знижки та Club картка.
10. [src/scrapers/action.py](https://github.com/OlehZvenyhorodskiy/promosbot/blob/main/src/scrapers/action.py): трирівневий збір (HTML/Next.js -> буклети Publitas -> агрегатор Tiendeo).
11. [src/scrapers/leaflets/orchestrator.py](https://github.com/OlehZvenyhorodskiy/promosbot/blob/main/src/scrapers/leaflets/orchestrator.py): повноцінний збір буклетів для 11 бельгійських мереж.
12. [src/i18n/translations.py](https://github.com/OlehZvenyhorodskiy/promosbot/blob/main/src/i18n/translations.py) та [src/bot/formatters.py](https://github.com/OlehZvenyhorodskiy/promosbot/blob/main/src/bot/formatters.py): інтелектуальний переклад умов акцій (1+1, 3e gratis, безкоштовна доставка тощо).
13. [src/db/database.py](https://github.com/OlehZvenyhorodskiy/promosbot/blob/main/src/db/database.py): міграції, дедуплікація, індекси на `fingerprint`, `source_type` та складений `(store_id, category_id)`.
14. [tests/](https://github.com/OlehZvenyhorodskiy/promosbot/tree/main/tests): 36 успішних юніт-тестів на всі компоненти системи.

---

## Текст промпту для копіювання

Скопіюйте блок нижче та надішліть його у вікно ШІ:

```markdown
Ти — Principal Python Architect та Lead Data Scraping Engineer. Проведи актуальний та об'єктивний технічний аудит репозиторію бельгійського Telegram-бота для відстеження знижок:
https://github.com/OlehZvenyhorodskiy/promosbot (гілка main, актуальний коміт).

ВАЖЛИВО: Перевіряй саме поточну версію коду за посиланням вище, а не застарілий кеш чи початковий стан проекту. 

У проекті вже реалізовано:
1. Детермінована дедуплікація за SHA-256 fingerprint: функція generate_fingerprint у src/scrapers/base.py та розширена модель PromoItem у src/scrapers/models.py (з полями fingerprint, source_type, leaflet_id, page_number, loyalty_card тощо).
2. Ізоляція збоїв: CircuitBreaker у src/utils/circuit_breaker.py з переходом у CLOSED/OPEN/HALF_OPEN.
3. Захист від блокувань та рейт-лімітинг: RateLimiter (Token Bucket) та PerDomainRateLimiter у src/utils/rate_limiter.py, а також модуль безпечних повторів async_retry у src/utils/retry.py.
4. Скрапери складних мереж:
   - Lidl (src/scrapers/lidl.py): обхід Akamai header limit через max_field_size=65536, підтримка Brotli, картка Lidl Plus та фолбек на буклети.
   - Colruyt (src/scrapers/colruyt.py): прямий виклик Search API, картка Xtra, парсинг дат та фолбек на буклети.
   - Carrefour (src/scrapers/carrefour.py): Client Hints (sec-ch-ua) для проходження WAF, парсинг JSON-LD (Product та ItemList), картка Bonus Card.
   - Kruidvat (src/scrapers/kruidvat.py): Hybris API з пагінацією до 300 товарів, збереження зворотної сумісності через аліас parse_json_api.
   - Action (src/scrapers/action.py): трирівневий збір (HTML -> Publitas буклети -> Tiendeo).
5. Рушій буклетів (src/scrapers/leaflets/): PublitasLeafletExtractor, TiendeoAggregator, PDFLeafletExtractor та оркестратор з підтримкою 11 бельгійських мереж.
6. Локалізація: функція localize_discount_text у src/i18n/translations.py для перекладу нідерландських та французьких промо-термінів на мову користувача бота (3e gratis -> 3-й безкоштовно тощо).
7. База даних: автоматичні безпечні міграції в src/db/database.py, індекси на fingerprint, source_type та складений індекс (store_id, category_id).
8. Тестове покриття: 36 юніт-тестів у директорії tests/ (всі проходять успішно).

Проведи детальний аналіз за такими критеріями:
1. Надійність скрапінгу: наскільки стійкі запропоновані рішення для Colruyt, Carrefour, Lidl, Action, Kruidvat при довгостроковій роботі у фоновому режимі?
2. Робота захисних механізмів: оціни ефективність комбінації CircuitBreaker + RateLimiter + async_retry для запобігання бана IP-адреси на Cloud Run.
3. Цілісність даних: оціни алгоритм нормалізації та розрахунку fingerprint при злитті даних з вебсайтів та цифрових буклетів.
4. Оцінка готовності до продакшну: які залишилися дрібні нюанси, що можуть проявитися при навантаженні?
5. Фінальний вердикт та оцінка проекту за шкалою від 1 до 10.
```
