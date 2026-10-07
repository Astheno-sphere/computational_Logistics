/** 출력 스트림 추상화 (테스트에서 캡처 가능하게) */
export interface IO {
  out: (line: string) => void;
  err: (line: string) => void;
}

/** 표준 출력/에러에 쓰는 기본 IO */
export const consoleIO: IO = {
  out: (line) => process.stdout.write(`${line}\n`),
  err: (line) => process.stderr.write(`${line}\n`),
};
