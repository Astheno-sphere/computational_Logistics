import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import type { DeliveryClient } from "../client.js";
import {
  cargoTypeEnum,
  claimId,
  DESTRUCTIVE,
  fail,
  ok,
  READ_ONLY,
  rfc3339Date,
  taxiClassEnum,
  WRITE,
} from "./util.js";

/** Известные статусы экспресс-заявки (для описаний; фильтр в поиске — строка). */
const CLAIM_STATUSES =
  "new, estimating, ready_for_approval, accepted, performer_lookup, performer_found, " +
  "performer_not_found, pickup_arrived, pickuped, delivery_arrived, delivered, " +
  "returning, returned, failed, cancelled, cancelled_by_taxi";

export function registerExpressTools(server: McpServer, client: DeliveryClient): void {
  server.registerTool(
    "express_check_price",
    {
      title: "Экспресс: оценка стоимости",
      annotations: READ_ONLY,
      description:
        "Первичная оценка стоимости экспресс-доставки (день в день) БЕЗ создания заявки. " +
        "Возвращает price (строка-decimal, не число!), currency_rules {code, sign}, distance_meters, " +
        "eta (минуты) и zone_id. Точки маршрута задаются координатами [долгота, широта] и/или адресом " +
        "строкой. Типовые ошибки: 400 address_not_found (адрес не распознан), " +
        "409 estimating.cant_construct_route (маршрут не строится).",
      inputSchema: {
        route_points: z
          .array(
            z
              .object({
                id: z.number().int().optional().describe("id точки (на него ссылаются pickup_point/dropoff_point товаров)."),
                coordinates: z
                  .array(z.number())
                  .length(2)
                  .optional()
                  .describe("Координаты точки [долгота, широта], например [37.588074, 55.733924]."),
                fullname: z
                  .string()
                  .optional()
                  .describe("Полный адрес строкой, например «Москва, ул. Льва Толстого, 16»."),
              })
              .passthrough(),
          )
          .min(1)
          .describe("Точки маршрута: координаты и/или адрес (хотя бы одно из двух у каждой точки)."),
        items: z
          .array(
            z
              .object({
                quantity: z.number().int().min(1).describe("Количество единиц товара."),
                size: z
                  .object({
                    length: z.number().describe("Длина, метры."),
                    width: z.number().describe("Ширина, метры."),
                    height: z.number().describe("Высота, метры."),
                  })
                  .optional()
                  .describe("Габариты единицы товара в МЕТРАХ."),
                weight: z.number().optional().describe("Вес единицы товара, кг."),
                pickup_point: z.number().int().optional().describe("id точки забора из route_points."),
                dropoff_point: z.number().int().optional().describe("id точки вручения из route_points."),
              })
              .passthrough(),
          )
          .min(1)
          .describe("Товары/грузоместа."),
        requirements: z
          .object({
            taxi_class: taxiClassEnum().optional().describe("Класс доставки: courier, express или cargo."),
            cargo_type: cargoTypeEnum().optional().describe("Тип кузова для cargo: van, lcv_m, lcv_l."),
          })
          .passthrough()
          .optional()
          .describe("Требования к доставке (класс, тип кузова, доп. опции)."),
        skip_door_to_door: z
          .boolean()
          .optional()
          .describe("true — отключить доставку до двери (по умолчанию false)."),
      },
    },
    async (body) => {
      try {
        return ok(await client.checkPrice(body));
      } catch (e) {
        return fail(e);
      }
    },
  );

  server.registerTool(
    "express_create_claim",
    {
      title: "Экспресс: создать заявку",
      annotations: WRITE,
      description:
        "Создаёт заявку на экспресс-доставку. ВАЖНО: заявка не запускается сразу — после создания она " +
        "проходит оценку (status: new → estimating → ready_for_approval), затем её нужно подтвердить " +
        "инструментом express_accept_claim; либо передайте auto_accept=true. Возвращает id (claim_id), " +
        "status, version, route_points, pricing, created_ts. Идемпотентность обеспечивает request_id: " +
        "повторный вызов с тем же request_id вернёт ту же заявку, а не создаст дубликат.",
      inputSchema: {
        request_id: z
          .string()
          .min(1)
          .max(128)
          .optional()
          .describe(
            "Токен идемпотентности (1–128 символов, query-параметр). Если не задан — UUID сгенерируется автоматически.",
          ),
        items: z
          .array(
            z
              .object({
                title: z.string().describe("Название товара."),
                quantity: z.number().int().min(1).describe("Количество единиц."),
                cost_value: z.string().describe('Цена за единицу, строка-decimal, например "350.00".'),
                cost_currency: z.string().describe('Валюта ISO 4217, например "RUB".'),
                pickup_point: z.number().int().optional().describe("point_id точки забора из route_points."),
                dropoff_point: z.number().int().optional().describe("point_id точки вручения из route_points."),
                weight: z.number().optional().describe("Вес единицы, кг."),
                size: z
                  .object({
                    length: z.number().describe("Длина, метры."),
                    width: z.number().describe("Ширина, метры."),
                    height: z.number().describe("Высота, метры."),
                  })
                  .optional()
                  .describe("Габариты единицы, метры."),
                extra_id: z.string().optional().describe("Внешний артикул/id товара в системе магазина."),
              })
              .passthrough(),
          )
          .min(1)
          .describe("Товары к доставке. Ставка НДС передаётся кодами vat_none | vat0 | vat10 | vat20."),
        route_points: z
          .array(
            z
              .object({
                point_id: z.number().int().describe("Уникальный id точки в рамках заявки."),
                type: z
                  .enum(["source", "destination", "return"])
                  .describe("Тип точки: source — забор, destination — вручение, return — возврат."),
                visit_order: z.number().int().min(1).describe("Порядок посещения, начиная с 1."),
                contact: z
                  .object({
                    name: z.string().describe("Имя контактного лица."),
                    phone: z.string().describe("Телефон в международном формате, например +79991234567."),
                    email: z.string().optional().describe("Email контактного лица."),
                  })
                  .passthrough()
                  .describe("Контакт на точке."),
                address: z
                  .object({
                    fullname: z.string().describe("Полный адрес строкой."),
                    coordinates: z
                      .array(z.number())
                      .length(2)
                      .optional()
                      .describe("Координаты [долгота, широта] — повышают точность геокодинга."),
                  })
                  .passthrough()
                  .describe("Адрес точки."),
              })
              .passthrough(),
          )
          .min(2)
          .max(300)
          .describe("Точки маршрута (2–300): как минимум source и destination."),
        client_requirements: z
          .object({
            taxi_class: taxiClassEnum().describe("Класс доставки: courier, express, cargo или sdd_multislot."),
            cargo_type: cargoTypeEnum().optional().describe("Тип кузова (для cargo): van, lcv_m, lcv_l."),
            cargo_loaders: z.number().int().min(0).optional().describe("Число грузчиков (для cargo)."),
            pro_courier: z.boolean().optional().describe("true — опытный курьер («Профи»)."),
          })
          .passthrough()
          .describe("Требования к доставке; taxi_class обязателен."),
        emergency_contact: z
          .object({
            name: z.string().describe("Имя контакта."),
            phone: z.string().describe("Телефон контакта."),
          })
          .passthrough()
          .optional()
          .describe("Контакт на случай проблем с доставкой."),
        callback_properties: z
          .object({
            callback_url: z.string().describe("URL, на который придут уведомления о смене статуса."),
          })
          .passthrough()
          .optional()
          .describe("Webhook о смене статусов заявки."),
        due: rfc3339Date()
          .optional()
          .describe("Желаемое время подачи курьера (ISO-8601), например 2026-08-10T12:00:00+03:00."),
        comment: z.string().max(7000).optional().describe("Комментарий курьеру (до 7000 символов)."),
        skip_door_to_door: z.boolean().optional().describe("true — не подниматься до двери (вручение у подъезда)."),
        skip_client_notify: z.boolean().optional().describe("true — не отправлять SMS/пуши получателю."),
        skip_act: z.boolean().optional().describe("true — не формировать акт приёма-передачи."),
        optional_return: z
          .boolean()
          .optional()
          .describe("true — при неудачном вручении курьер не возвращает товары отправителю."),
        same_day_data: z
          .record(z.any())
          .optional()
          .describe("Параметры доставки «в течение дня» (для taxi_class=sdd_multislot): {delivery_interval: {from, to}}."),
        auto_accept: z
          .boolean()
          .optional()
          .describe("true — подтвердить заявку автоматически после успешной оценки (без express_accept_claim)."),
      },
    },
    async ({ request_id, ...body }) => {
      try {
        return ok(await client.createClaim({ request_id, body }));
      } catch (e) {
        return fail(e);
      }
    },
  );

  server.registerTool(
    "express_get_claim",
    {
      title: "Экспресс: информация о заявке",
      annotations: READ_ONLY,
      description:
        "Полная информация по заявке: status, version (нужен для accept/cancel), items, route_points, " +
        "pricing {offer, final_price, currency}, performer_info (имя курьера, транспорт), eta, " +
        `created_ts/updated_ts. Статусы: ${CLAIM_STATUSES}. ` +
        "ВНИМАНИЕ: ошибки оценки могут прийти массивом error_messages [{code, message}] внутри " +
        "успешного 200-ответа — проверяйте и HTTP-ошибку, и это поле.",
      inputSchema: {
        claim_id: claimId(),
      },
    },
    async ({ claim_id }) => {
      try {
        return ok(await client.getClaim(claim_id));
      } catch (e) {
        return fail(e);
      }
    },
  );

  server.registerTool(
    "express_accept_claim",
    {
      title: "Экспресс: подтвердить заявку",
      annotations: WRITE,
      description:
        "Подтверждает заявку после успешной оценки (status ready_for_approval) и запускает поиск курьера — " +
        "с этого момента доставка реально заказана. version берётся из express_get_claim. " +
        "Ошибки 409: inappropriate_status (заявка не в подходящем статусе), old_version (устаревшая версия — " +
        "перечитайте заявку), offer_expired / offer_already_used (оффер истёк — пересоздайте заявку).",
      inputSchema: {
        claim_id: claimId(),
        version: z.number().int().describe("Версия заявки из последнего ответа express_get_claim."),
      },
    },
    async ({ claim_id, version }) => {
      try {
        return ok(await client.acceptClaim({ claim_id, version }));
      } catch (e) {
        return fail(e);
      }
    },
  );

  server.registerTool(
    "express_cancel_info",
    {
      title: "Экспресс: условия отмены",
      annotations: READ_ONLY,
      description:
        "Условия отмены заявки — вызывайте ПЕРЕД express_cancel_claim. Возвращает cancel_state: " +
        "free (бесплатная), paid (платная — вернётся price/price_with_vat и currency) или " +
        "unavailable (отменить уже нельзя).",
      inputSchema: {
        claim_id: claimId(),
      },
    },
    async ({ claim_id }) => {
      try {
        return ok(await client.cancelInfo(claim_id));
      } catch (e) {
        return fail(e);
      }
    },
  );

  server.registerTool(
    "express_cancel_claim",
    {
      title: "Экспресс: отменить заявку",
      annotations: DESTRUCTIVE,
      description:
        "Отменяет заявку (в том числе уже подтверждённую). Перед вызовом получите условия отмены через " +
        "express_cancel_info и передайте её cancel_state: при paid спишется стоимость отмены. " +
        "version берётся из express_get_claim. Ошибки 409: устаревшая версия, недопустимый статус " +
        "или бесплатная отмена уже недоступна.",
      inputSchema: {
        claim_id: claimId(),
        version: z.number().int().describe("Версия заявки из последнего ответа express_get_claim."),
        cancel_state: z
          .enum(["free", "paid"])
          .describe("Режим отмены из express_cancel_info: free — бесплатно, paid — платно."),
      },
    },
    async ({ claim_id, version, cancel_state }) => {
      try {
        return ok(await client.cancelClaim({ claim_id, version, cancel_state }));
      } catch (e) {
        return fail(e);
      }
    },
  );

  server.registerTool(
    "express_search_claims",
    {
      title: "Экспресс: поиск заявок",
      annotations: READ_ONLY,
      description:
        "Поиск заявок по фильтрам с пагинацией (сортировка — по дате создания). Возвращает claims " +
        "(каждая — как в express_get_claim) и cursor для следующей страницы. Пагинация: либо " +
        "offset/limit, либо курсорная — передайте cursor из предыдущего ответа (тогда остальные " +
        "фильтры не нужны).",
      inputSchema: {
        offset: z.number().int().min(0).optional().describe("Смещение offset-пагинации (по умолчанию 0)."),
        limit: z.number().int().min(1).max(1000).optional().describe("Сколько заявок вернуть (1–1000)."),
        claim_id: z.string().optional().describe("Фильтр по id заявки."),
        phone: z.string().optional().describe("Фильтр по телефону из контактов заявки."),
        status: z
          .string()
          .optional()
          .describe(`Фильтр по статусу. Известные статусы: ${CLAIM_STATUSES}.`),
        state: z
          .enum(["active", "finished", "delayed"])
          .optional()
          .describe("Группа статусов: active — активные, finished — завершённые, delayed — отложенные."),
        created_from: rfc3339Date().optional().describe("Создана не ранее (ISO-8601)."),
        created_to: rfc3339Date().optional().describe("Создана не позднее (ISO-8601)."),
        due_from: rfc3339Date().optional().describe("Подача не ранее (ISO-8601)."),
        due_to: rfc3339Date().optional().describe("Подача не позднее (ISO-8601)."),
        external_order_id: z.string().optional().describe("Фильтр по внешнему id заказа."),
        cursor: z
          .string()
          .optional()
          .describe("Курсор из предыдущего ответа — альтернатива offset/limit."),
      },
    },
    async (filters) => {
      try {
        return ok(await client.searchClaims(filters));
      } catch (e) {
        return fail(e);
      }
    },
  );

  server.registerTool(
    "express_performer_position",
    {
      title: "Экспресс: позиция курьера",
      annotations: READ_ONLY,
      description:
        "Текущая геопозиция курьера по активной заявке: position {lat, lon, timestamp (unix), accuracy, " +
        "speed (м/с), direction (0–360°)} и route_points с sharing_link. Ошибки: 404 — курьер/позиция " +
        "не найдены, 409 — заявка не в активном статусе.",
      inputSchema: {
        claim_id: claimId(),
      },
    },
    async ({ claim_id }) => {
      try {
        return ok(await client.performerPosition(claim_id));
      } catch (e) {
        return fail(e);
      }
    },
  );

  server.registerTool(
    "express_tracking_links",
    {
      title: "Экспресс: ссылки для отслеживания",
      annotations: READ_ONLY,
      description:
        "Публичные ссылки для отслеживания курьера — их можно отдавать получателю. Возвращает " +
        "route_points [{id, type, visit_order, sharing_link}]; sharing_link доступен только для точек " +
        "type=destination. Ошибки 409: inappropriate_status, unknown_tracking_links.",
      inputSchema: {
        claim_id: claimId(),
      },
    },
    async ({ claim_id }) => {
      try {
        return ok(await client.trackingLinks(claim_id));
      } catch (e) {
        return fail(e);
      }
    },
  );
}
