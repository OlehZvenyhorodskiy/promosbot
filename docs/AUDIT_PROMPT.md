# Інструкція та готовий промпт для незалежного аудиту репозиторію

Цей документ містить прямі посилання на актуальний стан коду (коміт 2efe874) та готовий промпт для зовнішніх ШІ-моделей (Claude, ChatGPT тощо) для перевірки стійкості скрапінгу, обходу рейт-лімітів та архітектури.

---

## Актуальні посилання на GitHub

Репозиторій: [https://github.com/OlehZvenyhorodskiy/promosbot](https://github.com/OlehZvenyhorodskiy/promosbot)
Гілка: main
Останній коміт: [main](https://github.com/OlehZvenyhorodskiy/promosbot/commit/main)
Пряме посилання на дерево коду: [https://github.com/OlehZvenyhorodskiy/promosbot/tree/main](https://github.com/OlehZvenyhorodskiy/promosbot/tree/main)

### Прямі посилання на ключові файли:

1. [src/scrapers/engine.py](https://github.com/OlehZvenyhorodskiy/promosbot/blob/main/src/scrapers/engine.py)
   (Raw: https://raw.githubusercontent.com/OlehZvenyhorodskiy/promosbot/main/src/scrapers/engine.py)
   Інтеграція семафора обмеження конкурентності (max_concurrency=3), по-доменного RateLimiter (Token Bucket), повторних спроб async_retry та автоматичних CircuitBreaker.

2. [src/scrapers/base.py](https://github.com/OlehZvenyhorodskiy/promosbot/blob/main/src/scrapers/base.py)
   (Raw: https://raw.githubusercontent.com/OlehZvenyhorodskiy/promosbot/main/src/scrapers/base.py)
   Детермінований розрахунок SHA-256 fingerprint, функція нормалізації назв, безпечний SSL-контекст certifi через get_ssl_context.

3. [src/scrapers/lidl.py](https://github.com/OlehZvenyhorodskiy/promosbot/blob/main/src/scrapers/lidl.py)
   (Raw: https://raw.githubusercontent.com/OlehZvenyhorodskiy/promosbot/main/src/scrapers/lidl.py)
   Обхід ліміту заголовків Akamai через max_field_size=65536 та max_line_size=65536, декомпресія Brotli (Accept-Encoding br), перевірений SSL через certifi, картка Lidl Plus, фолбек на буклети.

4. [src/scrapers/colruyt.py](https://github.com/OlehZvenyhorodskiy/promosbot/blob/main/src/scrapers/colruyt.py)
   (Raw: https://raw.githubusercontent.com/OlehZvenyhorodskiy/promosbot/main/src/scrapers/colruyt.py)
   Робота через Colruyt Search API, картка Xtra, фолбек на HTML-картки та цифрові буклети Publitas, дедуплікація за fingerprint.

5. [src/scrapers/carrefour.py](https://github.com/OlehZvenyhorodskiy/promosbot/blob/main/src/scrapers/carrefour.py)
   (Raw: https://raw.githubusercontent.com/OlehZvenyhorodskiy/promosbot/main/src/scrapers/carrefour.py)
   Client Hints (sec-ch-ua, sec-ch-ua-mobile, sec-ch-ua-platform) для проходження WAF, парсинг структурованих даних JSON-LD (Product та ItemList), картка Bonus Card, фолбек на буклети.

6. [src/scrapers/kruidvat.py](https://github.com/OlehZvenyhorodskiy/promosbot/blob/main/src/scrapers/kruidvat.py)
   (Raw: https://raw.githubusercontent.com/OlehZvenyhorodskiy/promosbot/main/src/scrapers/kruidvat.py)
   Hybris REST API з пагінацією до 300 товарів (pageSize=100, 3 сторінки), збереження зворотної сумісності через аліас parse_json_api, картка Kruidvat Club, certifi SSL.

7. [src/scrapers/action.py](https://github.com/OlehZvenyhorodskiy/promosbot/blob/main/src/scrapers/action.py)
   (Raw: https://raw.githubusercontent.com/OlehZvenyhorodskiy/promosbot/main/src/scrapers/action.py)
   Трирівневий збір: прямий HTML з парсингом __NEXT_DATA__, фолбек на цифрові буклети Publitas та агрегатор Tiendeo.

8. [src/utils/rate_limiter.py](https://github.com/OlehZvenyhorodskiy/promosbot/blob/main/src/utils/rate_limiter.py)
   (Raw: https://raw.githubusercontent.com/OlehZvenyhorodskiy/promosbot/main/src/utils/rate_limiter.py)
   Асинхронний алгоритм Token Bucket (RateLimiter) та ізольований менеджер лімітів за доменами (PerDomainRateLimiter).

9. [src/utils/retry.py](https://github.com/OlehZvenyhorodskiy/promosbot/blob/main/src/utils/retry.py)
   (Raw: https://raw.githubusercontent.com/OlehZvenyhorodskiy/promosbot/main/src/utils/retry.py)
   Модуль безпечних повторів async_retry з експоненційним бекофом і джитер-рандомізацією для мережевих помилок.

10. [src/utils/circuit_breaker.py](https://github.com/OlehZvenyhorodskiy/promosbot/blob/main/src/utils/circuit_breaker.py)
    (Raw: https://raw.githubusercontent.com/OlehZvenyhorodskiy/promosbot/main/src/utils/circuit_breaker.py)
    Захист від каскадних падінь зі станами CLOSED, OPEN, HALF_OPEN і тайм-аутом відновлення.

11. [src/main.py](https://github.com/OlehZvenyhorodskiy/promosbot/blob/main/src/main.py)
    (Raw: https://raw.githubusercontent.com/OlehZvenyhorodskiy/promosbot/main/src/main.py)
    Коректна обробка сигналів SIGTERM і SIGINT для безпечної зупинки сервісу в контейнерах Cloud Run без пошкодження даних.

12. [src/web/server.py](https://github.com/OlehZvenyhorodskiy/promosbot/blob/main/src/web/server.py)
    (Raw: https://raw.githubusercontent.com/OlehZvenyhorodskiy/promosbot/main/src/web/server.py)
    Ендпоінти моніторингу стану сервісу: /api/v1/health/scrapers, /health та /ping.

13. [tests/](https://github.com/OlehZvenyhorodskiy/promosbot/tree/main/tests)
    37 автоматичних юніт-тестів, що покривають дедуплікацію, мовні переклади, буклети, захисні утиліти та логіку скрапінгу.

---

## Готовий промпт для зовнішнього аудиту

Скопіюйте текст нижче та надішліть його моделі ШІ:

```text
Ти виступаєш у ролі Principal Python Architect та Lead Data Scraping Engineer. Проведи технічний аудит репозиторію бельгійського Telegram-бота для моніторингу знижок:
https://github.com/OlehZvenyhorodskiy/promosbot (коміт main).

Зверни увагу: перевіряй актуальний код саме за комітом main, де реалізовано всі захисні механізми та оновлені модулі:
- Дерево репозиторію: https://github.com/OlehZvenyhorodskiy/promosbot/tree/main
- Головний рушій скрапінгу: https://raw.githubusercontent.com/OlehZvenyhorodskiy/promosbot/main/src/scrapers/engine.py
- Базовий модуль та SSL certifi: https://raw.githubusercontent.com/OlehZvenyhorodskiy/promosbot/main/src/scrapers/base.py
- Модулі супермаркетів:
  * Lidl (Akamai 64KB headers, Brotli, certifi SSL, Lidl Plus): https://raw.githubusercontent.com/OlehZvenyhorodskiy/promosbot/main/src/scrapers/lidl.py
  * Colruyt (Search API, Xtra loyalty, Publitas fallback): https://raw.githubusercontent.com/OlehZvenyhorodskiy/promosbot/main/src/scrapers/colruyt.py
  * Carrefour (Client Hints sec-ch-ua, JSON-LD Product/ItemList, Bonus Card): https://raw.githubusercontent.com/OlehZvenyhorodskiy/promosbot/main/src/scrapers/carrefour.py
  * Kruidvat (Hybris API з пагінацією 300 товарів, certifi SSL, Club card): https://raw.githubusercontent.com/OlehZvenyhorodskiy/promosbot/main/src/scrapers/kruidvat.py
  * Action (HTML + Next.js + Publitas + Tiendeo): https://raw.githubusercontent.com/OlehZvenyhorodskiy/promosbot/main/src/scrapers/action.py
- Захисні утиліти:
  * Token Bucket RateLimiter: https://raw.githubusercontent.com/OlehZvenyhorodskiy/promosbot/main/src/utils/rate_limiter.py
  * Exponential Backoff Retry: https://raw.githubusercontent.com/OlehZvenyhorodskiy/promosbot/main/src/utils/retry.py
  * CircuitBreaker: https://raw.githubusercontent.com/OlehZvenyhorodskiy/promosbot/main/src/utils/circuit_breaker.py
- Моніторинг та завершення процесів:
  * Graceful shutdown SIGTERM/SIGINT: https://raw.githubusercontent.com/OlehZvenyhorodskiy/promosbot/main/src/main.py
  * Scraper health endpoint /api/v1/health/scrapers: https://raw.githubusercontent.com/OlehZvenyhorodskiy/promosbot/main/src/web/server.py

Критерії оцінки:
1. Захист від блокувань і лімітів (Rate Limiting та Concurrency):
Оціни інтеграцію asyncio.Semaphore(max_concurrency=3), PerDomainRateLimiter, CircuitBreaker та async_retry в ScraperEngine. Наскільки надійно це захищає IP-адресу Cloud Run від 429 Too Many Requests і блокувань при одночасному опитуванні 10+ мереж?

2. Стійкість скраперів складних мереж:
Оціни технічні рішення для Lidl (Akamai headers 65536, Brotli), Colruyt (Search API), Carrefour (Client Hints), Kruidvat (Hybris API pagination до 300 товарів) та Action (3-рівневий збір). Чи витримає система тривалу роботу у фоновому режимі?

3. Цілісність даних та дедуплікація:
Оціни детермінований алгоритм SHA-256 fingerprinting у base.py та об'єднання даних з сайтів, буклетів Publitas і Tiendeo.

4. Готовність до продакшну:
Перевір коректність SSL через certifi, обробку сигналів SIGTERM у main.py для Cloud Run, та ендпоінти моніторингу здоров'я скраперів.

5. Підсумковий вердикт:
Дай об'єктивну оцінку за шкалою від 1 до 10 та виділи ключові переваги та можливі рекомендації для подальшого розвитку.
```
