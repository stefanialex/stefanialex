#!/usr/bin/env node
/**
 * Simulateur de parties — le poste QA / équilibrage de l'équipe, automatisé.
 *
 * Joue N parties sans écran, au hasard, et sort des statistiques. Sert à trois
 * choses, dans cet ordre d'importance :
 *   1. détecter les blocages avant qu'un testeur humain les trouve ;
 *   2. vérifier que la mécanique testée SE DÉCLENCHE — un instrument qui ne
 *      déclenche pas le phénomène qu'il mesure ne mesure rien ;
 *   3. mesurer la couverture des répliques : lesquelles ne sortent jamais.
 *
 *   npm install            (une fois, installe jsdom)
 *   node simulateur.js 20  (20 parties)
 */
'use strict';
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const JEU = path.join(__dirname, '..', 'prototypes', 'p01-banc-essai.html');
const PARTIES = Number(process.argv[2] || 10);
const PLAFOND_MS = 180000;         // garde-fou absolu ; le vrai détecteur est l'immobilité
const PAS_MS = 20;

function jouerUnePartie(src, idx) {
  return new Promise((resolve) => {
    const dom = new JSDOM(
      '<!doctype html><html><head><meta charset="utf-8"></head><body>' + src + '</body></html>',
      {
        runScripts: 'dangerously',
        pretendToBeVisual: true,
        beforeParse(w) {
          w.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
          w.fetch = () => Promise.reject(new Error('hors ligne'));
          w.Element.prototype.getBoundingClientRect = function () {
            const p = this.parentNode && this.parentNode.children
              ? [...this.parentNode.children].indexOf(this) : 0;
            return { left: p * 100, top: 0, right: p * 100 + 80, bottom: 90, width: 80, height: 90, x: p * 100, y: 0 };
          };
          w.onerror = (m) => { erreurs.push(String(m)); };
          w.addEventListener('unhandledrejection', (e) => {
            erreurs.push(String((e.reason && e.reason.message) || e.reason));
          });
        },
      }
    );

    const w = dom.window, d = w.document;
    const $ = (s) => d.querySelector(s);
    const erreurs = [];
    let clics = 0, immobile = 0, empreinte = '', debut = Date.now(), fini = false;

    const relever = () => [...d.querySelectorAll('#journal .l')].map((p) => p.textContent);

    const terminer = (statut) => {
      if (fini) return;
      fini = true;
      clearInterval(tic);
      const j = relever();
      const res = {
        idx, statut, clics, erreurs,
        ms: Date.now() - debut,
        lignes: j.length,
        engueulades: j.filter((t) => t.includes('ENGUEULADE')).length,
        rates: j.filter((t) => / rate /.test(t)).length,
        repliques: j.filter((t) => !/^[A-ZÉ]/.test(t) === false && t.length > 0),
        victoire: j.some((t) => t.includes('Salle vidée')),
        defaite: j.some((t) => t.includes('se replie')),
        tours: Number(($('#cTour') || {}).textContent) || null,
        journal: j,
      };
      try { dom.window.close(); } catch (e) {}
      resolve(res);
    };

    const tic = setInterval(() => {
      if (Date.now() - debut > PLAFOND_MS) return terminer('PLAFOND');
      const e = [
        d.querySelectorAll('#journal .l').length,
        $('#titre') ? $('#titre').textContent : '',
        $('#modale').innerHTML.length,
      ].join('|');
      if (e === empreinte) immobile++; else { immobile = 0; empreinte = e; }
      if (immobile > 300) return terminer('BLOCAGE');

      const bs = [...d.querySelectorAll('#modale button')];
      if (bs.length) {
        if (bs.some((x) => x.dataset.c === 'go')) return terminer('FIN');
        const b = bs.find((x) => x.dataset.c === 'ok') || bs.find((x) => x.dataset.c === 'x') || bs[0];
        b.click(); clics++; return;
      }
      const avc = $('#avc'); if (avc) { avc.click(); clics++; return; }
      const vis = $('.fig.visable'); if (vis) { vis.click(); clics++; return; }
      const act = [...d.querySelectorAll('#btns button')].filter((x) => !x.disabled);
      if (act.length) { act[clics % act.length].click(); clics++; }
    }, PAS_MS);
  });
}

(async () => {
  if (!fs.existsSync(JEU)) { console.error('Jeu introuvable :', JEU); process.exit(1); }
  const src = fs.readFileSync(JEU, 'utf8');
  const build = (src.match(/build (\d+)/) || [])[1] || '?';
  console.log(`Simulateur — build ${build} — ${PARTIES} parties\n`);

  const res = [];
  for (let i = 0; i < PARTIES; i++) {
    const r = await jouerUnePartie(src, i + 1);
    res.push(r);
    process.stdout.write(
      `  partie ${String(i + 1).padStart(3)} · ${r.statut.padEnd(7)} · ` +
      `${String(r.tours || '?').padStart(2)} tours · ${String(r.lignes).padStart(3)} lignes · ` +
      `${r.engueulades} engueulade(s)${r.erreurs.length ? ' · ' + r.erreurs.length + ' ERREUR(S)' : ''}\n`
    );
  }

  const ok = res.filter((r) => r.statut === 'FIN');
  const moy = (f) => (ok.length ? (ok.reduce((s, r) => s + f(r), 0) / ok.length) : 0);
  const bloquees = res.filter((r) => r.statut !== 'FIN');
  const erreurs = res.flatMap((r) => r.erreurs);
  const sansEng = ok.filter((r) => r.engueulades === 0);

  // couverture : chaque réplique du jeu est-elle déjà sortie ?
  const vues = new Set();
  res.forEach((r) => r.journal.forEach((t) => vues.add(t.trim())));
  const pools = [...src.matchAll(/"([^"\\]{12,120})"/g)].map((m) => m[1])
    .filter((s) => /[.!?…»]$/.test(s) && / /.test(s));
  const uniques = [...new Set(pools)];
  const jamais = uniques.filter((l) => ![...vues].some((v) => v.includes(l.slice(0, 28))));

  console.log('\n──────── SYNTHÈSE ────────');
  console.log(`Parties terminées      : ${ok.length}/${PARTIES}`);
  console.log(`Parties bloquées       : ${bloquees.length}   ${bloquees.length ? '← À CORRIGER EN PRIORITÉ' : '✓'}`);
  console.log(`Erreurs JS             : ${erreurs.length}   ${erreurs.length ? '← ' + erreurs[0].slice(0, 80) : '✓'}`);
  console.log(`Tours par partie       : ${moy((r) => r.tours || 0).toFixed(1)}`);
  console.log(`Répliques par partie   : ${moy((r) => r.lignes).toFixed(1)}`);
  console.log(`Engueulades par partie : ${moy((r) => r.engueulades).toFixed(2)}`);
  console.log(`Parties SANS engueulade: ${sansEng.length}/${ok.length}   ${sansEng.length ? '← la mécanique testée ne se déclenche pas toujours' : '✓'}`);
  console.log(`Taux de victoire       : ${ok.length ? Math.round(ok.filter((r) => r.victoire).length / ok.length * 100) : 0} %`);
  console.log(`Répliques jamais vues  : ${jamais.length}/${uniques.length}`);
  if (jamais.length) {
    console.log('\n  Extraits jamais déclenchés (revoir la fréquence ou le pool) :');
    jamais.slice(0, 12).forEach((l) => console.log('   · ' + l.slice(0, 84)));
  }

  const alerte = bloquees.length || erreurs.length || sansEng.length > ok.length * 0.25;
  console.log('\n' + (alerte ? '⚠  NE PAS LIVRER EN L\'ÉTAT' : '✓  Livrable'));
  process.exit(alerte ? 1 : 0);
})();
