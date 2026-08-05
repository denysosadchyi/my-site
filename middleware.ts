// Basic Auth for the Scalr case (password only, any username).
// Runs before redirects/filesystem; the -ua paths are covered anyway since
// their redirect lands on /case-scalr.html which is matched here too.
export const config = {
  matcher: [
    "/case-scalr",
    "/case-scalr.html",
    "/case-scalr-en",
    "/case-scalr-en.html",
    "/case-scalr-ua",
    "/case-scalr-ua.html",
  ],
};

export default function middleware(req: Request): Response | undefined {
  const auth = req.headers.get("authorization") || "";
  if (auth.startsWith("Basic ")) {
    try {
      // ponytail: any username accepted, only the password is checked
      if (atob(auth.slice(6)).split(":").slice(1).join(":") === "admin99") {
        return; // no response -> request continues to the static file
      }
    } catch {}
  }
  return new Response("Authentication required", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="Scalr case"' },
  });
}
