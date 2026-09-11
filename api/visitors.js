// api/visitors.js — Vercel Serverless Function
// Uses GoatCounter public stats API — reliable, no CORS issues server-side

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET');
  res.setHeader('Cache-Control', 'no-store, max-age=0');

  // Try multiple counter backends in sequence
  const backends = [
    // Backend 1: countapi.xyz
    async () => {
      const r = await fetch('https://countapi.xyz/hit/runmyllm-app/page-views', {
        headers: { 'User-Agent': 'runmyllm.app server/1.0' }
      });
      const d = await r.json();
      return typeof d.value === 'number' ? d.value : null;
    },
    // Backend 2: api.counterapi.dev
    async () => {
      const r = await fetch('https://api.counterapi.dev/v1/runmyllm-app/pageviews/up', {
        headers: { 'User-Agent': 'runmyllm.app server/1.0' }
      });
      const d = await r.json();
      return typeof d.count === 'number' ? d.count : null;
    },
  ];

  for (const backend of backends) {
    try {
      const count = await backend();
      if (count !== null && count > 0) {
        return res.status(200).json({ count, ok: true });
      }
    } catch (e) {
      console.error('Backend failed:', e.message);
    }
  }

  return res.status(200).json({ count: null, ok: false });
}
