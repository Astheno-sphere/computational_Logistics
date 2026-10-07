import type { DatabaseTable } from "@unfour/command-client";

export function databaseTableTreeId(connectionId: string, table: DatabaseTable) {
  return `${connectionId}:table:${table.catalog ?? "default"}:${table.schema ?? "default"}:${table.name}`;
}

// Normalized object tree shared across drivers. The internal shape is always
// DataSource -> Catalog -> Schema -> DbObject; individual drivers simply leave
// levels empty (SQLite has neither catalog nor schema, MySQL has a catalog but
// no schema). The UI maps these to driver-familiar labels.
export type DatabaseTreeSchemaNode = {
  /** Schema name, or "" when the driver has no schema level. */
  key: string;
  tables: DatabaseTable[];
};

export type DatabaseTreeCatalogNode = {
  /** Catalog (database) name, or "" when the driver has no catalog level. */
  key: string;
  /** True when at least one object carries a schema (PostgreSQL). */
  hasSchemaLevel: boolean;
  schemas: DatabaseTreeSchemaNode[];
};

export type DatabaseTreeModel = {
  catalogs: DatabaseTreeCatalogNode[];
};

/**
 * Group a flat object list into catalogs and (optionally) schemas, preserving
 * first-seen order. Works for every driver: SQLite collapses to a single
 * empty-key catalog/schema, MySQL produces one catalog per database with no
 * schema level, and PostgreSQL produces a catalog with nested schemas.
 */
export function buildDatabaseTree(tables: DatabaseTable[]): DatabaseTreeModel {
  const catalogOrder: string[] = [];
  const catalogMap = new Map<string, { order: string[]; schemas: Map<string, DatabaseTable[]> }>();

  for (const table of tables) {
    const catalogKey = (table.catalog ?? "").trim();
    const schemaKey = (table.schema ?? "").trim();

    let catalog = catalogMap.get(catalogKey);
    if (!catalog) {
      catalog = { order: [], schemas: new Map() };
      catalogMap.set(catalogKey, catalog);
      catalogOrder.push(catalogKey);
    }

    if (!catalog.schemas.has(schemaKey)) {
      catalog.schemas.set(schemaKey, []);
      catalog.order.push(schemaKey);
    }
    catalog.schemas.get(schemaKey)!.push(table);
  }

  const catalogs = catalogOrder.map((catalogKey) => {
    const catalog = catalogMap.get(catalogKey)!;
    const hasSchemaLevel = catalog.order.some((key) => key !== "");
    const schemas = catalog.order.map((schemaKey) => ({
      key: schemaKey,
      tables: catalog.schemas.get(schemaKey)!,
    }));
    return { key: catalogKey, hasSchemaLevel, schemas };
  });

  return { catalogs };
}
