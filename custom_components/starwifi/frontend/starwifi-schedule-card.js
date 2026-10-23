// Weekly plan editor for Star Wi-Fi heaters: the app's 7 x 24 grid, saved with starwifi.set_schedule.
// Slots are "0" off, "1" comfort (the setpoint), "2" eco. Monday first.

const TEXT = {
  en: {
    title: "Heating plan",
    days: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    modes: { 1: "Comfort", 2: "Eco", 0: "Off" },
    copy: "Copy",
    to: "to",
    weekdays: "Mon–Fri",
    weekend: "Sat–Sun",
    all: "All days",
    undo: "Undo",
    save: "Save",
    saving: "Saving… about 20 s",
    saved: "Saved and sent to the heater.",
    hint: "Tap or drag to paint hours. Tap a day name to fill the whole day.",
    manual: "This heater is in manual mode, so it ignores this plan. Set it to auto to follow it.",
    none: "No plan read for this heater yet.",
    noHeater: "No Star Wi-Fi heater found.",
    locked: "Save or undo before you switch heater.",
  },
  fr: {
    title: "Programme de chauffe",
    days: ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"],
    modes: { 1: "Confort", 2: "Éco", 0: "Arrêt" },
    copy: "Copier",
    to: "vers",
    weekdays: "Lun–Ven",
    weekend: "Sam–Dim",
    all: "Tous les jours",
    undo: "Annuler",
    save: "Enregistrer",
    saving: "Enregistrement… environ 20 s",
    saved: "Enregistré et envoyé au radiateur.",
    hint: "Touchez ou glissez pour peindre les heures. Touchez un jour pour le remplir.",
    manual: "Ce radiateur est en mode manuel : il ignore ce programme. Passez-le en auto pour le suivre.",
    none: "Pas encore de programme lu pour ce radiateur.",
    noHeater: "Aucun radiateur Star Wi-Fi trouvé.",
    locked: "Enregistrez ou annulez avant de changer de radiateur.",
  },
};

const BRUSHES = ["1", "2", "0"];
const COPY_TARGETS = { weekdays: [0, 1, 2, 3, 4], weekend: [5, 6], all: [0, 1, 2, 3, 4, 5, 6] };

const STYLE = `
  .wrap { padding: 16px; }
  .head { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; justify-content: space-between; }
  .title { font-size: 18px; font-weight: 500; }
  select { font: inherit; padding: 6px 8px; border-radius: 8px; border: 1px solid var(--divider-color);
    background: var(--card-background-color); color: var(--primary-text-color); max-width: 100%; }
  .brushes { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
  button { font: inherit; cursor: pointer; }
  button:disabled { opacity: 0.5; cursor: default; }
  .brush { display: flex; align-items: center; gap: 6px; padding: 4px 12px; border-radius: 16px;
    border: 1px solid var(--divider-color); background: none; color: var(--primary-text-color); }
  .brush[aria-pressed="true"] { border-color: var(--primary-color); box-shadow: inset 0 0 0 1px var(--primary-color); }
  .sw { width: 12px; height: 12px; border-radius: 3px; }
  .grid { display: grid; grid-template-columns: 2.6em repeat(24, minmax(0, 1fr)); gap: 2px; margin-top: 12px;
    touch-action: none; user-select: none; -webkit-user-select: none; }
  .hour { grid-column: span 3; font-size: 10px; color: var(--secondary-text-color); }
  .day { align-self: center; font-size: 12px; color: var(--secondary-text-color); cursor: pointer; }
  .c { height: 22px; border-radius: 3px; cursor: pointer; }
  .s0 { background: var(--secondary-background-color, #e8e8e8); }
  .s1 { background: var(--state-climate-heat-color, #ff8100); }
  .s2 { background: var(--state-climate-cool-color, #2b9af9); }
  .now { outline: 2px solid var(--primary-text-color); outline-offset: -1px; }
  .tools { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-top: 12px; font-size: 14px; }
  .tools button, .undo { padding: 4px 10px; border-radius: 8px; border: 1px solid var(--divider-color);
    background: none; color: var(--primary-text-color); }
  .note { margin-top: 8px; font-size: 13px; color: var(--secondary-text-color); }
  .note:empty { display: none; }
  .warn { color: var(--warning-color, #ffa600); }
  .err { color: var(--error-color, #db4437); }
  .actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px; }
  .save { padding: 8px 16px; border: none; border-radius: 8px; background: var(--primary-color);
    color: var(--text-primary-color, #fff); }
`;

class StarWifiScheduleCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._brush = "1";
    this._saved = null; // 7 strings, as the heater has them
    this._draft = null; // 7 arrays of 24 states, as edited
    this._status = null;
    this._saving = false;
    this._painting = false;
  }

  static getStubConfig() {
    return {};
  }

  setConfig(config) {
    this._config = config || {};
    this._entity = this._config.entity || null;
    this._built = false;
    if (this._hass) this._update();
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  getCardSize() {
    return 8;
  }

  get _t() {
    const lang = this._hass?.locale?.language || this._hass?.language || "en";
    return TEXT[lang.startsWith("fr") ? "fr" : "en"];
  }

  _heaters() {
    const hass = this._hass;
    return Object.keys(hass.states)
      .filter((id) => id.startsWith("calendar.") && hass.entities?.[id]?.platform === "starwifi")
      .map((id) => {
        const device = hass.devices?.[hass.entities[id].device_id];
        return { id, name: device?.name_by_user || device?.name || hass.states[id].attributes.friendly_name || id };
      })
      .sort((a, b) => a.name.localeCompare(b.name));
  }

  _dirty() {
    return !!this._draft && !!this._saved && this._draft.map((d) => d.join("")).join() !== this._saved.join();
  }

  _update() {
    if (!this._config || !this._hass) return;
    const heaters = this._heaters();
    if (!this._entity || !this._hass.states[this._entity]) this._entity = heaters[0]?.id || null;
    if (!this._built) this._build();
    this._fillPicker(heaters);
    const week = this._entity ? this._hass.states[this._entity].attributes.week : null;
    const saved = Array.isArray(week) && week.length === 7 ? week : null;
    // A new plan from the cloud replaces the grid, unless the user is editing it.
    if (!this._saving && JSON.stringify(saved) !== JSON.stringify(this._saved)) {
      const keep = this._dirty();
      this._saved = saved;
      if (!keep) this._draft = saved ? saved.map((d) => d.split("")) : null;
    }
    this._paint();
  }

  _build() {
    const t = this._t;
    const root = this.shadowRoot;
    root.innerHTML = `<style>${STYLE}</style>
      <ha-card><div class="wrap">
        <div class="head"><div class="title"></div><select class="picker"></select></div>
        <div class="brushes"></div>
        <div class="grid"></div>
        <div class="tools"></div>
        <div class="note hint"></div>
        <div class="note manual warn"></div>
        <div class="note status"></div>
        <div class="actions"><button class="undo"></button><button class="save"></button></div>
      </div></ha-card>`;
    root.querySelector(".title").textContent = this._config.title || t.title;
    root.querySelector(".hint").textContent = t.hint;
    root.querySelector(".undo").textContent = t.undo;
    root.querySelector(".save").textContent = t.save;

    const brushes = root.querySelector(".brushes");
    for (const state of BRUSHES) {
      const b = document.createElement("button");
      b.className = "brush";
      b.dataset.brush = state;
      b.innerHTML = `<span class="sw s${state}"></span>`;
      b.append(t.modes[state]);
      brushes.append(b);
    }

    const grid = root.querySelector(".grid");
    grid.append(document.createElement("div"));
    for (let h = 0; h < 24; h += 3) {
      const label = document.createElement("div");
      label.className = "hour";
      label.textContent = String(h).padStart(2, "0");
      grid.append(label);
    }
    for (let d = 0; d < 7; d++) {
      const day = document.createElement("div");
      day.className = "day";
      day.dataset.day = d;
      day.textContent = t.days[d];
      grid.append(day);
      for (let h = 0; h < 24; h++) {
        const c = document.createElement("div");
        c.dataset.d = d;
        c.dataset.h = h;
        c.title = `${t.days[d]} ${String(h).padStart(2, "0")}:00`;
        grid.append(c);
      }
    }

    const tools = root.querySelector(".tools");
    const from = document.createElement("select");
    from.className = "from";
    t.days.forEach((name, d) => from.add(new Option(name, d)));
    tools.append(t.copy, from, t.to);
    for (const key of Object.keys(COPY_TARGETS)) {
      const b = document.createElement("button");
      b.dataset.copy = key;
      b.textContent = t[key];
      tools.append(b);
    }

    root.querySelector(".picker").addEventListener("change", (e) => this._pick(e.target.value));
    brushes.addEventListener("click", (e) => {
      const b = e.target.closest("[data-brush]");
      if (b) {
        this._brush = b.dataset.brush;
        this._paint();
      }
    });
    grid.addEventListener("pointerdown", (e) => this._down(e));
    grid.addEventListener("pointermove", (e) => this._move(e));
    for (const type of ["pointerup", "pointercancel"]) grid.addEventListener(type, () => (this._painting = false));
    tools.addEventListener("click", (e) => {
      const b = e.target.closest("[data-copy]");
      if (b) this._copy(Number(from.value), COPY_TARGETS[b.dataset.copy]);
    });
    root.querySelector(".undo").addEventListener("click", () => this._undo());
    root.querySelector(".save").addEventListener("click", () => this._save());
    this._built = true;
  }

  _fillPicker(heaters) {
    const picker = this.shadowRoot.querySelector(".picker");
    picker.hidden = !!this._config.entity || heaters.length < 2;
    const key = heaters.map((h) => `${h.id}=${h.name}`).join();
    if (picker.dataset.key !== key) {
      picker.replaceChildren(...heaters.map((h) => new Option(h.name, h.id)));
      picker.dataset.key = key;
    }
    if (this._entity) picker.value = this._entity;
  }

  _editable() {
    return !!this._draft && !this._saving;
  }

  _paint() {
    const t = this._t;
    const root = this.shadowRoot;
    const now = new Date();
    const today = (now.getDay() + 6) % 7;
    for (const c of root.querySelectorAll("[data-h]")) {
      const d = Number(c.dataset.d);
      const h = Number(c.dataset.h);
      const state = this._draft ? this._draft[d][h] : "0";
      c.className = `c s${state}${d === today && h === now.getHours() ? " now" : ""}`;
    }
    for (const b of root.querySelectorAll("[data-brush]")) {
      b.setAttribute("aria-pressed", String(b.dataset.brush === this._brush));
    }
    const editable = this._editable();
    const dirty = this._dirty();
    for (const el of root.querySelectorAll(".brush, .tools button, .tools select")) el.disabled = !editable;
    root.querySelector(".undo").disabled = !editable || !dirty;
    root.querySelector(".save").disabled = !editable || !dirty;
    root.querySelector(".picker").disabled = this._saving || dirty;

    const state = this._entity ? this._hass.states[this._entity] : null;
    root.querySelector(".manual").textContent = state?.attributes.followed === false ? t.manual : "";
    const status = root.querySelector(".status");
    let text = this._status?.text || "";
    const kind = this._status?.kind || "";
    if (!this._entity) text = t.noHeater;
    else if (!this._draft) text = t.none;
    else if (dirty && !this._saving && !text && !root.querySelector(".picker").hidden) text = t.locked;
    status.textContent = text;
    status.className = `note status ${kind}`;
  }

  _pick(id) {
    if (this._dirty() || this._saving) return;
    this._entity = id;
    this._saved = null;
    this._draft = null;
    this._status = null;
    this._update();
  }

  _set(cell) {
    if (!cell || !this._editable()) return;
    const d = Number(cell.dataset.d);
    const h = Number(cell.dataset.h);
    if (this._draft[d][h] === this._brush) return;
    this._draft[d][h] = this._brush;
    this._status = null;
    this._paint();
  }

  _down(e) {
    if (!this._editable()) return;
    const day = e.target.closest("[data-day]");
    if (day) {
      this._draft[Number(day.dataset.day)].fill(this._brush);
      this._status = null;
      this._paint();
      return;
    }
    const cell = e.target.closest("[data-h]");
    if (!cell) return;
    this._painting = true;
    e.currentTarget.setPointerCapture(e.pointerId);
    this._set(cell);
  }

  _move(e) {
    if (!this._painting) return;
    const el = this.shadowRoot.elementFromPoint(e.clientX, e.clientY);
    this._set(el?.closest?.("[data-h]"));
  }

  _copy(from, targets) {
    if (!this._editable()) return;
    for (const d of targets) if (d !== from) this._draft[d] = [...this._draft[from]];
    this._status = null;
    this._paint();
  }

  _undo() {
    if (!this._saved || this._saving) return;
    this._draft = this._saved.map((d) => d.split(""));
    this._status = null;
    this._paint();
  }

  async _save() {
    if (!this._editable() || !this._dirty()) return;
    const week = this._draft.map((d) => d.join(""));
    this._saving = true;
    this._status = { kind: "", text: this._t.saving };
    this._paint();
    try {
      await this._hass.callService("starwifi", "set_schedule", { week }, { entity_id: this._entity });
      this._saved = week;
      this._status = { kind: "", text: this._t.saved };
    } catch (err) {
      this._status = { kind: "err", text: err?.message || String(err) };
    } finally {
      this._saving = false;
      this._paint();
    }
  }
}

if (!customElements.get("starwifi-schedule-card")) {
  customElements.define("starwifi-schedule-card", StarWifiScheduleCard);
}
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "starwifi-schedule-card")) {
  window.customCards.push({
    type: "starwifi-schedule-card",
    name: "Star Wi-Fi schedule",
    description: "Edit the weekly plan of Star Wi-Fi (Climastar) heaters, like the app.",
  });
}
