/*
 * Participation map for the stats dashboard.
 *
 * The tile server is configured through data attributes on the #map_stats
 * element (see STATS_MAP_TILE_* settings) rather than being hardcoded, as
 * the OpenStreetMap tile usage policy requests. Tile requests opt back in
 * to sending a Referer header because the site's default Referrer-Policy
 * (same-origin) would otherwise strip it, which OSM treats as a policy
 * violation. If the tile server refuses to serve tiles, the map is replaced
 * with a short message instead of a grid of error tiles.
 */
(function () {
  "use strict";

  var REFERRER_POLICY = "strict-origin-when-cross-origin";
  var TILE_ERROR_THRESHOLD = 3;

  function tileUrlFor(template, z, x, y) {
    return template
      .replace("{z}", z)
      .replace("{x}", x)
      .replace("{y}", y)
      .replace("{s}", "a");
  }

  function showUnavailable(container, fallback) {
    container.hidden = true;
    fallback.hidden = false;
  }

  /*
   * Ask the tile server for a single tile and decide whether it is willing
   * to serve us. OSM answers policy violations with an HTTP 200 "blocked"
   * image marked Cache-Control: no-cache, whereas real tiles carry a
   * max-age (the policy requires tiles to be cacheable for at least seven
   * days), so a no-cache answer is treated as a refusal too.
   */
  function probeTileServer(template) {
    if (typeof fetch !== "function") {
      return Promise.resolve(true);
    }

    return fetch(tileUrlFor(template, 0, 0, 0), {
      method: "GET",
      mode: "cors",
      referrerPolicy: REFERRER_POLICY,
    })
      .then(function (response) {
        if (!response.ok) {
          return false;
        }

        var cacheControl = (
          response.headers.get("Cache-Control") || ""
        ).toLowerCase();

        return (
          cacheControl.indexOf("no-cache") === -1 &&
          cacheControl.indexOf("no-store") === -1
        );
      })
      .catch(function () {
        return false;
      });
  }

  function addPoints(map, points) {
    Object.keys(points).forEach(function (institution) {
      var values = points[institution];

      L.circle([values[0], values[1]], {
        color: "red",
        fillColor: "#f03",
        fillOpacity: 0.5,
        radius: values[2],
      })
        .addTo(map)
        .bindPopup(institution);
    });
  }

  function initMap(container, fallback, config, points) {
    var map = L.map(container).setView([0, 0], 2);
    var tileErrors = 0;
    var tileLoaded = false;

    var layer = L.tileLayer(config.url, {
      maxZoom: config.maxZoom,
      attribution: config.attribution,
      referrerPolicy: REFERRER_POLICY,
    });

    layer.on("tileload", function () {
      tileLoaded = true;
    });

    layer.on("tileerror", function () {
      tileErrors += 1;

      if (!tileLoaded && tileErrors >= TILE_ERROR_THRESHOLD) {
        map.remove();
        showUnavailable(container, fallback);
      }
    });

    layer.addTo(map);
    addPoints(map, points);
  }

  function readPoints() {
    var dataElement = document.getElementById("map_stats_data");

    if (!dataElement) {
      return {};
    }

    try {
      return JSON.parse(dataElement.textContent) || {};
    } catch (error) {
      return {};
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var container = document.getElementById("map_stats");
    var fallback = document.getElementById("map_stats_unavailable");

    if (!container || !fallback) {
      return;
    }

    var config = {
      url: container.dataset.tileUrl,
      attribution: container.dataset.tileAttribution || "",
      maxZoom: parseInt(container.dataset.tileMaxZoom, 10) || 19,
    };

    if (typeof L === "undefined" || !config.url) {
      showUnavailable(container, fallback);
      return;
    }

    probeTileServer(config.url).then(function (available) {
      if (!available) {
        showUnavailable(container, fallback);
        return;
      }

      initMap(container, fallback, config, readPoints());
    });
  });
})();
