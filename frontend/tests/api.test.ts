import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, getCategories, saveAlwaysRule, toApiError } from "../lib/api";

afterEach(() => vi.unstubAllGlobals());

describe("toApiError", () => {
  it("reads the backend error envelope", async () => {
    const res = new Response(
      JSON.stringify({ error: { code: "unrecognized_layout", message: "Unrecognized statement layout", details: { supported: ["first_federal_checking"] } } }),
      { status: 422 },
    );
    const err = await toApiError(res);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("unrecognized_layout");
    expect(err.message).toBe("Unrecognized statement layout");
    expect(err.status).toBe(422);
  });

  it("falls back to a generic error for non-JSON bodies", async () => {
    const err = await toApiError(new Response("boom", { status: 500 }));
    expect(err.code).toBe("http_error");
    expect(err.status).toBe(500);
  });
});

describe("API calls", () => {
  it("turns a network failure into a readable error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));
    await expect(getCategories()).rejects.toMatchObject({ code: "network_error" });
  });

  it("sends the rule body the backend expects", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ rule: { id: "user.1", merchant_key: "JOES CAFE", category: "Personal" }, updated_count: 2 })),
    );
    vi.stubGlobal("fetch", fetchMock);
    const res = await saveAlwaysRule("abc", "JOES CAFE", "Personal");
    expect(res.updated_count).toBe(2);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/sessions\/abc\/rules$/);
    expect(JSON.parse(init.body)).toEqual({ merchant_key: "JOES CAFE", category: "Personal", apply_to_existing: true });
  });
});
