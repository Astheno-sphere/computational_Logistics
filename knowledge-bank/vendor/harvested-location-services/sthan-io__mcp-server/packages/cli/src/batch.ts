import { mapWithConcurrency, SthanClient } from "@sthan/core";
import { readInput, writeOutput } from "./fileio.js";

export interface BatchOptions {
  input?: string;
  output?: string;
  column?: string;
  concurrency?: string;
}

export interface BatchOp {
  /** Progress verb, e.g. "Verifying". */
  verb: string;
  /** Fetch the Result object for one address. */
  call: (client: SthanClient, address: string) => Promise<Record<string, unknown>>;
  /** Appended output columns, in order (the trailing "error" column is added automatically). */
  resultColumns: string[];
  /** Map a successful Result into its appended column values. */
  mapResult: (r: Record<string, unknown>) => Record<string, string>;
}

/**
 * Read addresses from a file, run `op` over them with bounded concurrency,
 * and write the original columns plus `op`'s result columns to the output file.
 * Sets exit code 6 if any row failed.
 */
export async function runBatch(
  client: SthanClient,
  op: BatchOp,
  opts: BatchOptions
): Promise<void> {
  if (!opts.input || !opts.output) {
    console.error("Batch mode requires --input <file> and --output <file>.");
    process.exit(4);
  }

  let parsed;
  try {
    parsed = await readInput(opts.input, opts.column);
  } catch (e) {
    console.error(`Cannot read input file: ${e instanceof Error ? e.message : e}`);
    process.exit(4);
  }
  if (!parsed.rows.length) {
    console.error("No rows found in input file.");
    process.exit(4);
  }

  const concurrency = Number(opts.concurrency) > 0 ? Number(opts.concurrency) : 10;
  const total = parsed.rows.length;
  process.stderr.write(`${op.verb} ${total} addresses (concurrency ${concurrency})...\n`);

  const results = await mapWithConcurrency(
    parsed.rows,
    (row) => op.call(client, row.address),
    {
      concurrency,
      onProgress: (done) => {
        if (done % 25 === 0 || done === total) {
          process.stderr.write(`  ${done}/${total}\r`);
        }
      },
    }
  );

  const appended = [...op.resultColumns, "error"];
  const outHeaders = [
    ...parsed.headers,
    ...appended.filter((c) => !parsed.headers.includes(c)),
  ];
  const outRows = results.map((res, i) => {
    const out: Record<string, string> = { ...parsed.rows[i].original };
    if (res.error || !res.value) {
      for (const c of op.resultColumns) out[c] = "";
      out.error = res.error?.message ?? "no result";
    } else {
      Object.assign(out, op.mapResult(res.value));
      out.error = "";
    }
    return out;
  });

  try {
    await writeOutput(opts.output, outRows, outHeaders);
  } catch (e) {
    console.error(`Cannot write output file: ${e instanceof Error ? e.message : e}`);
    process.exit(1);
  }

  const failed = results.filter((r) => r.error || !r.value).length;
  process.stderr.write(
    `\nDone. ${total - failed} succeeded, ${failed} failed → ${opts.output}\n`
  );
  if (failed > 0) process.exitCode = 6; // partial success
}
