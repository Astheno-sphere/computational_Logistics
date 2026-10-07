import type { DatabaseTable } from "@unfour/command-client";
import { describe, expect, it } from "vitest";
import { buildDatabaseTree, databaseTableTreeId } from "./database-tree";

function table(overrides: Partial<DatabaseTable>): DatabaseTable {
  return { columns: [], kind: "table", name: "users", ...overrides };
}

describe("databaseTableTreeId", () => {
  it("includes connection, catalog, schema, and table name", () => {
    expect(
      databaseTableTreeId("conn-1", table({ name: "orders", catalog: "appdb", schema: "public" })),
    ).toBe("conn-1:table:appdb:public:orders");
  });

  it("falls back to the default segments when catalog and schema are absent", () => {
    expect(databaseTableTreeId("conn-1", table({ schema: null }))).toBe(
      "conn-1:table:default:default:users",
    );
  });

  it("distinguishes same-named tables in different catalogs", () => {
    const appUsers = databaseTableTreeId("conn-1", table({ catalog: "app" }));
    const analyticsUsers = databaseTableTreeId("conn-1", table({ catalog: "analytics" }));
    expect(appUsers).not.toBe(analyticsUsers);
  });
});

describe("buildDatabaseTree", () => {
  it("collapses SQLite into a single empty catalog with no schema level", () => {
    const model = buildDatabaseTree([table({ name: "a" }), table({ name: "b" })]);
    expect(model.catalogs).toHaveLength(1);
    expect(model.catalogs[0].key).toBe("");
    expect(model.catalogs[0].hasSchemaLevel).toBe(false);
    expect(model.catalogs[0].schemas[0].tables).toHaveLength(2);
  });

  it("groups MySQL databases as separate catalogs without a schema level", () => {
    const model = buildDatabaseTree([
      table({ name: "users", catalog: "app" }),
      table({ name: "events", catalog: "analytics" }),
    ]);
    expect(model.catalogs.map((catalog) => catalog.key)).toEqual(["app", "analytics"]);
    expect(model.catalogs.every((catalog) => !catalog.hasSchemaLevel)).toBe(true);
  });

  it("nests PostgreSQL schemas under their catalog", () => {
    const model = buildDatabaseTree([
      table({ name: "users", catalog: "appdb", schema: "public" }),
      table({ name: "logs", catalog: "appdb", schema: "audit" }),
    ]);
    expect(model.catalogs).toHaveLength(1);
    expect(model.catalogs[0].hasSchemaLevel).toBe(true);
    expect(model.catalogs[0].schemas.map((schema) => schema.key)).toEqual(["public", "audit"]);
  });
});
