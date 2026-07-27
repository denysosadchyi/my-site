// Agentation dev toolbar — visual annotations -> context for coding agents.
// ponytail: localhost-only gate so it never ships to visitors; no build step,
// React comes from esm.sh. If the site ever gets a bundler, npm i -D agentation.
// ponytail: gate = localhost + RFC1918 LAN, so it loads over the local network
// but never on the public deploy.
if (/^(localhost$|127\.|10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/.test(location.hostname)) {
  const R = 'react@18.3.1', D = 'react-dom@18.3.1';
  const [react, client, { Agentation }] = await Promise.all([
    import(`https://esm.sh/${R}`),
    import(`https://esm.sh/${D}/client`),
    import(`https://esm.sh/agentation@3?deps=${R},${D}`),
  ]);
  // Over LAN http:// this is not a secure context, so navigator.clipboard is
  // undefined and Agentation's own copy silently no-ops (it swallows the throw
  // and still flashes "copied"). execCommand still works there.
  const copy = (text) => {
    const ta = document.body.appendChild(document.createElement('textarea'));
    ta.value = text;
    ta.style.cssText = 'position:fixed;top:-9999px';
    ta.select();
    const ok = document.execCommand('copy');
    ta.remove();
    return ok;
  };

  const mount = document.body.appendChild(document.createElement('div'));
  client.createRoot(mount).render(react.createElement(Agentation, {
    // "Send to Agent" -> serve.py -> annotations.md, which Claude reads.
    webhookUrl: location.origin + '/agentation',
    copyToClipboard: false,
    onCopy: (md) => copy(md) || console.warn('[agentation] copy failed:\n' + md),
  }));
}
