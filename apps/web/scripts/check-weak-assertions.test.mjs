import { test } from "node:test";
import assert from "node:assert/strict";

import { scanSource } from "./check-weak-assertions.mjs";

const wrap = (body) => `it("a test", () => {\n${body}\n});\n`;
const verdictOf = (body) => scanSource(wrap(body))[0]?.verdict ?? null;

test("a weak matcher on a plain value is an offender", () => {
  assert.equal(verdictOf(`expect(parse("x")).toBeTruthy();`), "only_weak_assertions");
});

test("a test with no expect at all is an offender", () => {
  assert.equal(verdictOf(`render(<Thing />);`), "no_assertions");
});

test("a strong matcher passes", () => {
  assert.equal(verdictOf(`expect(sum(1, 2)).toBe(3);`), null);
});

test("toBeEmptyDOMElement is a strong matcher", () => {
  assert.equal(verdictOf(`expect(container).toBeEmptyDOMElement();`), null);
});

test("a getBy query on a string literal is itself the assertion", () => {
  assert.equal(verdictOf(`expect(screen.getByText("3.48")).toBeTruthy();`), null);
});

test("a getBy query on a regex literal is itself the assertion", () => {
  assert.equal(verdictOf(`expect(screen.getByText(/3\\.48/)).toBeTruthy();`), null);
});

test("the query's later arguments do not have to be literals", () => {
  assert.equal(
    verdictOf(`expect(getByRole("button", { name: label })).toBeInTheDocument();`),
    null,
  );
});

test("getAllBy counts too, and so does a scoped query", () => {
  assert.equal(verdictOf(`expect(screen.getAllByRole("row")).toBeDefined();`), null);
  assert.equal(verdictOf(`expect(within(row).getByText("42")).toBeTruthy();`), null);
});

test("a query on a variable pins nothing the file states", () => {
  assert.equal(
    verdictOf(`expect(screen.getByText(expected)).toBeTruthy();`),
    "only_weak_assertions",
  );
});

test("queryBy returns null instead of throwing, so it stays weak", () => {
  assert.equal(
    verdictOf(`expect(screen.queryByText("3.48")).toBeTruthy();`),
    "only_weak_assertions",
  );
});

test("findBy returns a promise, so it stays weak", () => {
  assert.equal(
    verdictOf(`expect(await screen.findByText("3.48")).toBeTruthy();`),
    "only_weak_assertions",
  );
});

test("reading a property off a query is not the query", () => {
  assert.equal(
    verdictOf(`expect(screen.getByTestId("row").textContent).toBeTruthy();`),
    "only_weak_assertions",
  );
});
