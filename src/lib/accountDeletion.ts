type Request = (path: string, options: RequestInit, expectedUserId: string) => Promise<unknown>;

export async function submitAccountDeletion(confirmation: string, userId: string, request: Request) {
  if (confirmation !== "DELETE") throw new Error("Type DELETE to confirm.");
  if (!userId) throw new Error("Please sign in to continue.");
  const result = await request("/api/v1/users/me", {
    method: "DELETE", body: JSON.stringify({ confirmation }),
  }, userId);
  if (!result || typeof result !== "object" || !("status" in result) || result.status !== "requested") {
    throw new Error("Unable to confirm the request. Check its status before trying again.");
  }
  return "requested" as const;
}
