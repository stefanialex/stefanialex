// Script du module Valheim.
// Fichier separe pour la meme raison que valheim.css : la CSP de Cockpit
// bloque les <script> en ligne, sans erreur visible cote serveur.
const $ = (id) => document.getElementById(id);
const lance = (argv, sudo = "require") =>
  cockpit.spawn(argv, { err: "message", superuser: sudo });

const nf = (n, d = 0) => n.toLocaleString("fr-FR", { maximumFractionDigits: d });

/* ---------- thème : suivre le shell ----------
   Cockpit ne pose pas la classe sur les pages tierces. Il enregistre le choix
   dans localStorage["shell:style"] (auto | light | dark), partagé avec cette
   iframe puisqu'elle est de même origine, et notifie par l'événement storage. */
function majTheme() {
  const choix = localStorage.getItem("shell:style") || "auto";
  const sombre = choix === "dark" ||
    (choix === "auto" && window.matchMedia?.("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("pf-v6-theme-dark", sombre);
}
majTheme();
window.addEventListener("storage", (e) => { if (e.key === "shell:style") majTheme(); });
window.matchMedia?.("(prefers-color-scheme: dark)").addEventListener("change", majTheme);

function duree(ms) {
  if (!isFinite(ms) || ms < 0) return "—";
  const s = Math.floor(ms / 1000);
  const j = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
  if (j) return `${j} j ${h} h`;
  if (h) return `${h} h ${m} min`;
  if (m) return `${m} min`;
  return `${s} s`;
}
const octets = (o) => o > 1e9 ? nf(o / 1e9, 1) + " Go" : o > 1e6 ? nf(o / 1e6, 1) + " Mo" : nf(o / 1e3) + " ko";

function classeLatence(ms) {
  if (ms === null) return "grave";
  if (ms < 50) return "ok";
  if (ms < 150) return "alerte";
  return "grave";
}

/* ---------- bandeau de résumé ---------- */
const etat = { actif: null, joueurs: null, zdos: null, maj: null };
function majResume() {
  const p = [];
  if (etat.actif !== null)
    p.push(`<span class="pastille ${etat.actif ? "ok" : "grave"}">${etat.actif ? "en service" : "à l'arrêt"}</span>`);
  if (etat.joueurs !== null)
    p.push(`<span>${etat.joueurs} joueur${etat.joueurs > 1 ? "s" : ""} en jeu</span>`);
  if (etat.zdos !== null) p.push(`<span>${nf(etat.zdos)} objets dans le monde</span>`);
  if (etat.maj) p.push(`<span>actualisé à ${etat.maj}</span>`);
  $("resume").innerHTML = p.join("");
}

/* ---------- état du service ---------- */
async function majService() {
  try {
    const t = await lance(["systemctl", "show", "valheim.service", "-p", "ActiveState",
      "-p", "SubState", "-p", "ExecMainStartTimestamp", "-p", "MemoryCurrent",
      "-p", "NRestarts", "-p", "CPUUsageNSec"]);
    const p = {};
    t.trim().split("\n").forEach((l) => { const i = l.indexOf("="); p[l.slice(0, i)] = l.slice(i + 1); });
    const actif = p.ActiveState === "active";
    etat.actif = actif;
    const depuis = p.ExecMainStartTimestamp ? new Date(p.ExecMainStartTimestamp.replace(/^\w+ /, "")) : null;
    $("service").innerHTML = `
      <dt>État</dt><dd><span class="pastille ${actif ? "ok" : "grave"}">${actif ? "en service" : p.ActiveState}</span></dd>
      <dt>Démarré depuis</dt><dd>${depuis && !isNaN(depuis) ? duree(Date.now() - depuis) : "—"}</dd>
      <dt>Mémoire</dt><dd>${p.MemoryCurrent && p.MemoryCurrent !== "[not set]" ? octets(+p.MemoryCurrent) : "—"}</dd>
      <dt>Redémarrages auto</dt><dd class="${+p.NRestarts > 0 ? "alerte" : ""}">${p.NRestarts ?? "—"}</dd>`;
    $("err-service").textContent = "";
  } catch (e) { $("err-service").textContent = e.message || String(e); }
}

/* ---------- journal : joueurs et monde ---------- */
function analyseJournal(texte) {
  const joueurs = new Map();
  const zones = new Set();
  let attente = null, ambigu = false;
  let zdos = null, sauve = null, dateSauve = null, donjons = 0;
  for (const l of texte.split("\n")) {
    const dt = (l.match(/^(\S+T\S+)/) || [])[1];
    let m;
    if ((m = l.match(/Got connection SteamID (\d+)/))) {
      // Deux connexions sans nom entre elles : on ne saura pas laquelle porte
      // le personnage qui va apparaitre, donc on ne devine pas.
      ambigu = attente !== null;
      attente = m[1];
      const e = joueurs.get(m[1]) || { id: m[1] };
      e.enligne = true; e.depuis = dt; joueurs.set(m[1], e);
    } else if ((m = l.match(/Got character ZDOID from (.+?) :/))) {
      // Une connexion ne nomme qu'un personnage, le premier qui la suit.
      // Sans cette remise a zero, « attente » restait sur le dernier entrant
      // et TOUTE ligne ZDOID ulterieure -- une mort, une reapparition, celles
      // d'un autre joueur -- ecrasait son nom. C'est ce qui a affiche « Djoos
      // Io » en face du compte de Bab-y le 2026-09-10, deux Djoose dans la
      // meme table pour quatre joueurs.
      if (attente && !ambigu) {
        const e = joueurs.get(attente) || { id: attente };
        e.nom = m[1].trim(); joueurs.set(attente, e);
      }
      attente = null; ambigu = false;
    } else if ((m = l.match(/Closing socket (\d+)/))) {
      const e = joueurs.get(m[1]); if (e) e.enligne = false;
    } else if ((m = l.match(/Connections \d+ ZDOS:(\d+)/)) || (m = l.match(/Saved (\d+) ZDOs/))) {
      // La 1.0 a remplace « Saved N ZDOs » par un recensement periodique.
      // L'ancien motif est garde pour relire un journal d'avant la bascule.
      zdos = +m[1];
    } else if ((m = l.match(/World save \(5\/5\) done\. Total time \[(\d+)ms\]/)) ||
               (m = l.match(/World saved \(\s*([\d.,]+)\s*ms\s*\)/))) {
      sauve = parseFloat(String(m[1]).replace(",", ".")); dateSauve = dt;
    } else if ((m = l.match(/Placed location \S+ in zone (\S+)/)) ||
               (m = l.match(/Placed locations in zone (\S+)/))) {
      // La 1.0 ecrit une ligne par lieu pose, donc plusieurs par zone : c'est
      // un ensemble de coordonnees, pas un compteur de lignes.
      zones.add(m[1]);
    } else if (/Placed \d+ rooms/.test(l)) { donjons++; }
  }
  return { joueurs: [...joueurs.values()], zdos, sauve, dateSauve, donjons,
           zones: zones.size };
}

async function majJournal() {
  try {
    const t = await lance(["journalctl", "-u", "valheim", "--since", "-12h", "--no-pager", "-o", "short-iso"]);
    const d = analyseJournal(t);
    const enligne = d.joueurs.filter((j) => j.enligne);
    etat.joueurs = enligne.length; etat.zdos = d.zdos;
    $("compte-joueurs").textContent = enligne.length ? `${enligne.length} connecté${enligne.length > 1 ? "s" : ""}` : "";
    const tb = $("joueurs").querySelector("tbody");
    if (!d.joueurs.length) {
      tb.innerHTML = `<tr><td class="vide">Personne ne s'est connecté depuis 12 heures.</td></tr>`;
    } else {
      d.joueurs.sort((a, b) => (b.enligne - a.enligne) || String(a.nom).localeCompare(String(b.nom)));
      tb.innerHTML = `<tr><th>Joueur</th><th>État</th><th>Depuis</th><th>Compte Steam</th></tr>` +
        d.joueurs.map((j) => {
          const t0 = j.depuis ? new Date(j.depuis) : null;
          return `<tr>
            <td>${j.nom ? j.nom : '<span class="doux">personnage non chargé</span>'}</td>
            <td><span class="pastille ${j.enligne ? "ok" : "doux"}">${j.enligne ? "en jeu" : "parti"}</span></td>
            <td>${j.enligne && t0 && !isNaN(t0) ? duree(Date.now() - t0) : "—"}</td>
            <td class="doux">${j.id}</td></tr>`;
        }).join("");
    }
    $("monde").innerHTML = `
      <dt>Objets du monde (ZDOs)</dt><dd>${d.zdos !== null ? nf(d.zdos) : "—"}</dd>
      <dt>Zones découvertes (12 h)</dt><dd>${nf(d.zones)}</dd>
      <dt>Dernière sauvegarde du jeu</dt><dd>${d.dateSauve ? "il y a " + duree(Date.now() - new Date(d.dateSauve)) : "—"}</dd>
      <dt>Durée de cette sauvegarde</dt><dd class="${d.sauve > 2000 ? "alerte" : ""}">${d.sauve !== null ? nf(d.sauve) + " ms" : "—"}</dd>
      <dt>Donjons générés (12 h)</dt><dd>${d.donjons}</dd>`;
  } catch (e) { $("err-service").textContent = e.message || String(e); }
}

/* ---------- réseau par pair ---------- */
let precedent = new Map(), precedentT = null;

async function majReseau() {
  try {
    const brut = await lance(["tailscale", "status", "--json"], "try");
    const st = JSON.parse(brut);
    const pairs = Object.values(st.Peer || {}).filter((p) => p.Online);
    const maintenant = Date.now();
    const dt = precedentT ? (maintenant - precedentT) / 1000 : null;

    const lignes = await Promise.all(pairs.map(async (p) => {
      const ip = (p.TailscaleIPs || [])[0] || "";
      let ms = null;
      try {
        const r = await lance(["tailscale", "ping", "-c", "1", "--timeout", "3s", ip], "try");
        const m = r.match(/in ([\d.]+)(ms|s)\b/);
        if (m) ms = parseFloat(m[1]) * (m[2] === "s" ? 1000 : 1);
      } catch (e) { /* pair injoignable : reste a null */ }
      let nom = p.HostName || ip;
      if (/^device-of/.test(nom)) {
        try {
          const w = await lance(["tailscale", "whois", ip], "try");
          const m = w.match(/Name:\s+(\S+@\S+)/);
          if (m) nom = m[1];
        } catch (e) { /* on garde HostName */ }
      }
      const av = precedent.get(ip);
      const env = av && dt ? Math.max(0, (p.TxBytes - av.tx) / dt / 1024) : null;
      const rec = av && dt ? Math.max(0, (p.RxBytes - av.rx) / dt / 1024) : null;
      precedent.set(ip, { tx: p.TxBytes, rx: p.RxBytes });
      return { nom, ip, ms, env, rec, direct: !!p.CurAddr };
    }));
    precedentT = maintenant;

    const tb = $("reseau").querySelector("tbody");
    lignes.sort((a, b) => (b.ms ?? 1e9) - (a.ms ?? 1e9));
    tb.innerHTML = `<tr><th>Appareil</th><th>Latence</th><th>Chemin</th>
        <th class="num">Envoyé</th><th class="num">Reçu</th></tr>` +
      lignes.map((l) => `<tr>
        <td>${l.nom}<br><span class="ip">${l.ip}</span></td>
        <td><span class="pastille ${classeLatence(l.ms)}">${l.ms === null ? "sans réponse" : nf(l.ms) + " ms"}</span></td>
        <td>${l.direct ? '<span class="ok">direct</span>' : '<span class="alerte">relais DERP</span>'}</td>
        <td class="num">${l.env === null ? '<span class="doux">…</span>' : nf(l.env) + " ko/s"}</td>
        <td class="num">${l.rec === null ? '<span class="doux">…</span>' : nf(l.rec) + " ko/s"}</td>
      </tr>`).join("");
    $("err-reseau").textContent = lignes.length ? "" : "Aucun pair Tailscale en ligne.";
  } catch (e) { $("err-reseau").textContent = e.message || String(e); }
}

/* ---------- minuteries et archives ---------- */
async function majSauvegardes() {
  const timers = ["sauvegarde-valheim.timer", "sauvegarde-valheim-hors-site.timer", "redemarrage-valheim.timer"];
  const etiquettes = { "sauvegarde-valheim.timer": "Sauvegarde locale",
    "sauvegarde-valheim-hors-site.timer": "Copie hors site",
    "redemarrage-valheim.timer": "Redémarrage hebdomadaire" };
  try {
    const script = timers.map((u) =>
      `n=$(systemctl show -P NextElapseUSecRealtime ${u}); ` +
      `echo "${u}|$(date -d "$n" +%s 2>/dev/null)"`).join("; ");
    const sortie = await lance(["/bin/sh", "-c", script]);
    const res = sortie.trim().split("\n").map((l) => {
      const [u, epoch] = l.split("|");
      const s = parseInt(epoch, 10);
      return { u, suiv: isFinite(s) && s > 0 ? s * 1000 : null };
    });
    $("minuteries").querySelector("tbody").innerHTML =
      `<tr><th>Tâche</th><th class="num">Dans</th></tr>` + res.map((r) => `<tr>
        <td>${etiquettes[r.u] || r.u}</td>
        <td class="num">${r.suiv ? duree(r.suiv - Date.now()) : '<span class="doux">—</span>'}</td></tr>`).join("");

    const t = await lance(["/bin/sh", "-c",
      "ls -1t /srv/ia/sauvegardes-valheim/*.tar.gz 2>/dev/null | head -6 | xargs -r stat -c '%n|%s|%Y'"]);
    const arch = t.trim().split("\n").filter(Boolean).map((l) => {
      const [chemin, taille, mtime] = l.split("|");
      return { nom: chemin.split("/").pop(), taille: +taille, date: +mtime * 1000 };
    });
    $("archives").querySelector("tbody").innerHTML = arch.length
      ? `<tr><th>Archive</th><th class="num">Taille</th><th class="num">Âge</th></tr>` +
        arch.map((a) => `<tr><td>${a.nom}</td>
          <td class="num">${octets(a.taille)}</td>
          <td class="num">${duree(Date.now() - a.date)}</td></tr>`).join("")
      : `<tr><td class="vide">Aucune archive lisible.</td></tr>`;
  } catch (e) { /* silencieux : les cartes gardent leur contenu */ }
}

/* ---------- actions ---------- */
$("btn-relancer").onclick = async () => {
  if (!window.confirm("Redémarrer le serveur Valheim ?\n\nLe monde est sauvegardé à l'arrêt " +
      "(KillSignal=SIGINT, 120 s de marge), mais tous les joueurs connectés seront déconnectés.")) return;
  const b = $("btn-relancer"); b.disabled = true; b.textContent = "redémarrage…";
  try { await lance(["systemctl", "restart", "valheim.service"]); }
  catch (e) { $("err-service").textContent = e.message || String(e); }
  b.disabled = false; b.textContent = "Redémarrer la partie";
  tout();
};

$("btn-sauver").onclick = async () => {
  const b = $("btn-sauver"); b.disabled = true; b.textContent = "sauvegarde…";
  try { await lance(["systemctl", "start", "sauvegarde-valheim.service"]); }
  catch (e) { $("err-service").textContent = e.message || String(e); }
  b.disabled = false; b.textContent = "Sauvegarder maintenant";
  majSauvegardes();
};

/* ---------- boucle ---------- */
async function tout() {
  await Promise.all([majService(), majJournal(), majSauvegardes()]);
  etat.maj = new Date().toLocaleTimeString("fr-FR");
  majResume();
}
tout();
majReseau();
setInterval(tout, 10000);
setInterval(majReseau, 20000);
