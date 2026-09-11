// api/visitors.js — Vercel Serverless Function
// Proxies countapi.xyz to avoid CORS issues
// Deployed automatically by Vercel as /api/visitors

export default async function handler(req, res) {
  // Allow CORS from your own domain
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET');
  res.setHeader('Cache-Control', 'no-store');

  try {
    const response = await fetch(
      'https://countapi.xyz/hit/runmyllm.app/visitors',
      { headers: { 'User-Agent': 'runmyllm.app/1.0' } }
    );

    if (!response.ok) throw new Error(`countapi returned ${response.status}`);

    const data = await response.json();
    return res.status(200).json({ count: data.value });

  } catch (err) {
    console.error('Counter error:', err.message);
    // Return a fallback so the widget never breaks
    return res.status(200).json({ count: null, error: err.message });
  }
}
