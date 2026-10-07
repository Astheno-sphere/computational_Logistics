import { format } from "sql-formatter";

export function formatSqlWithLibrary(sql: string): string {
  if (!sql.trim()) {
    return sql;
  }

  return format(sql, {
    keywordCase: "upper",
    language: "sql",
    linesBetweenQueries: 1,
  }).trimEnd();
}
