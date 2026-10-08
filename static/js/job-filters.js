/* =========================================================
   REUSABLE JOB FILTERS - drawer open/close + domain->subdomain
   dependency. Used on jobs/job_list.html (components/job_filters.html).
========================================================== */

(function () {

    var sidebar = document.getElementById("jobFilterSidebar");
    var toggle = document.querySelector("[data-filter-toggle]");
    var overlay = document.querySelector("[data-filter-overlay]");
    var closeButtons = document.querySelectorAll("[data-filter-close]");

    function openDrawer() {
        if (!sidebar) return;
        sidebar.classList.add("is-open");
        if (overlay) {
            overlay.hidden = false;
            overlay.classList.add("is-open");
        }
        if (toggle) toggle.setAttribute("aria-expanded", "true");
        document.body.classList.add("nc-filter-drawer-open");
    }

    function closeDrawer() {
        if (!sidebar) return;
        sidebar.classList.remove("is-open");
        if (overlay) {
            overlay.classList.remove("is-open");
            overlay.hidden = true;
        }
        if (toggle) toggle.setAttribute("aria-expanded", "false");
        document.body.classList.remove("nc-filter-drawer-open");
    }

    if (toggle && sidebar) {
        toggle.addEventListener("click", function () {
            if (sidebar.classList.contains("is-open")) {
                closeDrawer();
            } else {
                openDrawer();
            }
        });
    }

    if (overlay) {
        overlay.addEventListener("click", closeDrawer);
    }

    closeButtons.forEach(function (btn) {
        btn.addEventListener("click", closeDrawer);
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            closeDrawer();
        }
    });

    /* =====================================================
       DOMAIN -> SUBDOMAIN DEPENDENCY

       The subdomain <select> only ever shows options belonging to
       the selected domain (server-side validation still applies -
       see JobSearchForm.clean() - this is just the UI convenience).
    ===================================================== */

    var domainSelect = document.getElementById("id_search_domain");
    var subdomainSelect = document.getElementById("id_search_subdomain");

    if (domainSelect && subdomainSelect) {
        var allOptions = Array.prototype.slice.call(subdomainSelect.options);

        var applyFilter = function (preserveSelection) {
            var domainValue = domainSelect.value;
            var previousValue = subdomainSelect.value;
            subdomainSelect.innerHTML = "";
            allOptions.forEach(function (option) {
                var optionDomain = option.getAttribute("data-domain");
                if (!option.value || !domainValue || optionDomain === domainValue) {
                    subdomainSelect.appendChild(option);
                }
            });
            if (
                preserveSelection &&
                Array.prototype.some.call(subdomainSelect.options, function (o) {
                    return o.value === previousValue;
                })
            ) {
                subdomainSelect.value = previousValue;
            }
        };

        applyFilter(true);
        domainSelect.addEventListener("change", function () {
            applyFilter(false);
        });
    }

})();
