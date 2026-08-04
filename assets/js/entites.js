/**
 * Journal de Gaspard — socle partagé des pages d'entités (équipes, techniques).
 *
 * Les quatre pages equipes/equipe/techniques/technique partagent l'essentiel de
 * leur logique : charger un JSON, filtrer, trier, afficher, et relier chaque
 * entité à des personnages. Ce module porte cette mécanique une seule fois ;
 * chaque page ne décrit plus que ce qui lui est propre (source, libellés,
 * badges, clé de relation).
 *
 * Module ES natif : aucun build step, aucune dépendance — conforme à agents.md.
 *
 * Note : personnages.js et personnage.html dupliquent encore certains de ces
 * helpers. Les migrer est un chantier à part, volontairement hors de celui-ci.
 */

const PERSONNAGES_SOURCE = "/assets/data/personnages.json";
const PERSONNAGE_BASE = "/univers/olive-et-tom/personnage.html?slug=";

/** Libellés FR des types d'équipe présents dans equipes.json. */
export const TYPE_LABELS = {
  club: "Club",
  national: "Sélection nationale",
  school: "École"
};

/** Libellés FR des catégories d'âge présentes dans equipes.json. */
export const AGE_LABELS = {
  adult: "Adultes",
  youth: "Jeunes",
  "middle-school": "Collège",
  "high-school": "Lycée",
  elementary: "Primaire",
  olympic: "Olympique"
};

const POSITION_LABELS = {
  goalkeeper: "Gardien",
  defender: "Défenseur",
  midfielder: "Milieu",
  forward: "Attaquant"
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

export function safeText(value) {
  return String(value ?? "").trim();
}

/** Normalise pour la recherche : sans accents, sans casse. */
function toComparable(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .trim();
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function getInitials(name) {
  return (
    String(name || "?")
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((chunk) => chunk[0].toUpperCase())
      .join("") || "?"
  );
}

/**
 * Portrait de repli : initiales sur dégradé, encodé en data: URI.
 * Aucune requête réseau, aucun asset à déployer.
 */
export function makePlaceholder(name) {
  const initials = getInitials(name);
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="640" height="640" viewBox="0 0 640 640" role="img" aria-label="Portrait indisponible de ${escapeHtml(name)}">
      <defs>
        <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#16233f"/>
          <stop offset="100%" stop-color="#345da8"/>
        </linearGradient>
      </defs>
      <rect x="14" y="14" width="612" height="612" rx="72" fill="url(#bg)"/>
      <text x="320" y="332" text-anchor="middle" dominant-baseline="middle"
            font-family="Inter, Segoe UI, Roboto, Arial, sans-serif"
            font-size="168" font-weight="800" fill="#f5f7ff" letter-spacing="4">${initials}</text>
    </svg>
  `;

  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

function debounce(callback, delay) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => callback(...args), delay);
  };
}

/** Accorde un nom commun et le préfixe de son compte. */
function plural(count, singular, pluralForm) {
  return `${count} ${count > 1 ? pluralForm : singular}`;
}

function compareNames(left, right) {
  return left.localeCompare(right, "fr", { sensitivity: "base" });
}

/**
 * Le champ `position` du Fandom est une concaténation d'infobox
 * ("Attacking midfielderForward") : on ne garde que le premier poste reconnu.
 */
function positionLabel(rawPosition) {
  const key = toComparable(rawPosition);

  if (!key || key === "unknown") {
    return "";
  }

  const match = Object.keys(POSITION_LABELS).find((position) => key.includes(position));

  return match ? POSITION_LABELS[match] : "";
}

async function fetchJson(url) {
  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`HTTP ${response.status} sur ${url}`);
  }

  const data = await response.json();

  return Array.isArray(data) ? data : [];
}

/** Révèle les cartes à l'entrée dans le viewport (même effet que la liste des personnages). */
const revealObserver = new IntersectionObserver(
  (entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add("is-revealed");
        revealObserver.unobserve(entry.target);
      }
    });
  },
  { threshold: 0.15 }
);

// ---------------------------------------------------------------------------
// Cartes personnage (utilisées par les fiches détail)
// ---------------------------------------------------------------------------

/**
 * Indexe les personnages par slug pour retrouver portrait et poste en O(1).
 */
function indexBySlug(personnages) {
  const index = new Map();

  personnages.forEach((personnage) => {
    const slug = safeText(personnage.slug);
    if (slug) {
      index.set(slug, personnage);
    }
  });

  return index;
}

function buildPersonCard(relation, personnage) {
  const name = safeText(relation.name) || safeText(relation.slug) || "Personnage";
  const slug = safeText(relation.slug);

  const card = document.createElement("li");
  card.className = "entity-person";

  const link = document.createElement("a");
  link.className = "entity-person-link";
  link.href = safeText(relation.url) || `${PERSONNAGE_BASE}${encodeURIComponent(slug)}`;

  const image = document.createElement("img");
  image.className = "entity-person-image";
  image.loading = "lazy";
  image.alt = `Portrait de ${name}`;
  const fallback = makePlaceholder(name);
  image.addEventListener(
    "error",
    () => {
      image.src = fallback;
    },
    { once: true }
  );
  image.src = safeText(personnage?.image) || fallback;

  const body = document.createElement("div");
  body.className = "entity-person-body";

  const title = document.createElement("p");
  title.className = "entity-person-name";
  title.textContent = name;
  body.appendChild(title);

  const position = positionLabel(personnage?.position || personnage?.poste);
  if (position) {
    const positionEl = document.createElement("p");
    positionEl.className = "entity-person-position";
    positionEl.textContent = position;
    body.appendChild(positionEl);
  }

  link.append(image, body);
  card.appendChild(link);

  return card;
}

// ---------------------------------------------------------------------------
// Page liste
// ---------------------------------------------------------------------------

/**
 * Monte une page liste d'entités.
 *
 * @param {object} config
 * @param {string}   config.source        JSON à charger.
 * @param {string}   config.detailBase    Base d'URL de la fiche détail.
 * @param {string}   config.relationKey   Clé du tableau de personnages liés.
 * @param {object}   config.labels        { unit, units, relation, relations }
 * @param {function} [config.getBadges]   entry => string[] affichés sur la carte.
 * @param {object}   [config.filter]      { selectId, getValue, labels } filtre facultatif.
 */
export async function createEntityListPage(config) {
  const grid = document.querySelector("#entities-grid");
  const searchInput = document.querySelector("#filter-search");
  const sortSelect = document.querySelector("#sort-select");
  const resultsCount = document.querySelector("#results-count");
  const emptyState = document.querySelector("#empty-state");
  const resetButton = document.querySelector("#reset-filters");
  const filterSelect = config.filter ? document.querySelector(`#${config.filter.selectId}`) : null;

  if (!grid) {
    return;
  }

  let entities = [];

  function normalize(entry) {
    const slug = safeText(entry.slug);
    const name = safeText(entry.name) || slug;
    const relations = Array.isArray(entry[config.relationKey]) ? entry[config.relationKey] : [];
    const badges = config.getBadges ? config.getBadges(entry).filter(Boolean) : [];

    return {
      slug,
      name,
      badges,
      relationCount: relations.length,
      filterValue: config.filter ? safeText(config.filter.getValue(entry)) : "",
      searchableText: toComparable([name, slug, badges.join(" ")].join(" ")),
      url: safeText(entry.url) || `${config.detailBase}${encodeURIComponent(slug)}`,
      element: null
    };
  }

  function buildCard(entity) {
    const card = document.createElement("article");
    card.className = "entity-card";

    const link = document.createElement("a");
    link.className = "entity-card-link";
    link.href = entity.url;

    const title = document.createElement("h3");
    title.className = "entity-card-name";
    title.textContent = entity.name;
    link.appendChild(title);

    if (entity.badges.length) {
      const badges = document.createElement("p");
      badges.className = "entity-card-badges";

      entity.badges.forEach((label) => {
        const badge = document.createElement("span");
        badge.className = "entity-badge";
        badge.textContent = label;
        badges.appendChild(badge);
      });

      link.appendChild(badges);
    }

    const meta = document.createElement("p");
    meta.className = "entity-card-meta";
    meta.textContent = plural(
      entity.relationCount,
      config.labels.relation,
      config.labels.relations
    );
    link.appendChild(meta);

    card.appendChild(link);

    return card;
  }

  function applyFilters() {
    const query = toComparable(searchInput?.value);
    const selected = filterSelect ? filterSelect.value : "";
    let visibleCount = 0;

    entities.forEach((entity) => {
      const matchesFilter = !selected || entity.filterValue === selected;
      const matchesSearch = !query || entity.searchableText.includes(query);
      const isVisible = matchesFilter && matchesSearch;

      entity.element.classList.toggle("is-hidden", !isVisible);

      if (isVisible) {
        visibleCount += 1;
      }
    });

    if (resultsCount) {
      const noun = plural(visibleCount, config.labels.unit, config.labels.units);
      resultsCount.textContent = `${noun} affichée${visibleCount > 1 ? "s" : ""}`;
    }

    if (emptyState) {
      emptyState.hidden = visibleCount !== 0;
    }
  }

  function render(sorted) {
    entities = sorted;
    grid.textContent = "";

    const fragment = document.createDocumentFragment();

    sorted.forEach((entity) => {
      const card = buildCard(entity);
      entity.element = card;
      revealObserver.observe(card);
      fragment.appendChild(card);
    });

    grid.appendChild(fragment);
    applyFilters();
  }

  function sortEntities(mode, data) {
    return [...data].sort((left, right) => {
      if (mode === "za") {
        return compareNames(right.name, left.name);
      }

      if (mode === "relations") {
        return right.relationCount - left.relationCount || compareNames(left.name, right.name);
      }

      return compareNames(left.name, right.name);
    });
  }

  function populateFilterOptions(data) {
    if (!filterSelect || !config.filter) {
      return;
    }

    const values = [...new Set(data.map((entity) => entity.filterValue).filter(Boolean))].sort(
      compareNames
    );

    values.forEach((value) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = config.filter.labels[value] || value;
      filterSelect.appendChild(option);
    });
  }

  try {
    const data = await fetchJson(config.source);
    const normalized = data.map(normalize).filter((entity) => entity.slug && entity.name);

    populateFilterOptions(normalized);

    searchInput?.addEventListener("input", debounce(applyFilters, 150));
    filterSelect?.addEventListener("change", applyFilters);
    sortSelect?.addEventListener("change", () => {
      render(sortEntities(sortSelect.value, normalized));
    });
    resetButton?.addEventListener("click", () => {
      if (searchInput) {
        searchInput.value = "";
      }
      if (filterSelect) {
        filterSelect.value = "";
      }
      applyFilters();
      searchInput?.focus();
    });

    render(sortEntities(sortSelect?.value || "az", normalized));
  } catch (error) {
    console.error("Impossible de charger la liste:", error);
    grid.innerHTML = '<p class="entity-error">Impossible de charger les données. Réessayez plus tard.</p>';
  }
}

// ---------------------------------------------------------------------------
// Page détail
// ---------------------------------------------------------------------------

/**
 * Monte une fiche détail d'entité.
 *
 * @param {object} config
 * @param {string}   config.source          JSON de l'entité.
 * @param {string}   config.relationKey     Clé du tableau de personnages liés.
 * @param {string}   config.titlePrefix     Préfixe du <title> de la page.
 * @param {object}   config.labels          { notFound, notFoundHint, section, relation, relations }
 * @param {function} [config.getBadges]     entry => string[] affichés sous le titre.
 * @param {function} [config.getSubtitle]   entry => string affiché en surtitre discret.
 */
export async function createEntityDetailPage(config) {
  const shell = document.querySelector("#entity-detail-shell");

  if (!shell) {
    return;
  }

  function renderNotFound() {
    shell.innerHTML = `
      <div class="entity-detail-empty">
        <h2>${escapeHtml(config.labels.notFound)}</h2>
        <p>${escapeHtml(config.labels.notFoundHint)}</p>
      </div>
    `;
  }

  function render(entry, personnagesIndex) {
    const name = safeText(entry.name) || safeText(entry.slug);
    const relations = Array.isArray(entry[config.relationKey]) ? entry[config.relationKey] : [];
    const badges = config.getBadges ? config.getBadges(entry).filter(Boolean) : [];
    const subtitle = config.getSubtitle ? safeText(config.getSubtitle(entry)) : "";

    shell.textContent = "";

    const content = document.createElement("div");
    content.className = "entity-detail-content";

    const header = document.createElement("header");
    header.className = "entity-detail-header";

    const title = document.createElement("h2");
    title.textContent = name;
    header.appendChild(title);

    if (subtitle) {
      const subtitleEl = document.createElement("p");
      subtitleEl.className = "entity-detail-subtitle";
      subtitleEl.textContent = subtitle;
      header.appendChild(subtitleEl);
    }

    if (badges.length) {
      const badgeRow = document.createElement("p");
      badgeRow.className = "entity-detail-badges";

      badges.forEach((label) => {
        const badge = document.createElement("span");
        badge.className = "entity-badge";
        badge.textContent = label;
        badgeRow.appendChild(badge);
      });

      header.appendChild(badgeRow);
    }

    content.appendChild(header);

    const section = document.createElement("section");
    section.className = "entity-detail-section";

    const sectionTitle = document.createElement("h3");
    sectionTitle.textContent = `${config.labels.section} (${relations.length})`;
    section.appendChild(sectionTitle);

    if (relations.length) {
      const list = document.createElement("ul");
      list.className = "entity-person-grid";

      relations.forEach((relation) => {
        const personnage = personnagesIndex.get(safeText(relation.slug));
        list.appendChild(buildPersonCard(relation, personnage));
      });

      section.appendChild(list);
    } else {
      const empty = document.createElement("p");
      empty.className = "entity-detail-none";
      empty.textContent = "Aucun personnage rattaché.";
      section.appendChild(empty);
    }

    content.appendChild(section);
    shell.appendChild(content);

    document.title = `${config.titlePrefix} ${name}`;
  }

  const slug = safeText(new URLSearchParams(window.location.search).get("slug"));

  if (!slug) {
    renderNotFound();
    return;
  }

  try {
    const [entries, personnages] = await Promise.all([
      fetchJson(config.source),
      fetchJson(PERSONNAGES_SOURCE)
    ]);

    const entry = entries.find((item) => safeText(item.slug) === slug);

    if (!entry) {
      renderNotFound();
      return;
    }

    render(entry, indexBySlug(personnages));
  } catch (error) {
    console.error("Impossible de charger la fiche:", error);
    renderNotFound();
  }
}
