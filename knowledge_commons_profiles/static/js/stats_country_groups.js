/*
 * "Members by Region or Group" section of the stats dashboard.
 *
 * The server embeds every group's breakdown as JSON (#country_group_data),
 * so switching groups in the dropdown re-renders the table locally without
 * another request.
 */
(function () {
  "use strict";

  function readGroups() {
    var element = document.getElementById("country_group_data");
    if (!element) {
      return [];
    }
    try {
      return JSON.parse(element.textContent) || [];
    } catch (error) {
      return [];
    }
  }

  function formatNumber(value) {
    try {
      return new Intl.NumberFormat().format(value);
    } catch (error) {
      return String(value);
    }
  }

  function formatPercent(part, whole) {
    if (!whole) {
      return "0%";
    }
    var share = (part / whole) * 100;
    return (share < 10 ? share.toFixed(1) : Math.round(share)) + "%";
  }

  function cell(className, text) {
    var td = document.createElement("td");
    if (className) {
      td.className = className;
    }
    if (text !== undefined) {
      td.textContent = text;
    }
    return td;
  }

  function countryCell(country) {
    var td = cell("text-sm font-weight-bold");
    td.appendChild(document.createTextNode(country.name));
    var code = document.createElement("span");
    code.className = "country-code";
    code.textContent = country.code;
    td.appendChild(code);
    return td;
  }

  function shareCell(count, total) {
    var td = cell("country-share");
    var wrapper = document.createElement("div");
    wrapper.className = "d-flex align-items-center gap-2";

    var progress = document.createElement("div");
    progress.className = "progress";
    progress.setAttribute("role", "progressbar");
    progress.setAttribute("aria-valuemin", "0");
    progress.setAttribute("aria-valuemax", "100");
    var share = total ? (count / total) * 100 : 0;
    progress.setAttribute("aria-valuenow", share.toFixed(1));

    var bar = document.createElement("div");
    bar.className = "progress-bar";
    bar.style.width = share.toFixed(2) + "%";
    progress.appendChild(bar);

    var value = document.createElement("span");
    value.className = "share-value";
    value.textContent = formatPercent(count, total);

    wrapper.appendChild(progress);
    wrapper.appendChild(value);
    td.appendChild(wrapper);
    return td;
  }

  function render(group, allTotal, elements) {
    var rows = elements.rows;
    while (rows.firstChild) {
      rows.removeChild(rows.firstChild);
    }

    group.countries.forEach(function (country, index) {
      var tr = document.createElement("tr");
      tr.appendChild(cell("country-rank text-sm", String(index + 1)));
      tr.appendChild(countryCell(country));
      tr.appendChild(cell("country-members text-sm", formatNumber(country.count)));
      tr.appendChild(shareCell(country.count, group.total));
      rows.appendChild(tr);
    });

    elements.total.textContent = formatNumber(group.total);
    if (elements.totalLabel) {
      elements.totalLabel.textContent = group.name;
    }
    elements.represented.textContent =
      formatNumber(group.countries.length) + " of " + formatNumber(group.size);
    elements.share.textContent = formatPercent(group.total, allTotal);

    var empty = group.countries.length === 0;
    elements.tableContainer.hidden = empty;
    elements.empty.hidden = !empty;
  }

  document.addEventListener("DOMContentLoaded", function () {
    var select = document.getElementById("country_group_select");
    var elements = {
      rows: document.getElementById("country_group_rows"),
      total: document.getElementById("country_group_total"),
      totalLabel: document.getElementById("country_group_total_label"),
      represented: document.getElementById("country_group_represented"),
      share: document.getElementById("country_group_share"),
      tableContainer: document.getElementById("country_group_table_cont"),
      empty: document.getElementById("country_group_empty")
    };

    if (!select || !elements.rows) {
      return;
    }

    var groups = readGroups();
    var byName = {};
    var allTotal = 0;
    groups.forEach(function (group) {
      byName[group.name] = group;
      if (group.total > allTotal) {
        allTotal = group.total;
      }
    });

    function show() {
      var group = byName[select.value];
      if (group) {
        render(group, allTotal, elements);
      }
    }

    select.addEventListener("change", show);
    show();
  });
})();
