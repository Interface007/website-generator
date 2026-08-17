/**
 * Progressive-enhancement language filter for the articles overview page.
 *
 * The C# generator renders a segmented control (#article-lang-filter) that is `hidden`
 * by default, so without JavaScript every article stays visible. This script reveals the
 * control and wires it up. The overview table is a DataTable (see mooc.js), so filtering
 * is done through a DataTables custom search plugin; a plain row-toggle fallback covers the
 * (unexpected) case where DataTables is not present.
 *
 * Default filter on first visit = browser language; the choice is persisted in localStorage.
 */
(function () {
    'use strict';

    var STORAGE_KEY = 'articleLangFilter';
    var VALID = { all: true, de: true, en: true };

    // "de-DE" / "en-US" -> "de" / "en"
    function normalizeLang(value) {
        return (value || '').trim().slice(0, 2).toLowerCase();
    }

    function initialFilter() {
        try {
            var stored = localStorage.getItem(STORAGE_KEY);
            if (VALID[stored]) {
                return stored;
            }
        } catch (e) { /* localStorage unavailable (private mode) */ }
        return (navigator.language || 'en').toLowerCase().indexOf('de') === 0 ? 'de' : 'en';
    }

    // Resolve the "Language"/"Sprache" column by header text; fall back to the last column.
    function findLangColumnIndex(table) {
        var headers = table.querySelectorAll('thead tr:first-child th');
        for (var i = 0; i < headers.length; i++) {
            var text = (headers[i].textContent || '').trim().toLowerCase();
            if (text === 'language' || text === 'sprache') {
                return i;
            }
        }
        return headers.length ? headers.length - 1 : 0;
    }

    function init() {
        var container = document.getElementById('article-lang-filter');
        if (!container) {
            return; // present on the articles overview only
        }
        var table = document.querySelector('table.gradienttable');
        if (!table) {
            return;
        }

        var buttons = container.querySelectorAll('.lang-filter__btn');
        var countEl = document.getElementById('article-lang-count');
        var colIndex = findLangColumnIndex(table);
        var current = initialFilter();

        var jq = window.jQuery;
        var dt = (jq && jq.fn && jq.fn.dataTable && jq.fn.dataTable.isDataTable(table))
            ? jq(table).DataTable()
            : null;

        if (dt) {
            // Scoped to this table so other DataTables on the site are unaffected.
            jq.fn.dataTable.ext.search.push(function (settings, data) {
                if (settings.nTable !== table) {
                    return true;
                }
                return current === 'all' || normalizeLang(data[colIndex]) === current;
            });
        }

        function announce(n) {
            if (countEl) {
                countEl.textContent = n + (n === 1 ? ' article' : ' articles');
            }
        }

        function applyFallback() {
            var rows = table.querySelectorAll('tbody tr');
            var visible = 0;
            for (var i = 0; i < rows.length; i++) {
                var cell = rows[i].children[colIndex];
                var match = current === 'all' || normalizeLang(cell ? cell.textContent : '') === current;
                rows[i].hidden = !match;
                if (match) {
                    visible++;
                }
            }
            return visible;
        }

        function apply(lang) {
            current = VALID[lang] ? lang : 'all';
            try {
                localStorage.setItem(STORAGE_KEY, current);
            } catch (e) { /* ignore */ }

            for (var i = 0; i < buttons.length; i++) {
                buttons[i].setAttribute(
                    'aria-pressed',
                    buttons[i].getAttribute('data-lang') === current ? 'true' : 'false');
            }

            if (dt) {
                dt.draw();
                announce(dt.rows({ search: 'applied' }).count());
            } else {
                announce(applyFallback());
            }
        }

        for (var b = 0; b < buttons.length; b++) {
            buttons[b].addEventListener('click', function () {
                apply(this.getAttribute('data-lang'));
            });
        }

        container.hidden = false; // JS active: expose the control
        apply(current);
    }

    // Run after mooc.js has initialised the DataTable (both are ready-scoped, in load order).
    if (window.jQuery) {
        window.jQuery(function () { init(); });
    } else if (document.readyState !== 'loading') {
        init();
    } else {
        document.addEventListener('DOMContentLoaded', init);
    }
})();
