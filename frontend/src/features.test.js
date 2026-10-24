import { describe, expect, it } from "vitest";
import { FIELDS, exampleValues, toPayload } from "./features.js";

describe("features helpers", () => {
  it("has the 11 wine features", () => expect(FIELDS).toHaveLength(11));
  it("converts numeric strings to numbers", () => {
    expect(toPayload(exampleValues()).alcohol).toBe(9.4);
  });
  it("keeps invalid text as text so the API can reject it", () => {
    expect(toPayload({ ph: "abc" }).ph).toBe("abc");
    expect(toPayload({ ph: "" }).ph).toBe("");
  });
});
