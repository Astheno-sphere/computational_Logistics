import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import type { DeliveryClient } from "../client.js";
import { DESTRUCTIVE, fail, ok, paymentMethodEnum, READ_ONLY, WRITE } from "./util.js";

export function registerPlatformTools(server: McpServer, client: DeliveryClient): void {
  server.registerTool(
    "platform_list_pickup_points",
    {
      title: "Платформа: список ПВЗ и постаматов",
      annotations: READ_ONLY,
      description:
        "Список ПВЗ, постаматов и точек самопривоза платформенного контура (доставка «в другой день»). " +
        "Возвращает points [{id, operator_id, name, type, position {latitude, longitude}, address, " +
        "payment_methods, schedule, available_for_dropoff, dayoffs}]. id точки используется как " +
        "platform_station в destination инструмента platform_create_offers. ВНИМАНИЕ: пустое тело " +
        "вернёт ВСЕ точки (их очень много) — задавайте хотя бы один фильтр (geo_id, диапазон координат " +
        "или pickup_point_ids).",
      inputSchema: {
        pickup_point_ids: z.array(z.string()).optional().describe("Точечный запрос по id точек."),
        geo_id: z
          .number()
          .int()
          .optional()
          .describe("Гео-id города/региона по геобазе Яндекса, например 213 — Москва."),
        latitude: z
          .object({
            from: z.number().describe("Нижняя граница широты."),
            to: z.number().describe("Верхняя граница широты."),
          })
          .optional()
          .describe("Диапазон по широте {from, to}."),
        longitude: z
          .object({
            from: z.number().describe("Нижняя граница долготы."),
            to: z.number().describe("Верхняя граница долготы."),
          })
          .optional()
          .describe("Диапазон по долготе {from, to}."),
        type: z
          .enum(["pickup_point", "terminal", "warehouse"])
          .optional()
          .describe("Тип точки: pickup_point — ПВЗ, terminal — постамат, warehouse — точка самопривоза."),
        payment_method: paymentMethodEnum()
          .optional()
          .describe("Только точки, поддерживающие способ оплаты: already_paid, card_on_receipt, postpay."),
        payment_methods: z
          .array(paymentMethodEnum())
          .optional()
          .describe("Несколько способов оплаты сразу."),
        available_for_dropoff: z
          .boolean()
          .optional()
          .describe("true — только точки, куда можно самопривозить отправления."),
        is_yandex_branded: z.boolean().optional().describe("true — только брендированные ПВЗ Яндекса."),
        operator_ids: z.array(z.string()).optional().describe("Фильтр по операторам точек."),
        pickup_services: z.array(z.string()).optional().describe("Фильтр по доступным услугам точки."),
      },
    },
    async (filters) => {
      try {
        return ok(await client.listPickupPoints(filters));
      } catch (e) {
        return fail(e);
      }
    },
  );

  server.registerTool(
    "platform_create_offers",
    {
      title: "Платформа: рассчитать варианты доставки",
      annotations: WRITE,
      description:
        "Рассчитывает варианты доставки (офферы) для заказа «в другой день» (НДД/ПВЗ). Возвращает offers " +
        "[{offer_id, expires_at, offer_details {delivery_interval {min, max, policy}, pickup_interval, " +
        "pricing, pricing_total, pricing_commission_on_delivery_payment}}]. Оффер действует до expires_at — " +
        "выбранный вариант бронируется инструментом platform_confirm_offer (до подтверждения заказ НЕ создан). " +
        "Ошибка 400 no_delivery_options — на выбранный интервал вариантов доставки нет. " +
        "Денежные суммы — в копейках (целые числа).",
      inputSchema: {
        info: z
          .object({
            operator_request_id: z
              .string()
              .describe("Уникальный id заказа на стороне магазина (идемпотентность расчёта)."),
            merchant_id: z.string().optional().describe("id мерчанта (если в кабинете их несколько)."),
            comment: z.string().optional().describe("Комментарий к заказу."),
          })
          .passthrough()
          .describe("Служебная информация о заказе."),
        source: z
          .object({
            platform_station: z
              .object({
                platform_id: z.string().describe("id станции отгрузки (platform_station_id из ЛК)."),
              })
              .passthrough()
              .describe("Станция самопривоза/склад отгрузки."),
            interval_utc: z
              .object({
                from: z.string().describe("Начало интервала (UTC, ISO-8601)."),
                to: z.string().describe("Конец интервала (UTC, ISO-8601)."),
              })
              .passthrough()
              .optional()
              .describe("Желаемый интервал отгрузки (UTC)."),
          })
          .passthrough()
          .describe("Откуда забирать отправление."),
        destination: z
          .object({
            platform_station: z
              .object({
                platform_id: z.string().describe("id ПВЗ/постамата из platform_list_pickup_points."),
              })
              .passthrough()
              .optional()
              .describe("Доставка в ПВЗ/постамат."),
            custom_location: z
              .record(z.any())
              .optional()
              .describe(
                "Курьерская доставка по адресу: {details: {full_address: \"...\"}} и/или {latitude, longitude}. " +
                  "Полная схема — в документации метода offers/create.",
              ),
            interval_utc: z
              .object({
                from: z.string().describe("Начало интервала (UTC, ISO-8601)."),
                to: z.string().describe("Конец интервала (UTC, ISO-8601)."),
              })
              .passthrough()
              .optional()
              .describe("Желаемый интервал доставки (UTC)."),
          })
          .passthrough()
          .describe("Куда доставить: platform_station (ПВЗ/постамат) ИЛИ custom_location (адрес курьером)."),
        items: z
          .array(
            z
              .object({
                count: z.number().int().min(1).describe("Количество единиц."),
                name: z.string().describe("Название товара."),
                article: z.string().optional().describe("Артикул товара."),
                billing_details: z
                  .object({
                    unit_price: z.number().describe("Цена за единицу, копейки (целое число)."),
                    assessed_unit_price: z
                      .number()
                      .optional()
                      .describe("Оценочная стоимость единицы, копейки."),
                    currency: z.string().optional().describe("Валюта, например RUB."),
                  })
                  .passthrough()
                  .optional()
                  .describe("Стоимость товара."),
                physical_dims: z
                  .object({
                    weight_gross: z.number().optional().describe("Вес брутто, граммы."),
                    dx: z.number().optional().describe("Длина, см."),
                    dy: z.number().optional().describe("Ширина, см."),
                    dz: z.number().optional().describe("Высота, см."),
                  })
                  .passthrough()
                  .optional()
                  .describe("Габариты и вес товара."),
                place_barcode: z.string().optional().describe("Штрихкод грузоместа, в котором лежит товар."),
              })
              .passthrough(),
          )
          .min(1)
          .describe("Товары заказа."),
        places: z
          .array(
            z
              .object({
                barcode: z.string().describe("Штрихкод грузоместа."),
                physical_dims: z
                  .object({
                    weight_gross: z.number().optional().describe("Вес брутто, граммы."),
                    dx: z.number().optional().describe("Длина, см."),
                    dy: z.number().optional().describe("Ширина, см."),
                    dz: z.number().optional().describe("Высота, см."),
                  })
                  .passthrough()
                  .optional()
                  .describe("Габариты и вес грузоместа."),
              })
              .passthrough(),
          )
          .min(1)
          .describe("Грузоместа (коробки)."),
        billing_info: z
          .object({
            payment_method: paymentMethodEnum().describe(
              "already_paid — заказ уже оплачен, card_on_receipt — карта при получении, postpay — постоплата.",
            ),
            delivery_cost: z
              .number()
              .optional()
              .describe("Стоимость доставки для получателя, копейки."),
          })
          .passthrough()
          .describe("Параметры оплаты."),
        recipient_info: z
          .object({
            first_name: z.string().describe("Имя получателя."),
            last_name: z.string().optional().describe("Фамилия получателя."),
            phone: z.string().describe("Телефон получателя, например +79991234567."),
            email: z.string().optional().describe("Email получателя."),
          })
          .passthrough()
          .describe("Получатель."),
        last_mile_policy: z
          .enum(["time_interval", "self_pickup"])
          .describe(
            "Последняя миля: time_interval — курьерская доставка в интервал, self_pickup — самовывоз из ПВЗ/постамата.",
          ),
        particular_items_refuse: z
          .boolean()
          .optional()
          .describe("true — разрешить частичный выкуп (отказ от части товаров)."),
        forbid_unboxing: z.boolean().optional().describe("true — запретить вскрытие при получении."),
      },
    },
    async (body) => {
      try {
        return ok(await client.createOffers(body));
      } catch (e) {
        return fail(e);
      }
    },
  );

  server.registerTool(
    "platform_confirm_offer",
    {
      title: "Платформа: подтвердить оффер",
      annotations: WRITE,
      description:
        "Бронирует выбранный оффер — СОЗДАЁТ заказ в логистической платформе. Возвращает request_id " +
        "(id заказа, например «77241d8009bb46d0bff5c65a73077bcd-udp») — используйте его в " +
        "platform_get_request, platform_request_history и platform_cancel_request. Оффер должен быть " +
        "не просрочен (см. expires_at из platform_create_offers), иначе 400 bad_request.",
      inputSchema: {
        offer_id: z.string().min(1).describe("offer_id выбранного варианта из ответа platform_create_offers."),
      },
    },
    async ({ offer_id }) => {
      try {
        return ok(await client.confirmOffer(offer_id));
      } catch (e) {
        return fail(e);
      }
    },
  );

  server.registerTool(
    "platform_get_request",
    {
      title: "Платформа: информация о заказе",
      annotations: READ_ONLY,
      description:
        "Информация о заказе НДД: state {status (например CREATED), description, timestamp, timestamp_utc, " +
        "reason}, request (адреса, товары, получатель) и courier_order_id. Возможные причины отмены: " +
        "SHOP_CANCELLED, USER_CHANGED_MIND, DELIVERY_PROBLEMS, BROKEN_ITEM и др.",
      inputSchema: {
        request_id: z
          .string()
          .min(1)
          .describe("id заказа в платформе (из platform_confirm_offer)."),
        request_code: z
          .string()
          .optional()
          .describe("Номер заказа в системе заказчика (дополнительный фильтр)."),
        slim: z.boolean().optional().describe("true — сокращённый ответ."),
      },
    },
    async ({ request_id, request_code, slim }) => {
      try {
        return ok(await client.getRequest({ request_id, request_code, slim }));
      } catch (e) {
        return fail(e);
      }
    },
  );

  server.registerTool(
    "platform_request_history",
    {
      title: "Платформа: история статусов заказа",
      annotations: READ_ONLY,
      description:
        "История смены статусов заказа НДД: state_history [{status, description, timestamp (unix), " +
        "timestamp_utc (ISO-8601), reason?}] — от создания до текущего момента.",
      inputSchema: {
        request_id: z
          .string()
          .min(1)
          .describe("id заказа в платформе (из platform_confirm_offer)."),
      },
    },
    async ({ request_id }) => {
      try {
        return ok(await client.requestHistory(request_id));
      } catch (e) {
        return fail(e);
      }
    },
  );

  server.registerTool(
    "platform_cancel_request",
    {
      title: "Платформа: отменить заказ",
      annotations: DESTRUCTIVE,
      description:
        "Отменяет заказ в логистической платформе. Курьерский заказ можно отменить до статуса " +
        "DELIVERY_TRANSPORTATION_RECIPIENT (передача получателю). Возвращает status " +
        "(CREATED | SUCCESS | ERROR), reason и description. Ошибки: 403 — чужой заказ/нет прав, 404 — не найден.",
      inputSchema: {
        request_id: z
          .string()
          .min(1)
          .describe("id заказа в платформе (из platform_confirm_offer)."),
      },
    },
    async ({ request_id }) => {
      try {
        return ok(await client.cancelRequest(request_id));
      } catch (e) {
        return fail(e);
      }
    },
  );
}
