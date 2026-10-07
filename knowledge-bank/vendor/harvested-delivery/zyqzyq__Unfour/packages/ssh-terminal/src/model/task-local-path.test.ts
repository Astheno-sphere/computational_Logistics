import { describe, expect, it } from "vitest";
import {
  downloadPathFromDirectory,
  fileNameFromPath,
  joinLocalPath,
} from "./task-local-path";

describe("task local path helpers", () => {
  it("detects file-like trailing segments", () => {
    expect(fileNameFromPath("C:\\out\\archive.tar")).toBe("archive.tar");
    expect(fileNameFromPath("{{local_output_dir}}/{{archive_name}}.tar")).toBe(
      "{{archive_name}}.tar",
    );
    expect(fileNameFromPath("C:\\Users\\me\\Downloads")).toBeNull();
    expect(fileNameFromPath("C:\\Users\\me\\Downloads\\")).toBeNull();
    expect(fileNameFromPath("")).toBeNull();
  });

  it("joins directories with the matching separator style", () => {
    expect(joinLocalPath("C:\\out", "a.tar")).toBe("C:\\out\\a.tar");
    expect(joinLocalPath("/tmp/out/", "a.tar")).toBe("/tmp/out/a.tar");
  });

  it("keeps a file name when browsing a download folder", () => {
    expect(
      downloadPathFromDirectory(
        "D:\\exports",
        "C:\\old\\image.tar",
        "/tmp/remote.bin",
      ),
    ).toBe("D:\\exports\\image.tar");
    expect(
      downloadPathFromDirectory(
        "D:\\exports",
        "{{local_output_dir}}/{{archive_name}}.tar",
        "/tmp/{{archive_name}}.tar",
      ),
    ).toBe("D:\\exports\\{{archive_name}}.tar");
    expect(downloadPathFromDirectory("D:\\exports", "", "/tmp/app.bin")).toBe(
      "D:\\exports\\app.bin",
    );
    expect(downloadPathFromDirectory("D:\\exports", "", "")).toBe(
      "D:\\exports\\{{filename}}",
    );
  });
});
