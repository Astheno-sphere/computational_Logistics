// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { DataTable } from "./data-table";

afterEach(cleanup);

describe("DataTable", () => {
  it("keeps explicit column widths shared by header and body cells", () => {
    render(
      <DataTable
        columns={[
          { cell: (row) => row.name, header: "Name", id: "name", width: 120 },
          { align: "right", cell: (row) => row.count, header: "Count", id: "count", width: 80 },
        ]}
        rows={[{ count: 42, name: "Users" }]}
      />,
    );

    const table = screen.getByRole("table");
    const countHeader = screen.getByText("Count").closest("div");
    const countCell = screen.getByText("42").closest("td");
    const columns = table.querySelectorAll("col");

    expect(table).toHaveStyle({ width: "200px" });
    expect(columns[0]).toHaveStyle({ width: "120px" });
    expect(columns[1]).toHaveStyle({ width: "80px" });
    expect(countHeader).toHaveClass("justify-end");
    expect(countCell).toHaveClass("text-right");
    expect(countCell).toHaveClass("border-r");
  });

  it("renders a resize handle on each column header when onColumnResize is provided", () => {
    render(
      <DataTable
        columns={[
          { cell: (row) => row.name, header: "Name", id: "name", width: 120 },
          { cell: (row) => row.count, header: "Count", id: "count", width: 80 },
        ]}
        onColumnResize={() => {}}
        rows={[{ count: 42, name: "Users" }]}
      />,
    );

    // Each column header (<th>) holds a resize handle div with cursor-col-resize.
    const handles = document.querySelectorAll<HTMLElement>('.cursor-col-resize');
    expect(handles.length).toBe(2);
    expect(handles[0]).toHaveAttribute("role", "separator");
    expect(handles[0]).toHaveAttribute("tabindex", "0");
    expect(handles[0].firstElementChild).toHaveClass("opacity-0", "-right-px");
  });

  it("does not render resize handles when onColumnResize is absent", () => {
    render(
      <DataTable
        columns={[
          { cell: (row) => row.name, header: "Name", id: "name", width: 120 },
          { cell: (row) => row.count, header: "Count", id: "count", width: 80 },
        ]}
        rows={[{ count: 42, name: "Users" }]}
      />,
    );

    const handles = document.querySelectorAll('.cursor-col-resize');
    expect(handles.length).toBe(0);
  });

  it("reports the final width to onColumnResize after a drag", () => {
    const handleResize = vi.fn();
    render(
      <DataTable
        columns={[
          { cell: (row) => row.name, header: "Name", id: "name", width: 120 },
          { cell: (row) => row.count, header: "Count", id: "count", width: 80 },
        ]}
        onColumnResize={handleResize}
        rows={[{ count: 42, name: "Users" }]}
      />,
    );

    const handle = document.querySelector<HTMLElement>('.cursor-col-resize')!;
    fireEvent.pointerDown(handle, { clientX: 100 });

    // Simulate dragging 50px to the right.
    fireEvent.pointerMove(window, { clientX: 150 });
    fireEvent.pointerUp(window, { clientX: 150 });

    expect(handleResize).toHaveBeenCalledWith("name", 170);
  });

  it("fits a column to its configured content width on resize-handle double-click", () => {
    const handleResize = vi.fn();
    render(
      <DataTable
        columns={[
          { autoFitWidth: 236, cell: (row) => row.name, header: "Name", id: "name", width: 120 },
        ]}
        getColumnResizeLabel={(column) => `Resize ${column.id}`}
        onColumnResize={handleResize}
        rows={[{ name: "A longer user name" }]}
      />,
    );

    fireEvent.doubleClick(screen.getByRole("separator", { name: "Resize name" }));

    expect(handleResize).toHaveBeenLastCalledWith("name", 236);
    expect(screen.getByRole("table").querySelector("col")).toHaveStyle({ width: "236px" });
  });

  it("supports keyboard column resizing from the handle", () => {
    const handleResize = vi.fn();
    render(
      <DataTable
        columns={[{ cell: (row) => row.name, header: "Name", id: "name", width: 120 }]}
        onColumnResize={handleResize}
        rows={[{ name: "Users" }]}
      />,
    );

    fireEvent.keyDown(screen.getByRole("separator", { name: "name" }), { key: "ArrowRight" });

    expect(handleResize).toHaveBeenCalledWith("name", 128);
  });
});
