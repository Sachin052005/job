/* =========================================================
   ACTIVITY OVERVIEW CHART (Student Profile Performance)

   A small vanilla-JS multi-series SVG line chart with a hover/touch
   tooltip. No charting library - consistent with the rest of the app.
   Reads its data from a <script type="application/json"> tag rendered
   by Django's json_script filter (real, server-computed numbers only).
========================================================== */

(function () {

    function renderActivityChart(root) {
        var sourceId = root.getAttribute("data-chart-source");
        var dataScript = sourceId ? document.getElementById(sourceId) : null;
        if (!dataScript) return;

        var payload;
        try {
            payload = JSON.parse(dataScript.textContent);
        } catch (e) {
            return;
        }

        var labels = payload.labels || [];
        var tooltipLabels = payload.tooltipLabels || labels;
        var series = payload.series || [];
        if (!labels.length || !series.length) return;

        var width = Math.max(root.clientWidth || 600, 260);
        var height = 220;
        var paddingLeft = 34;
        var paddingRight = 12;
        var paddingTop = 16;
        var paddingBottom = 26;

        var maxValue = 0;
        series.forEach(function (s) {
            s.data.forEach(function (v) {
                if (v > maxValue) maxValue = v;
            });
        });
        var niceMax = maxValue <= 4 ? 4 : Math.ceil(maxValue / 4) * 4;

        var innerWidth = width - paddingLeft - paddingRight;
        var innerHeight = height - paddingTop - paddingBottom;
        var stepX = labels.length > 1 ? innerWidth / (labels.length - 1) : 0;

        function xFor(i) { return paddingLeft + stepX * i; }
        function yFor(v) { return paddingTop + innerHeight - (v / niceMax) * innerHeight; }

        var svgNS = "http://www.w3.org/2000/svg";
        var svg = document.createElementNS(svgNS, "svg");
        svg.setAttribute("viewBox", "0 0 " + width + " " + height);
        svg.setAttribute("width", "100%");
        svg.setAttribute("height", height);
        svg.setAttribute("aria-hidden", "true");
        svg.setAttribute("focusable", "false");

        [0, 0.5, 1].forEach(function (fraction) {
            var value = Math.round(niceMax * fraction);
            var y = yFor(value);

            var line = document.createElementNS(svgNS, "line");
            line.setAttribute("x1", paddingLeft);
            line.setAttribute("x2", width - paddingRight);
            line.setAttribute("y1", y);
            line.setAttribute("y2", y);
            line.setAttribute("stroke", "#e1e8e4");
            line.setAttribute("stroke-width", "1");
            svg.appendChild(line);

            var text = document.createElementNS(svgNS, "text");
            text.setAttribute("x", 2);
            text.setAttribute("y", y + 3);
            text.setAttribute("font-size", "10");
            text.setAttribute("fill", "#8994a3");
            text.textContent = String(value);
            svg.appendChild(text);
        });

        var labelIndexes = labels.length <= 8
            ? labels.map(function (_, i) { return i; })
            : [0, Math.floor((labels.length - 1) / 2), labels.length - 1];

        labelIndexes.forEach(function (i) {
            var text = document.createElementNS(svgNS, "text");
            text.setAttribute("x", xFor(i));
            text.setAttribute("y", height - 8);
            text.setAttribute("font-size", "10");
            text.setAttribute("fill", "#8994a3");
            text.setAttribute(
                "text-anchor",
                i === 0 ? "start" : (i === labels.length - 1 ? "end" : "middle")
            );
            text.textContent = labels[i];
            svg.appendChild(text);
        });

        var pointGroups = series.map(function (s) {
            var points = s.data.map(function (v, i) {
                return xFor(i) + "," + yFor(v);
            }).join(" ");

            if (s.data.length > 1) {
                var polyline = document.createElementNS(svgNS, "polyline");
                polyline.setAttribute("points", points);
                polyline.setAttribute("fill", "none");
                polyline.setAttribute("stroke", s.color);
                polyline.setAttribute("stroke-width", "2.5");
                polyline.setAttribute("stroke-linejoin", "round");
                polyline.setAttribute("stroke-linecap", "round");
                svg.appendChild(polyline);
            }

            return s.data.map(function (v, i) {
                var circle = document.createElementNS(svgNS, "circle");
                circle.setAttribute("cx", xFor(i));
                circle.setAttribute("cy", yFor(v));
                circle.setAttribute("r", "3");
                circle.setAttribute("fill", s.color);
                svg.appendChild(circle);
                return circle;
            });
        });

        var hoverLine = document.createElementNS(svgNS, "line");
        hoverLine.setAttribute("y1", paddingTop);
        hoverLine.setAttribute("y2", height - paddingBottom);
        hoverLine.setAttribute("stroke", "#c7d2d9");
        hoverLine.setAttribute("stroke-width", "1");
        hoverLine.setAttribute("stroke-dasharray", "3,3");
        hoverLine.style.display = "none";
        svg.appendChild(hoverLine);

        root.innerHTML = "";
        root.appendChild(svg);

        var tooltip = document.createElement("div");
        tooltip.className = "nc-activity-chart-tooltip";
        tooltip.hidden = true;
        root.appendChild(tooltip);

        function showTooltip(index) {
            hoverLine.style.display = "block";
            hoverLine.setAttribute("x1", xFor(index));
            hoverLine.setAttribute("x2", xFor(index));

            pointGroups.forEach(function (dots) {
                dots.forEach(function (dot, i) {
                    dot.setAttribute("r", i === index ? "5" : "3");
                });
            });

            var rows = series.map(function (s) {
                return (
                    '<div class="nc-activity-chart-tooltip-row">' +
                    '<span class="nc-activity-chart-dot" style="background:' + s.color + '"></span>' +
                    s.label + '<strong>' + s.data[index] + '</strong></div>'
                );
            }).join("");

            tooltip.innerHTML =
                '<div class="nc-activity-chart-tooltip-date">' + tooltipLabels[index] + '</div>' + rows;
            tooltip.hidden = false;

            var leftPercent = (xFor(index) / width) * 100;
            tooltip.style.left = Math.min(Math.max(leftPercent, 18), 82) + "%";
        }

        function hideTooltip() {
            hoverLine.style.display = "none";
            pointGroups.forEach(function (dots) {
                dots.forEach(function (dot) { dot.setAttribute("r", "3"); });
            });
            tooltip.hidden = true;
        }

        function indexFromClientX(clientX) {
            var rect = svg.getBoundingClientRect();
            var relativeX = ((clientX - rect.left) / rect.width) * width;
            var index = Math.round((relativeX - paddingLeft) / (stepX || 1));
            return Math.min(Math.max(index, 0), labels.length - 1);
        }

        svg.addEventListener("mousemove", function (event) {
            showTooltip(indexFromClientX(event.clientX));
        });
        svg.addEventListener("mouseleave", hideTooltip);
        svg.addEventListener("touchstart", function (event) {
            var touch = event.touches[0];
            if (touch) showTooltip(indexFromClientX(touch.clientX));
        }, { passive: true });
        svg.addEventListener("touchmove", function (event) {
            var touch = event.touches[0];
            if (touch) showTooltip(indexFromClientX(touch.clientX));
        }, { passive: true });
    }

    function renderAll() {
        document.querySelectorAll("[data-activity-chart]").forEach(renderActivityChart);
    }

    document.addEventListener("DOMContentLoaded", renderAll);

    var resizeTimer = null;
    window.addEventListener("resize", function () {
        window.clearTimeout(resizeTimer);
        resizeTimer = window.setTimeout(renderAll, 150);
    });

})();
