// --- Theme toggle (light / dark). Default is the light theme. ---
(function () {
    var root = document.documentElement;
    function isDark() { return root.getAttribute('data-theme') === 'dark'; }
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'theme-toggle';
    btn.setAttribute('aria-label', 'Toggle dark mode');
    function render() {
        var dark = isDark();
        btn.textContent = dark ? '☀️' : '🌙';
        btn.title = dark ? 'Switch to light theme' : 'Switch to dark theme';
        btn.setAttribute('aria-pressed', dark ? 'true' : 'false');
    }
    function apply(dark) {
        if (dark) { root.setAttribute('data-theme', 'dark'); }
        else { root.removeAttribute('data-theme'); }
        try { localStorage.setItem('theme', dark ? 'dark' : 'light'); } catch (e) {}
        render();
    }
    btn.addEventListener('click', function () { apply(!isDark()); });
    (document.body || root).appendChild(btn);
    render();
})();

const loc = window.location.href;
if (loc.startsWith('http://') && !loc.includes('localhost') && !loc.includes('127.0.0.1')) {
    window.location.href = loc.replace('http://', 'https://');
}

// DataTables configuration (only when jQuery is present on the page)
if (window.jQuery) $(document).ready(function () {
    function isResponsiveLayout() {
        const aside = $('#aside-first');
        const content = $('#layout-content');
        if (aside.length && content.length) {
            const asideRect = aside[0].getBoundingClientRect();
            const contentRect = content[0].getBoundingClientRect();
            // If aside is above content (smaller top position), we're in responsive layout
            return asideRect.top < contentRect.top && window.innerWidth <= 768;
        }
        return window.innerWidth <= 768; // Fallback to screen width check
    }

    // Small delay to ensure layout is settled
    setTimeout(function () {
        if (isResponsiveLayout()) {
            const projectsHeading = document.getElementById('heading');
            if (projectsHeading) {
                projectsHeading.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }
    }, 100);

    // Initialize DataTables for all tables - Compatible with DataTables 2.0 and jQuery 4.0
    // Check if DataTable plugin is available before using it
    if ($.fn.DataTable && $('table.gradienttable').length > 0) {
        $('table.gradienttable').each(function () {
            // Initialize each table individually and resolve the date column by header text
            // so sorting works for different table layouts (e.g. articles vs. mooc tables).
            var headers = $(this).find('thead tr:first th');
            var dateColumnIndex = -1;
            headers.each(function (index) {
                var headerText = ($(this).text() || '').trim().toLowerCase();
                if (headerText === 'date' || headerText === 'datum') {
                    dateColumnIndex = index;
                }
            });
            var hasDateColumn = dateColumnIndex >= 0;

            var options = {
                responsive: true,
                paging: false,
                language: {
                    search: 'Filter:',
                    lengthMenu: 'Show _MENU_ entries per page',
                    info: 'Showing _START_ to _END_ of _TOTAL_ rows',
                    paginate: {
                        first: 'First',
                        last: 'Last',
                        next: 'Next',
                        previous: 'Previous'
                    }
                }
            };

            if (hasDateColumn) {
                options.order = [[dateColumnIndex, 'desc']]; // Sort by date column (newest first)
                options.columnDefs = [
                    {
                        // Date is the primary sort key: highest responsive priority so it is
                        // never collapsed into the expandable child row on narrow layouts.
                        targets: [dateColumnIndex],
                        type: 'date',
                        responsivePriority: 1
                    },
                    {
                        // Title is next; let the wider Platform/Provider columns collapse first.
                        targets: 0,
                        responsivePriority: 2
                    }
                ];
            }

            $(this).DataTable(options);
        });
    }
});