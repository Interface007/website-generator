"use strict";

/*
 * Flip-Cards – spaced-repetition knowledge quiz.
 * Data comes from /flip-cards.json; per-card "index" values and the chosen
 * language are persisted in localStorage. A higher index gives a card a larger
 * draw weight; answering "known" lowers the index by 10 so it resurfaces less
 * often.
 */
(function () {

    /** UI strings per language. */
    const I18N = {
        de: {
            question: "Frage", answer: "Antwort",
            domain: "Bereich",
            reveal: "Antwort anzeigen (Leertaste)",
            conceal: "Frage anzeigen (Leertaste)",
            know: "✓ Gewusst", dontKnow: "✗ Nicht gewusst",
            reset: "Zurücksetzen",
            filterTitle: "Bereiche",
            resetConfirm: "Lernfortschritt für diese Sprache wirklich zurücksetzen?",
            hintReveal: "Leertaste zum Aufdecken",
            hintDecide: "Leertaste zur Frage    ·    ← Nicht gewusst    ·    Gewusst →",
            empty: "Keine Karten für diese Sprache vorhanden.",
            loadError: "Konnte flip-cards.json nicht laden. Bitte die Seite über einen Webserver öffnen (nicht direkt per file://).",
            status: (n, lang, idx, ok, bad) => `${n} Karten · ${lang.toUpperCase()} · Index ${idx} · ✓ ${ok} / ✗ ${bad}`
        },
        en: {
            question: "Question", answer: "Answer",
            domain: "Domain",
            reveal: "Reveal answer (Space)",
            conceal: "Show question (Space)",
            know: "✓ Knew it", dontKnow: "✗ Didn't know",
            reset: "Reset",
            filterTitle: "Areas",
            resetConfirm: "Really reset learning progress for this language?",
            hintReveal: "Press Space to reveal",
            hintDecide: "Space to return to question    ·    ← Didn't know    ·    Knew it →",
            empty: "No cards available for this language.",
            loadError: "Could not load flip-cards.json. Please open this page through a web server (not directly via file://).",
            status: (n, lang, idx, ok, bad) => `${n} cards · ${lang.toUpperCase()} · index ${idx} · ✓ ${ok} / ✗ ${bad}`
        }
    };

    /**
     * Persists the per-id "index" values and the language choice in localStorage.
     * The index is shared across languages (keyed by id).
     */
    class CardStore {
        static INDEX_KEY = "flipcards.indices";
        static LANG_KEY = "flipcards.language";
        static AREAS_KEY = "flipcards.areas";

        constructor() {
            this.indices = this._read();
        }

        _read() {
            try { return JSON.parse(localStorage.getItem(CardStore.INDEX_KEY)) || {}; }
            catch { return {}; }
        }

        _write() {
            try { localStorage.setItem(CardStore.INDEX_KEY, JSON.stringify(this.indices)); }
            catch { /* localStorage disabled – keep in-memory only */ }
        }

        /**
         * Reconciles stored indices with the ids currently present:
         * - Empty store: sort ids ascending, assign index 0..n-1.
         * - New ids: get higher indices than any existing → drawn most likely.
         * - Removed ids: pruned.
         */
        sync(ids) {
            const idSet = new Set(ids);
            for (const key of Object.keys(this.indices)) {
                if (!idSet.has(Number(key))) delete this.indices[key];
            }
            const missing = [...idSet].filter((id) => !(id in this.indices)).sort((a, b) => a - b);
            if (missing.length) {
                const values = Object.values(this.indices);
                let next = values.length ? Math.max(...values) + 1 : 0;
                for (const id of missing) this.indices[id] = next++;
            }
            this._write();
        }

        getIndex(id) { return this.indices[id]; }

        /** Shifts a card by {delta} (negative = lower draw weight). */
        adjustIndex(id, delta) {
            if (id in this.indices) { this.indices[id] += delta; this._write(); }
        }

        /** Clears only the given ids (language-scoped reset). */
        resetIds(ids) {
            for (const id of ids) delete this.indices[id];
            this._write();
        }

        getLanguage() {
            try { return localStorage.getItem(CardStore.LANG_KEY); }
            catch { return null; }
        }

        setLanguage(lang) {
            try { localStorage.setItem(CardStore.LANG_KEY, lang); } catch { /* ignore */ }
        }

        /** Selected areas as a { de: [...], en: [...] } map. */
        getAreas() {
            try { return JSON.parse(localStorage.getItem(CardStore.AREAS_KEY)) || {}; }
            catch { return {}; }
        }

        setAreas(map) {
            try { localStorage.setItem(CardStore.AREAS_KEY, JSON.stringify(map)); }
            catch { /* ignore */ }
        }
    }

    /**
     * Detached debug overlay (right edge, toggled bottom-right, hidden by default).
     * Renders the active deck ordered by index as a probability bar chart and a
     * ranked list, so the ordering algorithm can be inspected live.
     */
    class DebugPanel {
        constructor() {
            this.open = false;
            this.el = {
                panel: document.getElementById("flip-debug"),
                toggle: document.getElementById("flip-debug-toggle"),
                meta: document.getElementById("flip-debug-meta"),
                chart: document.getElementById("flip-debug-chart"),
                list: document.getElementById("flip-debug-list")
            };
            if (this.el.toggle) this.el.toggle.addEventListener("click", () => this.toggle());
        }

        toggle(force) {
            if (!this.el.panel) return;
            this.open = typeof force === "boolean" ? force : !this.open;
            this.el.panel.classList.toggle("is-open", this.open);
            this.el.panel.setAttribute("aria-hidden", String(!this.open));
            this.el.toggle.classList.toggle("is-open", this.open);
            this.el.toggle.setAttribute("aria-expanded", String(this.open));
            this.el.toggle.textContent = this.open ? "✕" : "⚙";
        }

        /** items: [{ pos, id, index, prob, area, topic, isCurrent }] sorted most-likely first. */
        render(items, meta) {
            if (!this.el.panel) return;

            const areasTxt = meta.areas.length ? meta.areas.join(", ") : "alle";
            this.el.meta.textContent = `${meta.lang.toUpperCase()} · ${meta.count} Karten · Bereiche: ${areasTxt}`;

            // Bar chart – heights relative to the most likely card.
            this.el.chart.textContent = "";
            const max = items.length ? items[0].prob : 1;
            for (const it of items) {
                const col = document.createElement("div");
                col.className = "flip-debug__col";
                col.title = `#${it.id} · idx ${it.index} · ${(it.prob * 100).toFixed(1)}%`;

                const plot = document.createElement("div");
                plot.className = "flip-debug__plot";
                const bar = document.createElement("div");
                bar.className = "flip-debug__bar" + (it.isCurrent ? " is-current" : "");
                bar.style.height = (max ? it.prob / max * 100 : 0).toFixed(1) + "%";
                plot.appendChild(bar);

                const id = document.createElement("span");
                id.className = "flip-debug__bar-id";
                id.textContent = it.id;

                col.append(plot, id);
                this.el.chart.appendChild(col);
            }

            // Ranked list – most likely next at the top.
            this.el.list.textContent = "";
            for (const it of items) {
                const li = document.createElement("li");
                li.className = "flip-debug__row" + (it.isCurrent ? " is-current" : "");

                const pos = document.createElement("span");
                pos.className = "flip-debug__pos";
                pos.textContent = "#" + it.pos;

                const prob = document.createElement("span");
                prob.className = "flip-debug__prob";
                prob.textContent = (it.prob * 100).toFixed(1) + "%";

                const main = document.createElement("div");
                main.className = "flip-debug__main";
                const topic = document.createElement("span");
                topic.className = "flip-debug__topic";
                topic.textContent = (it.isCurrent ? "● " : "") + (it.topic || "#" + it.id);
                const sub = document.createElement("span");
                sub.className = "flip-debug__sub";
                sub.textContent = `id ${it.id} · idx ${it.index} · ${it.area || "—"}`;
                main.append(topic, sub);

                li.append(pos, prob, main);
                this.el.list.appendChild(li);
            }
        }
    }

    /** Holds the cards and drives selection, reveal and scoring. */
    class FlipCardApp {
        static KNOWN_STEP = 10;

        constructor() {
            this.store = new CardStore();
            this.cards = [];   // all cards from the JSON
            this.active = [];  // filtered by language
            this.current = null;
            this.revealed = false;
            this.session = { ok: 0, bad: 0 };

            const storedLang = this.store.getLanguage();
            this.lang = storedLang || FlipCardApp.detectBrowserLanguage();
            if (!storedLang) this.store.setLanguage(this.lang);
            this.areaSel = this.store.getAreas(); // { de: [...], en: [...] }

            this._cacheDom();
            this._bindEvents();
            this.debug = new DebugPanel();
        }

        _cacheDom() {
            this.el = {
                message: document.getElementById("flip-message"),
                card: document.getElementById("flip-card"),
                actions: document.getElementById("flip-actions"),
                tagQ: document.getElementById("flip-tag-q"),
                tagA: document.getElementById("flip-tag-a"),
                question: document.getElementById("flip-question"),
                answer: document.getElementById("flip-answer"),
                reveal: document.getElementById("flip-reveal"),
                decision: document.getElementById("flip-decision"),
                know: document.getElementById("flip-know"),
                dontKnow: document.getElementById("flip-dont-know"),
                hint: document.getElementById("flip-hint"),
                status: document.getElementById("flip-status"),
                resetLabel: document.getElementById("flip-reset-label"),
                reset: document.getElementById("flip-reset"),
                filterTitle: document.getElementById("flip-filter-title"),
                filterList: document.getElementById("flip-filter-list"),
                langButtons: [...document.querySelectorAll(".flip-langs button")]
            };
        }

        static detectBrowserLanguage() {
            const langs = Array.isArray(navigator.languages) && navigator.languages.length
                ? navigator.languages
                : [navigator.language || "de"];

            for (const lang of langs) {
                if (String(lang).toLowerCase().startsWith("de")) return "de";
                if (String(lang).toLowerCase().startsWith("en")) return "en";
            }

            return "en";
        }

        _bindEvents() {
            this.el.reveal.addEventListener("click", () => this.toggleReveal());
            this.el.card.addEventListener("click", () => this.toggleReveal());
            this.el.know.addEventListener("click", () => this.decide(true));
            this.el.dontKnow.addEventListener("click", () => this.decide(false));
            this.el.reset.addEventListener("click", () => this.resetProgress());
            this.el.langButtons.forEach((btn) =>
                btn.addEventListener("click", () => this.setLanguage(btn.dataset.lang)));

            document.addEventListener("keydown", (e) => {
                if (e.code === "Space" && this.current) {
                    e.preventDefault();
                    this.toggleReveal();
                } else if (this.revealed && e.code === "ArrowRight") {
                    this.decide(true);
                } else if (this.revealed && e.code === "ArrowLeft") {
                    this.decide(false);
                }
            });
        }

        /** Loads the JSON file and starts the quiz. */
        async init() {
            try {
                const res = await fetch("flip-cards.json", { cache: "no-store" });
                if (!res.ok) throw new Error(res.status);
                this.cards = await res.json();
            } catch {
                this._applyStaticTexts();
                this._showMessage(I18N[this.lang].loadError);
                return;
            }
            const ids = [...new Set(this.cards.map((c) => Number(c.id)))];
            this.store.sync(ids);
            this._applyStaticTexts();
            this.renderAreaFilter();
            this.rebuild();
        }

        /** Filters by language and shows the first card. */
        rebuild() {
            const areas = new Set(this.areaSel[this.lang] || []);
            this.active = this.cards
                .filter((c) => c.language === this.lang)
                .filter((c) => areas.size === 0 || areas.has(c.area))
                .map((c) => ({ ...c, id: Number(c.id) }));

            this.el.langButtons.forEach((b) =>
                b.setAttribute("aria-pressed", String(b.dataset.lang === this.lang)));

            this._refreshDebug();

            if (this.active.length === 0) {
                this._showMessage(I18N[this.lang].empty);
                return;
            }
            this.el.message.classList.add("flip-hidden");
            this.el.card.classList.remove("flip-hidden");
            this.el.actions.classList.remove("flip-hidden");
            this.nextCard(true);
        }

        /** Picks the next card using index-derived weights. */
        nextCard(instant = false) {
            const selection = this._selectionModel();
            const items = selection.items;

            let pick = items[0].card;
            for (let attempt = 0; attempt < 6; attempt++) {
                const roll = Math.random() * selection.totalWeight;
                const selected = items.find((it) => roll < it.cumulativeWeight) || items[items.length - 1];
                pick = selected.card;
                if (items.length === 1 || !this.current || pick.id !== this.current.id) break;
            }

            const render = () => {
                this.current = pick;
                this.revealed = false;
                this.el.card.classList.remove("is-flipped");
                this.el.question.textContent = pick.question;
                this.el.answer.textContent = pick.answer;
                const domain = pick.area ? ` · ${I18N[this.lang].domain}: ${pick.area}` : "";
                this.el.tagQ.textContent = `${I18N[this.lang].question}${domain}`;
                this.el.tagA.textContent = `${I18N[this.lang].answer}${domain}`;
                this._syncRevealUi();
                this.el.card.scrollTop = 0;
                this._updateStatus();
                this._refreshDebug();
                this.el.card.classList.remove("is-swapping");
            };

            if (instant) { render(); return; }
            // Soft swap: fade out → swap content → fade in (no answer spoiler).
            this.el.card.classList.add("is-swapping");
            setTimeout(render, 180);
        }

        /** Builds the weighted draw model from the current active deck. */
        _selectionModel() {
            const indexed = this.active.map((card) => {
                const index = Number(this.store.getIndex(card.id));
                return { card, index: Number.isFinite(index) ? index : 0 };
            }).sort((a, b) => a.index - b.index || a.card.id - b.card.id);

            const minIndex = indexed.length ? indexed[0].index : 0;
            const items = indexed.map((it) => ({
                ...it,
                weight: Math.max(1, it.index - minIndex + 1)
            }));
            const totalWeight = items.reduce((sum, it) => sum + it.weight, 0) || 1;

            let cumulativeWeight = 0;
            for (const it of items) {
                cumulativeWeight += it.weight;
                it.cumulativeWeight = cumulativeWeight;
                it.prob = it.weight / totalWeight;
            }

            return { items, totalWeight };
        }

        /** Toggles between question and answer. */
        toggleReveal(force) {
            if (!this.current) return;

            const reveal = typeof force === "boolean" ? force : !this.revealed;
            this.revealed = reveal;
            this.el.card.classList.toggle("is-flipped", reveal);
            this._syncRevealUi();
        }

        _syncRevealUi() {
            const t = I18N[this.lang];
            this.el.reveal.classList.remove("flip-hidden");
            this.el.reveal.textContent = this.revealed ? t.conceal : t.reveal;
            this.el.decision.classList.toggle("flip-hidden", !this.revealed);
            this.el.hint.textContent = this.revealed ? t.hintDecide : t.hintReveal;
        }

        /** Scores the current card and loads the next one. */
        decide(known) {
            if (!this.revealed || !this.current) return;
            if (known) {
                this.session.ok++;
                this.store.adjustIndex(this.current.id, -FlipCardApp.KNOWN_STEP);
            } else {
                this.session.bad++;
                this.store.adjustIndex(this.current.id, FlipCardApp.KNOWN_STEP);
            }
            this.nextCard();
        }

        setLanguage(lang) {
            if (lang === this.lang || !I18N[lang]) return;
            this.lang = lang;
            this.store.setLanguage(lang);
            this.current = null;
            this._applyStaticTexts();
            this.renderAreaFilter();
            this.rebuild();
        }

        resetProgress() {
            if (!window.confirm(I18N[this.lang].resetConfirm)) return;
            this.store.resetIds(this.active.map((c) => c.id));
            const ids = [...new Set(this.cards.map((c) => Number(c.id)))];
            this.store.sync(ids);
            this.session = { ok: 0, bad: 0 };
            this.current = null;
            this.nextCard(true);
        }

        /** Distinct areas (with card counts) available for a language, sorted by name. */
        _areasForLang(lang) {
            const counts = new Map();
            for (const c of this.cards) {
                if (c.language !== lang || !c.area) continue;
                counts.set(c.area, (counts.get(c.area) || 0) + 1);
            }
            return [...counts.entries()].sort((a, b) => a[0].localeCompare(b[0]));
        }

        /** (Re)builds the area checkboxes for the current language. */
        renderAreaFilter() {
            const list = this.el.filterList;
            if (!list) return;
            const selected = new Set(this.areaSel[this.lang] || []);
            list.textContent = "";

            for (const [area, count] of this._areasForLang(this.lang)) {
                const label = document.createElement("label");
                label.className = "flip-filter__item";

                const input = document.createElement("input");
                input.type = "checkbox";
                input.value = area;
                input.checked = selected.has(area);
                input.addEventListener("change", () => this._onAreaToggle(area, input.checked));

                const name = document.createElement("span");
                name.className = "flip-filter__name";
                name.textContent = area;

                const badge = document.createElement("span");
                badge.className = "flip-filter__count";
                badge.textContent = count;

                label.append(input, name, badge);
                list.appendChild(label);
            }
        }

        /** Adds/removes an area from the current language's selection and reloads. */
        _onAreaToggle(area, checked) {
            const current = new Set(this.areaSel[this.lang] || []);
            if (checked) current.add(area); else current.delete(area);
            this.areaSel[this.lang] = [...current];
            this.store.setAreas(this.areaSel);
            this.current = null;
            this.rebuild();
        }

        /** Sets all language-dependent static labels. */
        _applyStaticTexts() {
            const t = I18N[this.lang];
            this.el.tagQ.textContent = t.question;
            this.el.tagA.textContent = t.answer;
            this.el.know.textContent = t.know;
            this.el.dontKnow.textContent = t.dontKnow;
            this.el.resetLabel.textContent = t.reset;
            this._syncRevealUi();
            if (this.el.filterTitle) this.el.filterTitle.textContent = t.filterTitle;
        }

        _updateStatus() {
            const t = I18N[this.lang];
            this.el.status.textContent = t.status(
                this.active.length, this.lang, this.store.getIndex(this.current.id),
                this.session.ok, this.session.bad);
        }

        /** Builds the debug view with the actual draw probability per card. */
        _debugView() {
            const selection = this._selectionModel();
            const items = selection.items.map((it) => ({
                id: it.card.id,
                index: it.index,
                prob: it.prob,
                area: it.card.area,
                topic: it.card.topic
            })).sort((a, b) => b.prob - a.prob || b.index - a.index || a.id - b.id);
            items.forEach((it, i) => {
                it.pos = i + 1;
                it.isCurrent = !!(this.current && this.current.id === it.id);
            });
            return { items, meta: { lang: this.lang, count: selection.items.length, areas: this.areaSel[this.lang] || [] } };
        }

        _refreshDebug() {
            if (!this.debug) return;
            const { items, meta } = this._debugView();
            this.debug.render(items, meta);
        }

        _showMessage(text) {
            this.el.message.textContent = text;
            this.el.message.classList.remove("flip-hidden");
            this.el.card.classList.add("flip-hidden");
            this.el.actions.classList.add("flip-hidden");
        }
    }

    const start = () => new FlipCardApp().init();
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        start();
    }
})();
