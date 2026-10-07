#!/usr/bin/env node
import { run, keepsProcessAlive } from "./cli.js";

const argv = process.argv.slice(2);

run(argv)
  .then((code) => {
    // 서버 기동은 프로세스를 유지, 그 외 명령은 종료 코드로 종료
    if (!keepsProcessAlive(argv)) process.exit(code);
  })
  .catch((err) => {
    console.error("[geowire:fatal]", err);
    process.exit(1);
  });
