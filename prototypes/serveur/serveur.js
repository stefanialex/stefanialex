#!/usr/bin/env node
/**
 * Banc d'essai — serveur d'auto-hébergement.
 *
 * Sert le prototype et collecte les rapports d'incident. Aucune dépendance :
 * uniquement les modules fournis avec Node (>= 18).
 *
 *   PORT=8787 CLE=motdepasse node serveur.js
 *
 * Variables d'environnement :
 *   PORT              port d'écoute (défaut 8787)
 *   CLE               clé exigée pour consulter /rapports (défaut : aucune, page fermée)
 *   DISCORD_WEBHOOK   URL de webhook Discord ; chaque rapport y est reposté
 *   JEU               chemin du fichier HTML (défaut ../p01-banc-essai.html)
 */
'use strict';
const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');

const PORT = Number(process.env.PORT || 8787);
const CLE = process.env.CLE || '';
const WEBHOOK = process.env.DISCORD_WEBHOOK || '';
const JEU = path.resolve(process.env.JEU || path.join(__dirname, '..', 'p01-banc-essai.html'));
const JOURNAL = path.join(__dirname, 'rapports.jsonl');

const MAX_CORPS = 32 * 1024;      // un rapport pèse ~2 Ko ; au-delà c'est un abus
const FENETRE = 60 * 1000;
const MAX_PAR_IP = 20;
const compteur = new Map();

function limite(ip) {
  const t = Date.now();
  const e = compteur.get(ip);
  if (!e || t - e.debut > FENETRE) { compteur.set(ip, { debut: t, n: 1 }); return false; }
  e.n += 1;
  return e.n > MAX_PAR_IP;
}

function ech(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/* ---------- page HTML du jeu ---------- */
let pageJeu = null;
function chargerJeu() {
  try { pageJeu = fs.readFileSync(JEU); }
  catch (e) { console.error('Jeu introuvable :', JEU); pageJeu = Buffer.from('<h1>Jeu introuvable</h1>'); }
}
chargerJeu();
try { fs.watch(JEU, { persistent: false }, () => setTimeout(chargerJeu, 120)); } catch (e) {}

/* ---------- Discord ---------- */
function versDiscord(r) {
  if (!WEBHOOK) return;
  let u;
  try { u = new URL(WEBHOOK); } catch (e) { return console.error('DISCORD_WEBHOOK invalide'); }
  if (u.protocol !== 'https:') return console.error('DISCORD_WEBHOOK doit être en https');
  const corps = JSON.stringify({
    username: 'Service des Donjons',
    content: '```\n' + String(r.texte || '').slice(0, 1800) + '\n```',
  });
  const req = https.request({
    hostname: u.hostname, path: u.pathname + u.search, method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(corps) },
  }, res => res.resume());
  req.on('error', e => console.error('Discord :', e.message));
  req.end(corps);
}

/* ---------- lecture des rapports ---------- */
function lire() {
  if (!fs.existsSync(JOURNAL)) return [];
  return fs.readFileSync(JOURNAL, 'utf8').split('\n').filter(Boolean)
    .map(l => { try { return JSON.parse(l); } catch (e) { return null; } })
    .filter(Boolean);
}

function pageRapports() {
  const rs = lire().reverse();
  const n = rs.length;
  const moy = c => n ? Math.round(rs.reduce((s, r) => s + (Number(r[c]) || 0), 0) / n) : 0;
  const cite = rs.filter(r => (r.citation || '').trim().length > 2).length;
  const relance = rs.filter(r => r.relancerait === 'oui').length;
  const lignes = rs.map(r => `<tr>
      <td>${ech(r.agent || '—')}</td>
      <td>${ech(r.issue)}</td>
      <td class="n">${ech(r.tours)}</td>
      <td class="n">${ech(r.engueulades)} / ${ech(r.vosGueules)}</td>
      <td class="n">${ech(r.pourcentLues)} %</td>
      <td>${ech(r.journal ? 'oui' : 'non')}</td>
      <td class="cit">${ech(r.citation) || '<i>aucune</i>'}</td>
      <td>${ech(r.decrochage)}</td>
      <td>${ech(r.relancerait)}</td>
      <td class="cit">${ech(r.remarque)}</td>
    </tr>`).join('');
  return `<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Rapports — banc d'essai</title>
<style>
 body{font:14px/1.5 ui-monospace,Menlo,Consolas,monospace;background:#E7EAE0;color:#202318;margin:0;padding:20px}
 h1{font-size:16px;letter-spacing:.14em;text-transform:uppercase;margin:0 0 4px}
 .res{display:flex;flex-wrap:wrap;gap:18px;margin:14px 0 20px;padding:12px;background:#F4F5EF;border:1px solid #C4C9B8}
 .res div{min-width:120px}.res b{display:block;font-size:22px}
 .res span{font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#6E7464}
 table{border-collapse:collapse;width:100%;font-size:12.5px;background:#F4F5EF}
 th{text-align:left;background:#DDE1D4;padding:7px 9px;border-bottom:1px solid #A5AC95;
    font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:#6E7464}
 td{padding:7px 9px;border-top:1px solid #C4C9B8;vertical-align:top}
 td.n{text-align:right;font-variant-numeric:tabular-nums}
 td.cit{font-family:Georgia,serif;font-size:13.5px;max-width:280px}
 p.vide{padding:24px;text-align:center;color:#6E7464;background:#F4F5EF;border:1px dashed #A5AC95}
</style></head><body>
<h1>Rapports d'incident — banc d'essai 01</h1>
<div class="res">
  <div><b>${n}</b><span>rapports</span></div>
  <div><b>${n ? Math.round(cite / n * 100) : 0} %</b><span>citent une réplique</span></div>
  <div><b>${moy('pourcentLues')} %</b><span>répliques lues</span></div>
  <div><b>${n ? Math.round(relance / n * 100) : 0} %</b><span>relanceraient</span></div>
  <div><b>${moy('engueulades')}</b><span>engueulades / partie</span></div>
</div>
${n ? `<table><thead><tr><th>Agent</th><th>Issue</th><th>Tours</th><th>Eng. / VG</th>
  <th>Lues</th><th>Journal</th><th>Réplique citée</th><th>Décrochage</th><th>Relance</th><th>Remarque</th>
  </tr></thead><tbody>${lignes}</tbody></table>`
  : '<p class="vide">Aucun rapport reçu. Le service reste à votre disposition.</p>'}
</body></html>`;
}

/* ---------- serveur ---------- */
const serveur = http.createServer((req, res) => {
  const ip = req.socket.remoteAddress || '?';
  const u = new URL(req.url, 'http://x');

  if (req.method === 'POST' && u.pathname === '/rapport') {
    if (limite(ip)) { res.writeHead(429).end('trop de demandes'); return; }
    let n = 0; const morceaux = [];
    req.on('data', c => {
      n += c.length;
      if (n > MAX_CORPS) { res.writeHead(413).end('rapport trop volumineux'); req.destroy(); return; }
      morceaux.push(c);
    });
    req.on('end', () => {
      if (res.writableEnded) return;
      let r;
      try { r = JSON.parse(Buffer.concat(morceaux).toString('utf8')); }
      catch (e) { res.writeHead(400).end('json invalide'); return; }
      if (!r || typeof r !== 'object' || Array.isArray(r)) { res.writeHead(400).end('objet attendu'); return; }
      r.recuLe = new Date().toISOString();
      fs.appendFile(JOURNAL, JSON.stringify(r) + '\n', e => {
        if (e) console.error('écriture :', e.message);
      });
      versDiscord(r);
      console.log(`rapport de ${r.agent || 'anonyme'} — ${r.pourcentLues}% lues — « ${(r.citation || '').slice(0, 60)} »`);
      res.writeHead(200, { 'Content-Type': 'text/plain' }).end('enregistré');
    });
    return;
  }

  if (req.method === 'GET' && u.pathname === '/rapports') {
    if (!CLE) { res.writeHead(403).end('Définissez CLE pour ouvrir cette page.'); return; }
    if (u.searchParams.get('cle') !== CLE) { res.writeHead(401).end('clé invalide'); return; }
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' })
       .end(pageRapports());
    return;
  }

  if (req.method === 'GET' && u.pathname === '/rapports.jsonl') {
    if (!CLE || u.searchParams.get('cle') !== CLE) { res.writeHead(401).end('clé invalide'); return; }
    res.writeHead(200, { 'Content-Type': 'application/x-ndjson; charset=utf-8' })
       .end(fs.existsSync(JOURNAL) ? fs.readFileSync(JOURNAL) : '');
    return;
  }

  if (req.method === 'GET' && (u.pathname === '/' || u.pathname === '/index.html')) {
    res.writeHead(200, {
      'Content-Type': 'text/html; charset=utf-8',
      'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff',
      'Referrer-Policy': 'no-referrer',
    }).end(pageJeu);
    return;
  }

  res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' }).end('rien à cette adresse');
});

serveur.listen(PORT, () => {
  console.log(`Banc d'essai servi sur http://localhost:${PORT}`);
  console.log(`Rapports : ${CLE ? `http://localhost:${PORT}/rapports?cle=${CLE}` : '(définissez CLE pour ouvrir la page)'}`);
  console.log(`Discord  : ${WEBHOOK ? 'webhook actif' : 'aucun webhook'}`);
});
