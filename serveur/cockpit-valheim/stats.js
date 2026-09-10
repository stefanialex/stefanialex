// Script de la page des defis. Fichier separe : la CSP de Cockpit bloque les
// <script> en ligne sans erreur visible cote serveur.
const $ = (id) => document.getElementById(id);
const nf = (n, d = 0) => n.toLocaleString("fr-FR", { maximumFractionDigits: d });

/* ---------- theme : suivre le shell ----------
   Meme mecanique que la page principale : Cockpit ne pose pas la classe sur
   les pages tierces, il ecrit le choix dans localStorage et notifie par
   l'evenement storage. */
function majTheme() {
  const choix = localStorage.getItem("shell:style") || "auto";
  const sombre = choix === "dark" ||
    (choix === "auto" && window.matchMedia?.("(prefers-color-scheme: dark)").matches);
  document.documentElement.classList.toggle("pf-v6-theme-dark", sombre);
}
majTheme();
window.addEventListener("storage", (e) => { if (e.key === "shell:style") majTheme(); });
window.matchMedia?.("(prefers-color-scheme: dark)").addEventListener("change", majTheme);

function duree(s) {
  if (!isFinite(s) || s < 0) return "—";
  s = Math.floor(s);
  const j = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600),
        m = Math.floor((s % 3600) / 60);
  if (j) return `${j} j ${h} h`;
  if (h) return `${h} h ${String(m).padStart(2, "0")}`;
  return `${m} min`;
}

// Les dates viennent de SQLite en « 2026-09-04 13:43:03 » ; on n'affiche que ce
// qui se lit, la seconde n'apporte rien ici.
const court = (t) => t ? t.slice(0, 16).replace(" ", " à ") : "—";

/* ---------- fabrique d'elements ----------
   Tout passe par createElement et textContent, jamais par innerHTML : les
   pseudos viennent du journal du serveur et sont donc du texte non maitrise. */
function el(balise, classe, texte) {
  const n = document.createElement(balise);
  if (classe) n.className = classe;
  if (texte !== undefined) n.textContent = texte;
  return n;
}

function vide(tbody, message) {
  tbody.replaceChildren();
  const tr = el("tr"), td = el("td", "vide", message);
  td.colSpan = 6;
  tr.append(td);
  tbody.append(tr);
}

/* ---------- joueurs ---------- */
function rendJoueurs(joueurs) {
  const tb = $("joueurs").tBodies[0];
  $("compte-joueurs").textContent = joueurs.length
    ? `${joueurs.length} connus` : "";
  if (!joueurs.length) return vide(tb, "aucune session enregistrée");

  tb.replaceChildren();
  // La classe « num » existe deja dans valheim.css : chiffres alignes a droite
  // et chasse fixe, pour que les colonnes se comparent verticalement.
  const entete = el("tr");
  const colonnes = [["joueur", null], ["perso", "num"], ["sessions", "num"],
                    ["temps de jeu", "num"], ["morts", "num"], ["morts / h", "num"],
                    ["dernière fois", null]];
  for (const [t, c] of colonnes) entete.append(el("th", c, t));
  tb.append(entete);

  // Les compteurs sont ceux du personnage en cours. Ce que le compte a fait
  // avant s'ecrit a cote, en « + N » : le total reste lisible sans que le
  // personnage du jour herite des morts d'un personnage qui n'existe plus.
  const cumul = (cell, ecart) => {
    if (ecart) cell.append(el("span", "cumul", ` + ${ecart}`));
    return cell;
  };

  for (const j of joueurs) {
    const tr = el("tr");
    const nom = el("td");
    nom.append(el("span", null, j.pseudo));
    if (j.en_cours) nom.append(document.createTextNode(" "), el("span", "badge", "en jeu"));
    tr.append(nom);
    const perso = el("td", "num", `${j.personnage || 1}e`);
    if (j.depuis) perso.title = `personnage joué depuis le ${court(j.depuis)}`;
    tr.append(perso);
    tr.append(el("td", "num", nf(j.sessions)));
    const reste = Math.round((j.temps_total || j.temps) - j.temps);
    tr.append(cumul(el("td", "num", duree(j.temps)), reste >= 60 ? duree(reste) : null));
    const mortsAvant = (j.morts_total || j.morts) - j.morts;
    tr.append(cumul(el("td", "num", nf(j.morts)), mortsAvant > 0 ? nf(mortsAvant) : null));
    const taux = j.temps > 3600 ? nf(j.morts / (j.temps / 3600), 2) : "—";
    tr.append(el("td", "num", taux));
    tr.append(el("td", "ip", court(j.derniere)));
    tb.append(tr);
  }
}

/* ---------- le monde ---------- */
function rendMonde(d) {
  const dl = $("monde");
  dl.replaceChildren();
  const actif = (d.mondes || [])[0];
  const paires = [
    ["Monde", d.monde || "—"],
    ["Seed", actif ? actif.seed : "inconnue"],
    ["Jour", d.jour ? `jour ${d.jour}` : "—"],
    ["Objets dans le monde", d.zdos ? `${nf(Number(d.zdos))} ZDOs` : "—"],
    ["Dernière sauvegarde", court(d.derniere_sauvegarde)],
  ];
  for (const [cle, val] of paires) {
    dl.append(el("dt", null, cle));
    dl.append(el("dd", cle === "Seed" ? "seed" : null, String(val)));
  }
  $("note-generateur").textContent = actif
    ? `Format de sauvegarde ${actif.version_format}, générateur de monde ` +
      `version ${actif.version_generateur}. Si ce dernier nombre change avec ` +
      `la 1.0, la génération de monde a changé et aucune seed conseillée ` +
      `avant le lancement n'est fiable.`
    : "";
}

/* ---------- progression ---------- */
function rendProgression(etapes) {
  const tb = $("progression").tBodies[0];
  const boss = (etapes || []).filter((e) => e.boss);
  if (!boss.length) return vide(tb, "relevé des clés du monde pas encore effectué");
  tb.replaceChildren();
  for (const e of boss) {
    const tr = el("tr");
    tr.append(el("td", null, e.boss));
    // « exacte » distingue une chute observée par le relevé d'une borne haute
    // déduite d'un raid : dire « le » quand on ne sait que « avant le » serait
    // une précision inventée.
    tr.append(el("td", "ip",
      (e.exacte ? "vaincu le " : "vaincu avant le ") + court(e.premier)));
    tb.append(tr);
  }
}

/* ---------- defis ---------- */
function rendDefis(defis) {
  const zone = $("defis");
  zone.replaceChildren();
  if (!defis || !defis.length) {
    zone.append(el("div", "vide", "pas encore assez de données"));
    return;
  }
  for (const d of defis) {
    const carte = el("div", "carte");
    carte.append(el("h2", null, d.nom));
    carte.append(el("div", "regle", d.regle));
    let place = 0;
    for (const r of d.rangs) {
      place += 1;
      const ligne = el("div", r.tient ? "rang tient" : "rang");
      ligne.append(el("span", "place", `${place}.`));
      ligne.append(el("span", "qui", r.joueur));
      const v = d.unite === "duree" ? duree(r.valeur) : nf(r.valeur, 2);
      ligne.append(el("span", "valeur", String(v)));
      carte.append(ligne);
      const apres = el("div", "apres", r.note + (r.tient ? " — tient le défi" : ""));
      carte.append(apres);
    }
    carte.append(el("div", "note", `Mesure : ${d.metrique}.`));
    zone.append(carte);
  }
}

/* ---------- KPI et jalons ---------- */
function rendKpi(k) {
  const zone = $("kpi");
  zone.replaceChildren();
  if (!k || !k.kpis || !k.kpis.length) {
    zone.append(el("div", "vide",
      "aucun objectif défini (/etc/valheim/objectifs.json)"));
    return;
  }
  for (const e of k.kpis) {
    const carte = el("div", e.tenu ? "carte kpi tenu" : "carte kpi");
    carte.append(el("h2", null, e.libelle));
    const fmt = (v) => e.unite === "duree" ? duree(v) : nf(v, 3);
    if (e.valeur === null) {
      carte.append(el("div", "attente", "pas encore mesurable"));
    } else {
      const chiffre = el("div", "chiffre", fmt(e.valeur));
      chiffre.append(el("span", "sur",
        ` / ${fmt(e.cible)}${e.unite && e.unite !== "duree" ? " " + e.unite : ""}`));
      carte.append(chiffre);
      if (e.avancement !== null) {
        // <progress> plutot qu'une div dont on fixerait la largeur : la valeur
        // est un attribut, pas du style, donc rien ici ne depend de ce que la
        // CSP de Cockpit autorise. Et si la feuille de style ne chargeait pas,
        // le navigateur affiche quand meme sa barre native.
        const jauge = el("progress", e.tenu ? "jauge tenu" : "jauge");
        jauge.max = 1;
        jauge.value = e.avancement;
        jauge.textContent = Math.round(e.avancement * 100) + " %";
        carte.append(jauge);
      }
      carte.append(el("div", "etat", e.tenu
        ? "objectif tenu"
        : (e.sens === "moins" ? "au-dessus de la cible" : "en dessous de la cible")));
    }
    if (e.note) carte.append(el("div", "note", e.note));
    zone.append(carte);
  }
}

function rendJalons(k) {
  const tb = $("jalons").tBodies[0];
  if (!k || !k.jalons || !k.jalons.length) return vide(tb, "aucun jalon défini");
  tb.replaceChildren();
  const entete = el("tr");
  for (const [t, c] of [["boss", null], ["atteint en", "num"],
                        ["objectif", "num"], ["", null]]) {
    entete.append(el("th", c, t));
  }
  tb.append(entete);
  for (const j of k.jalons) {
    const tr = el("tr");
    tr.append(el("td", null, j.boss));
    if (j.heures_reelles === null) {
      const td = el("td", "vide", "aucun raid observé");
      td.colSpan = 3;
      tr.append(td);
    } else {
      tr.append(el("td", "num", nf(j.heures_reelles, 1) + " h"));
      tr.append(el("td", "num", j.heures_cumulees + " h"));
      const etat = el("td");
      etat.append(el("span", j.tenu ? "badge" : "ip", j.tenu ? "tenu" : "dépassé"));
      tr.append(etat);
    }
    tb.append(tr);
  }
}

/* ---------- roles et chantiers, declaratifs ---------- */
const ETIQUETTE = { fait: "fait", en_cours: "en cours", a_faire: "à faire" };

function rendChantiers(c) {
  const tf = $("fonctions").tBodies[0];
  const tc = $("chantiers").tBodies[0];
  if (!c) {
    vide(tf, "aucune fonction déclarée");
    vide(tc, "aucun chantier déclaré");
    $("compte-chantiers").textContent = "";
    return;
  }

  // Le pseudo en jeu quand il est connu, sinon le surnom du tableau : c'est ce
  // qui relie la feuille du groupe aux mesures du serveur.
  const nom = (cle) => {
    const j = (c.joueurs || {})[cle];
    return j && j.pseudo && j.pseudo !== "?" ? `${cle} (${j.pseudo})` : cle;
  };

  tf.replaceChildren();
  for (const f of c.fonctions || []) {
    const tr = el("tr");
    tr.append(el("td", null, f.nom));
    tr.append(el("td", "ip", f.titulaires.map(nom).join(", ") || "personne"));
    tf.append(tr);
  }

  const a = c.avancement || {};
  $("compte-chantiers").textContent = a.total ? `${a.faits} / ${a.total} faits` : "";
  tc.replaceChildren();
  for (const ch of c.chantiers || []) {
    const tr = el("tr");
    const etat = el("td");
    etat.append(el("span", ch.etat === "fait" ? "badge" : "ip",
                   ETIQUETTE[ch.etat] || ch.etat));
    tr.append(etat);
    tr.append(el("td", null, ch.nom));
    tr.append(el("td", "ip", ch.titulaires.map(nom).join(", ") || "—"));
    tc.append(tr);
  }
}

/* ---------- artisans ---------- */
function rendArtisans(d) {
  const tb = $("artisans").tBodies[0];
  $("compte-artisans").textContent = d.total ? `${d.total} objets` : "";
  const lignes = [...(d.artisans || []), ...(d.sans_compte || [])];
  if (!lignes.length) return vide(tb, "aucun objet fabriqué ne porte de nom");

  tb.replaceChildren();
  const entete = el("tr");
  for (const [t, c] of [["artisan", null], ["objets", "num"], ["personnages", null]])
    entete.append(el("th", c, t));
  tb.append(entete);

  for (const a of lignes) {
    const tr = el("tr");
    tr.append(el("td", null, a.compte || a.pseudo));
    tr.append(el("td", "num", nf(a.objets)));
    // Un joueur qui a refait son personnage a fabrique sous deux noms : le
    // total est celui du compte, le detail dit sous quel personnage.
    const detail = (a.personnages || [])
      .map((p) => `${p.pseudo} (${p.objets})`).join(", ");
    tr.append(el("td", "ip", detail || "nom non rattaché à un compte"));
    tb.append(tr);
  }
}

/* ---------- chargement ---------- */
function resume(d) {
  const p = [];
  if (d.monde) p.push(`monde « ${d.monde} »`);
  if (d.jour) p.push(`jour ${d.jour}`);
  const enJeu = (d.joueurs || []).filter((j) => j.en_cours).length;
  p.push(enJeu ? `${enJeu} en jeu` : "personne en jeu");
  if (d.genere) p.push(`relevé à ${d.genere.slice(11, 16)}`);
  $("resume").replaceChildren(el("span", null, p.join(" · ")));
}

function charge() {
  // Aucun privilege demande : la base et les metadonnees de monde sont
  // deposees par le collecteur en lecture pour tous, exprès pour que cette
  // page de consultation ne reclame pas l'acces administrateur.
  // Les artisans se lisent dans le monde et non dans la base : c'est un autre
  // programme, donc un autre appel. Il echoue seul, sans emporter la page --
  // il depend d'une archive de sauvegarde qui peut manquer sur une machine
  // neuve.
  cockpit.spawn(["/usr/local/bin/artisan-valheim.py", "--json"], { err: "message" })
    .then((sortie) => rendArtisans(JSON.parse(sortie)))
    .catch(() => vide($("artisans").tBodies[0], "relevé des artisans indisponible"));

  cockpit.spawn(["/usr/local/bin/stats-valheim.py", "--json"], { err: "message" })
    .then((sortie) => {
      const d = JSON.parse(sortie);
      $("erreur").textContent = "";
      resume(d);
      rendJoueurs(d.joueurs || []);
      rendMonde(d);
      rendProgression(d.progression || []);
      rendKpi(d.kpi);
      rendJalons(d.kpi);
      rendChantiers(d.chantiers);
      rendDefis(d.defis);
    })
    .catch((e) => {
      $("erreur").textContent = "Lecture des statistiques impossible : " +
        (e.message || e.toString());
    });
}

$("btn-actualiser").addEventListener("click", charge);
charge();
setInterval(charge, 30000);
