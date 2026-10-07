# A1 · Яндекс Доставка · Каталог MCP-возможностей

Этот каталог описывает 16 MCP-инструментов (tools), через которые ИИ-ассистент работает с корпоративным аккаунтом Яндекс Доставки. Выберите не техническое имя, а действие, которое хотите выполнить.

## Доставка день в день

| Что нужно сделать | MCP-инструмент | Воздействие |
|---|---|---|
| Заранее узнать стоимость и ETA | [express_check_price](./express_check_price.md) | Только чтение |
| Подготовить новую заявку | [express_create_claim](./express_create_claim.md) | Изменяет данные |
| Проверить статус и детали заявки | [express_get_claim](./express_get_claim.md) | Только чтение |
| Подтвердить заявку и начать поиск курьера | [express_accept_claim](./express_accept_claim.md) | Изменяет данные |
| Узнать возможность и стоимость отмены | [express_cancel_info](./express_cancel_info.md) | Только чтение |
| Отменить заявку | [express_cancel_claim](./express_cancel_claim.md) | Опасная операция |
| Найти заявки по фильтрам | [express_search_claims](./express_search_claims.md) | Только чтение |
| Узнать текущую позицию курьера | [express_performer_position](./express_performer_position.md) | Только чтение |
| Получить ссылку для получателя | [express_tracking_links](./express_tracking_links.md) | Только чтение |

Реальная экспресс-доставка начинается после <code>express_accept_claim</code>. Сам расчёт стоимости и создание неподтверждённой заявки ещё не запускают поиск курьера, если при создании не использован <code>auto_accept=true</code>.

## Доставка на другой день, в ПВЗ и постаматы

| Что нужно сделать | MCP-инструмент | Воздействие |
|---|---|---|
| Найти ПВЗ, постамат или точку самопривоза | [platform_list_pickup_points](./platform_list_pickup_points.md) | Только чтение |
| Рассчитать доступные варианты доставки | [platform_create_offers](./platform_create_offers.md) | Изменяет данные |
| Забронировать вариант и создать заказ | [platform_confirm_offer](./platform_confirm_offer.md) | Изменяет данные |
| Проверить текущее состояние заказа | [platform_get_request](./platform_get_request.md) | Только чтение |
| Посмотреть историю статусов | [platform_request_history](./platform_request_history.md) | Только чтение |
| Отменить заказ | [platform_cancel_request](./platform_cancel_request.md) | Опасная операция |

Заказ на другой день создаётся только после <code>platform_confirm_offer</code>. Расчёт вариантов через <code>platform_create_offers</code> заказ не оформляет.

## Дополнительные методы API

| Что нужно сделать | MCP-инструмент | Воздействие |
|---|---|---|
| Вызвать метод B2B API без отдельного инструмента | [raw_request](./raw_request.md) | Опасная операция |

<code>raw_request</code> предназначен для технических пользователей, которые знают точный путь, HTTP-метод и контракт выбранного метода API.

## Форматы данных

- В Express деньги передаются строками decimal, вес — в килограммах, размеры — в метрах.
- В Platform деньги передаются целыми значениями в копейках, вес — в граммах, размеры — в сантиметрах.
- Полные схемы, статусы и системные ограничения собраны в [техническом справочнике](../TOOLS.md).
