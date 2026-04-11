/**
 * Celestial Arc — step flow, manual DOB validation,
 * API call, blueprint chips, and rich report rendering.
 */
document.addEventListener("DOMContentLoaded", function () {
    "use strict";

    const form = document.getElementById("astroForm");
    const step1 = document.getElementById("step1");
    const step2 = document.getElementById("step2");
    const step3 = document.getElementById("step3");
    const processing = document.getElementById("processing");
    const results = document.getElementById("results");
    const errorBox = document.getElementById("errorBox");

    const goStep2 = document.getElementById("goStep2");
    const palmYes = document.getElementById("palmYes");
    const palmNo = document.getElementById("palmNo");
    const submitBtn = document.getElementById("submitBtn");
    const palmEnabled = document.getElementById("palmEnabled");
    const handChoice = document.getElementById("handChoice");

    const birthDateHidden = document.getElementById("birthDateHidden");
    const birthYear = document.getElementById("birthYear");
    const birthMonth = document.getElementById("birthMonth");
    const birthDay = document.getElementById("birthDay");

    const track1 = document.getElementById("track1");
    const track2 = document.getElementById("track2");
    const track3 = document.getElementById("track3");
    const track4 = document.getElementById("track4");

    const progressBar = document.getElementById("progressBar");
    const progressText = document.getElementById("progressText");

    const resultTitle = document.getElementById("resultTitle");
    const resultMeta = document.getElementById("resultMeta");
    const blueprintChips = document.getElementById("blueprintChips");
    const profileCards = document.getElementById("profileCards");
    const reportSections = document.getElementById("reportSections");
    const reportPrintBlock = document.getElementById("reportPrintBlock");
    const downloadPdf = document.getElementById("downloadPdf");
    const tryAgain = document.getElementById("tryAgain");
    const chatHint = document.getElementById("chatHint");
    const chatLog = document.getElementById("chatLog");
    const chatInput = document.getElementById("chatInput");
    const chatSend = document.getElementById("chatSend");
    const birthPlace = document.getElementById("birthPlace");
    const placeDropdown = document.getElementById("placeDropdown");
    const placeLat = document.getElementById("placeLat");
    const placeLon = document.getElementById("placeLon");
    const placeLabel = document.getElementById("placeLabel");
    const placeTz = document.getElementById("placeTz");

    let progressInterval = null;
    let busy = false;
    let lastReportId = null;
    let placeTimeout = null;
    let lastPlaceQuery = "";
    let activePlaceIndex = -1;
    let csrfToken = "";

    // ============================================
    // CSRF + CHAT HINT
    // ============================================

    function fetchCsrfToken() {
        return fetch("/api/csrf")
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data && data.success && data.csrf_token) {
                    csrfToken = String(data.csrf_token);
                }
            })
            .catch(function () {
                csrfToken = "";
            });
    }

    function fetchChatHint() {
        fetch("/api/config")
            .then(function (r) { return r.json(); })
            .then(function (cfg) {
                if (!chatHint) return;
                if (cfg && cfg.ai_chat) {
                    chatHint.textContent =
                        "AI-enhanced Guru is on. Answers blend your saved chart context with your question.";
                } else {
                    chatHint.textContent =
                        "Offline Guru: rule-based guidance from your saved reading. Add GROQ_API_KEY or OPENAI_API_KEY on the server for deeper AI replies.";
                }
            })
            .catch(function () {
                if (chatHint) {
                    chatHint.textContent = "Ask about Rahu/Ketu, marriage, career, dasha, or remedies.";
                }
            });
    }

    // ============================================
    // HTML ESCAPING
    // ============================================

    function escapeHtml(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // ============================================
    // PLACE AUTOCOMPLETE
    // ============================================

    function clearPlaceSelection() {
        if (placeLat) placeLat.value = "";
        if (placeLon) placeLon.value = "";
        if (placeLabel) placeLabel.value = "";
        if (placeTz) placeTz.value = "";
    }

    function hidePlaceDropdown() {
        if (!placeDropdown) return;
        placeDropdown.classList.add("hidden");
        placeDropdown.innerHTML = "";
        activePlaceIndex = -1;
    }

    function showPlaceDropdown(items) {
        if (!placeDropdown) return;
        placeDropdown.innerHTML = "";
        activePlaceIndex = -1;

        if (!items || !items.length) {
            hidePlaceDropdown();
            return;
        }

        items.forEach(function (item, idx) {
            const row = document.createElement("div");
            row.className = "neo-option";
            row.setAttribute("role", "option");
            row.setAttribute("data-idx", String(idx));
            row.textContent = item.label || "";
            row.addEventListener("mousedown", function (e) {
                e.preventDefault();
                selectPlaceItem(item);
            });
            placeDropdown.appendChild(row);
        });

        placeDropdown.classList.remove("hidden");
    }

    function selectPlaceItem(item) {
        if (!item) return;
        if (birthPlace) birthPlace.value = item.label || "";
        if (placeLat) placeLat.value = item.lat != null ? String(item.lat) : "";
        if (placeLon) placeLon.value = item.lon != null ? String(item.lon) : "";
        if (placeLabel) placeLabel.value = item.label || "";
        if (placeTz) placeTz.value = item.tz || "";
        hidePlaceDropdown();
    }

    function fetchPlaceSuggestions(query) {
        const q = String(query || "").trim();
        if (!q || q.length < 2) {
            hidePlaceDropdown();
            return;
        }
        lastPlaceQuery = q;

        clearTimeout(placeTimeout);
        placeTimeout = setTimeout(function () {
            fetch("/api/places?q=" + encodeURIComponent(q))
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    if (lastPlaceQuery !== q) return;
                    showPlaceDropdown((data && data.places) || []);
                })
                .catch(function () {
                    hidePlaceDropdown();
                });
        }, 280);
    }

    if (birthPlace) {
        birthPlace.addEventListener("input", function () {
            clearPlaceSelection();
            fetchPlaceSuggestions(this.value);
        });
        birthPlace.addEventListener("blur", function () {
            setTimeout(hidePlaceDropdown, 120);
        });
        birthPlace.addEventListener("focus", function () {
            fetchPlaceSuggestions(this.value);
        });
        birthPlace.addEventListener("keydown", function (e) {
            const opts = placeDropdown ? placeDropdown.querySelectorAll(".neo-option") : [];
            if (!opts.length) return;
            if (e.key === "ArrowDown") {
                e.preventDefault();
                activePlaceIndex = Math.min(activePlaceIndex + 1, opts.length - 1);
                opts.forEach(function (o, i) { o.classList.toggle("active", i === activePlaceIndex); });
            } else if (e.key === "ArrowUp") {
                e.preventDefault();
                activePlaceIndex = Math.max(activePlaceIndex - 1, 0);
                opts.forEach(function (o, i) { o.classList.toggle("active", i === activePlaceIndex); });
            } else if (e.key === "Enter" && activePlaceIndex >= 0) {
                e.preventDefault();
                opts[activePlaceIndex] && opts[activePlaceIndex].dispatchEvent(new MouseEvent("mousedown"));
            } else if (e.key === "Escape") {
                hidePlaceDropdown();
            }
        });
    }

    // ============================================
    // DATE OF BIRTH SELECTORS
    // ============================================

    function syncHiddenBirthDate() {
        if (!birthDateHidden) return;
        const y = parseInt((birthYear && birthYear.value) || "", 10);
        const m = parseInt((birthMonth && birthMonth.value) || "", 10);
        const d = parseInt((birthDay && birthDay.value) || "", 10);
        if (!y || !m || !d) {
            birthDateHidden.value = "";
            return;
        }
        const dt = new Date(Date.UTC(y, m - 1, d));
        if (dt.getUTCFullYear() !== y || dt.getUTCMonth() !== (m - 1) || dt.getUTCDate() !== d) {
            birthDateHidden.value = "";
            return;
        }
        const mm = m < 10 ? "0" + m : String(m);
        const dd = d < 10 ? "0" + d : String(d);
        birthDateHidden.value = String(y) + "-" + mm + "-" + dd;
    }

    function daysInMonth(y, m) {
        return new Date(y, m, 0).getDate();
    }

    function initDobSelectors() {
        if (!birthYear || !birthMonth || !birthDay) return;

        const nowY = new Date().getFullYear();
        birthYear.innerHTML = '<option value="">Year</option>';
        for (let y = nowY; y >= 1940; y -= 1) {
            const opt = document.createElement("option");
            opt.value = String(y);
            opt.textContent = String(y);
            birthYear.appendChild(opt);
        }

        const monthNames = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ];
        birthMonth.innerHTML = '<option value="">Month</option>';
        monthNames.forEach(function (name, idx) {
            const opt = document.createElement("option");
            opt.value = String(idx + 1);
            opt.textContent = name;
            birthMonth.appendChild(opt);
        });

        birthDay.innerHTML = '<option value="">Day</option>';

        function refillDays() {
            const y = parseInt(birthYear.value || "", 10);
            const m = parseInt(birthMonth.value || "", 10);
            const prev = birthDay.value;
            birthDay.innerHTML = '<option value="">Day</option>';
            if (!y || !m) return;
            const max = daysInMonth(y, m);
            for (let d = 1; d <= max; d += 1) {
                const opt = document.createElement("option");
                opt.value = String(d);
                opt.textContent = String(d);
                birthDay.appendChild(opt);
            }
            if (prev && parseInt(prev, 10) <= max) birthDay.value = prev;
        }

        birthYear.addEventListener("change", function () { refillDays(); syncHiddenBirthDate(); });
        birthMonth.addEventListener("change", function () { refillDays(); syncHiddenBirthDate(); });
        birthDay.addEventListener("change", function () { syncHiddenBirthDate(); });
    }

    // ============================================
    // VALIDATION
    // ============================================

    function validateRequired() {
        clearError();
        if (!String(form.elements.full_name.value || "").trim()) {
            showError("Please enter your full name.");
            return false;
        }
        syncHiddenBirthDate();
        if (!birthDateHidden || !birthDateHidden.value) {
            showError("Please select your full date of birth (year, month, day).");
            return false;
        }
        if (!String(form.elements.birth_time.value || "").trim()) {
            showError("Please enter your time of birth.");
            return false;
        }
        if (!String(form.elements.birth_place.value || "").trim()) {
            showError("Please enter your place of birth.");
            return false;
        }
        return true;
    }

    // ============================================
    // STEP NAVIGATION
    // ============================================

    function setStepTrack(active) {
        [track1, track2, track3, track4].forEach(function (el) {
            if (el) el.classList.remove("neo-step-active");
        });
        if (active === 1 && track1) track1.classList.add("neo-step-active");
        if (active === 2 && track2) track2.classList.add("neo-step-active");
        if (active === 3 && track3) track3.classList.add("neo-step-active");
        if (active === 4 && track4) track4.classList.add("neo-step-active");
    }

    function onlyStep(stepEl, trackNum) {
        [step1, step2, step3, processing, results].forEach(function (el) {
            if (el) el.classList.add("hidden");
        });
        if (stepEl) stepEl.classList.remove("hidden");
        if (typeof trackNum === "number") {
            setStepTrack(trackNum);
        }
    }

    function showError(msg) {
        if (!errorBox) return;
        errorBox.textContent = msg;
        errorBox.classList.remove("hidden");
    }

    function clearError() {
        if (!errorBox) return;
        errorBox.textContent = "";
        errorBox.classList.add("hidden");
    }

    // ============================================
    // PROGRESS BAR
    // ============================================

    function resetProgress() {
        clearInterval(progressInterval);
        progressInterval = null;
        if (progressBar) progressBar.style.width = "0%";
        if (progressText) progressText.textContent = "0%";
    }

    function startProgress() {
        resetProgress();
        let p = 0;
        progressInterval = setInterval(function () {
            p = Math.min(p + Math.random() * 12, 88);
            if (progressBar) progressBar.style.width = p + "%";
            if (progressText) progressText.textContent = Math.floor(p) + "%";
        }, 400);
    }

    function finishProgress() {
        clearInterval(progressInterval);
        progressInterval = null;
        if (progressBar) progressBar.style.width = "100%";
        if (progressText) progressText.textContent = "100%";
    }

    // ============================================
    // REPORT RENDERING
    // ============================================

    function chip(label, value) {
        return (
            '<span class="blueprint-chip">' +
            '<span class="chip-label">' + escapeHtml(label) + "</span>" +
            '<span class="chip-value">' + escapeHtml(value) + "</span>" +
            "</span>"
        );
    }

    function sectionCard(title, body, icon) {
        var intensity = 50 + ((title.length * 7 + (body || "").length) % 42);
        return (
            '<div class="report-card reveal-hidden">' +
            '<div class="report-card-header">' +
            '<span class="report-card-icon">' + (icon || "✦") + "</span>" +
            '<h3 class="report-card-title">' + escapeHtml(title) + "</h3>" +
            "</div>" +
            '<p class="report-card-body">' + escapeHtml(body) + "</p>" +
            '<div class="reading-intensity"><span class="reading-intensity-label">Cosmic Intensity</span>' +
            '<div class="reading-intensity-bar"><div class="reading-intensity-fill" data-target="' + intensity + '%"></div></div></div>' +
            '<button type="button" class="reading-ask-cta" data-topic="' + escapeHtml(title) + '">✨ Ask Guru about this</button>' +
            "</div>"
        );
    }

    function renderResults(data) {
        const profile = data.profile || {};
        const bp = data.blueprint || {};

        if (resultTitle) resultTitle.textContent = (profile.zodiac || "") + " · Your Cosmic Brief";
        if (resultMeta) {
            resultMeta.textContent =
                "Sun " + (profile.zodiac || "—") +
                " · Moon " + (profile.moon_sign || "—") +
                " · Asc " + (profile.ascendant || "—");
        }

        if (profileCards) {
            if (bp && bp.element) {
                profileCards.innerHTML = [
                    ["Zodiac sign", profile.zodiac || "—"],
                    ["Moon sign", profile.moon_sign || "—"],
                    ["Ascendant", profile.ascendant || "—"],
                    ["Element · modality", (bp.element || "—") + " · " + (bp.modality || "—")],
                    ["Ruling planet", bp.ruling_planet || "—"],
                    ["Energy focus", bp.energy_focus || "—"]
                ]
                    .map(function (row) {
                        return (
                            '<div class="profile-card">' +
                            '<p class="profile-label">' +
                            escapeHtml(row[0]) +
                            '</p><p class="profile-value">' +
                            escapeHtml(row[1]) +
                            "</p></div>"
                        );
                    })
                    .join("");
            } else {
                profileCards.innerHTML = [
                    ["Zodiac sign", profile.zodiac || "Unknown"],
                    ["Moon sign", profile.moon_sign || "Unknown"],
                    ["Ascendant", profile.ascendant || "Unknown"]
                ]
                    .map(function (item) {
                        return (
                            '<div class="profile-card">' +
                            '<p class="profile-label">' +
                            escapeHtml(item[0]) +
                            '</p><p class="profile-value">' +
                            escapeHtml(item[1]) +
                            "</p></div>"
                        );
                    })
                    .join("");
            }
        }

        if (blueprintChips) {
            const pairs = [
                ["Lucky #", String(bp.lucky_number != null ? bp.lucky_number : "—")],
                ["Lucky day", bp.lucky_day || "—"],
                ["Lucky colors", bp.lucky_color || "—"],
                ["Easy resonance", bp.best_matches || "—"],
                ["Growth catalysts", bp.growth_signs || "—"]
            ];
            if (data.vedic && data.vedic.houses) {
                const h = data.vedic.houses;
                pairs.push(
                    ["Rahu (house)", String(h.rahu)],
                    ["Ketu (house)", String(h.ketu)],
                    ["Mahadasha (demo)", String(data.vedic.mahadasha || "—")]
                );
            }
            blueprintChips.innerHTML = pairs.map(function (pair) {
                return chip(pair[0], pair[1]);
            }).join("");
        }

        if (reportSections) {
            const sections = data.sections || {};
            const order = [
                ["Personality Analysis", sections.personality || "", "✦"],
                ["Career Path", sections.career || "", "✦"],
                ["Love & Relationships", sections.love || "", "✦"],
                ["Future Outlook", sections.future || "", "✦"],
                ["Core Strengths", sections.strengths || "", "☀"],
                ["Growth Edges", sections.weaknesses || "", "☽"],
                ["Wellness & Rhythm", sections.wellness || "", "✧"],
                ["Compatibility Notes", sections.compatibility || "", "♥"],
                ["Seasonal Energy & Timing", sections.seasonal_energy || "", "◎"],
                ["Kundli & chart layer", sections.kundli_layer || "", "✦"],
                ["Houses (whole-sign demo)", sections.vedic_houses || "", "✦"],
                ["Rahu & Ketu", sections.rahu_ketu || "", "✦"],
                ["Dasha / dosha snapshot", sections.vimshottari_timing || "", "✦"],
                ["Remedies & ethical lifestyle", sections.remedies_lifestyle || "", "✦"]
            ];
            let html = "";
            order.forEach(function (row) {
                if (row[1]) {
                    html += sectionCard(row[0], row[1], row[2]);
                }
            });
            if (data.palm_analysis) {
                html += sectionCard("Palm Reading Insight", data.palm_analysis, "✋");
            }
            reportSections.innerHTML = html;
        }

        if (reportPrintBlock && data.report_html) {
            reportPrintBlock.innerHTML = data.report_html;
        }

        lastReportId = data.report_id;
        if (chatLog) {
            chatLog.innerHTML = "";
        }

        // Render mini kundli chart in results
        var kundliChartContainer = document.getElementById("kundliChartContainer");
        var kundliChartDiv = document.getElementById("kundliChart");
        if (kundliChartContainer && kundliChartDiv && data.vedic && data.vedic.houses) {
            kundliChartDiv.innerHTML = "";
            var asc = (data.profile || {}).ascendant || (data.vedic || {}).lagna_sign || "Aries";
            var hp = _invertHouseMap(data.vedic.houses);
            _buildKundliSVG(kundliChartDiv, asc, hp, true);
            kundliChartDiv.querySelectorAll(".chart-line").forEach(function(el) {
                el.style.strokeDashoffset = "0";
            });
            kundliChartDiv.querySelectorAll(".kundli-house-num-text, .kundli-sign-label, .kundli-planet-glyph").forEach(function(el) {
                el.classList.add("visible");
            });
            kundliChartContainer.classList.remove("hidden");
        }

        // Setup staggered reading reveals
        setTimeout(_initReadingReveals, 150);
    }

    // ============================================
    // KUNDLI ANIMATION ENGINE
    // ============================================

    var _KUNDLI_HOUSES = [
        { id:1,  pts:"250,50 350,150 250,250 150,150", cx:250, cy:150 },
        { id:2,  pts:"250,50 450,50 350,150",          cx:350, cy:83  },
        { id:3,  pts:"450,50 450,250 350,150",          cx:417, cy:150 },
        { id:4,  pts:"350,150 450,250 350,350 250,250", cx:350, cy:250 },
        { id:5,  pts:"450,250 450,450 350,350",          cx:417, cy:350 },
        { id:6,  pts:"450,450 250,450 350,350",          cx:350, cy:417 },
        { id:7,  pts:"350,350 250,450 150,350 250,250", cx:250, cy:350 },
        { id:8,  pts:"250,450 50,450 150,350",           cx:150, cy:417 },
        { id:9,  pts:"50,450 50,250 150,350",            cx:83,  cy:350 },
        { id:10, pts:"150,350 50,250 150,150 250,250",   cx:150, cy:250 },
        { id:11, pts:"50,250 50,50 150,150",             cx:83,  cy:150 },
        { id:12, pts:"50,50 250,50 150,150",             cx:150, cy:83  }
    ];

    var _HOUSE_MEANINGS = {
        1:"Self, Identity & Life Path", 2:"Wealth, Speech & Family",
        3:"Courage, Siblings & Skills", 4:"Home, Mother & Inner Peace",
        5:"Creativity, Children & Romance", 6:"Health, Service & Competition",
        7:"Marriage, Partnerships & Desires", 8:"Transformation & Hidden Forces",
        9:"Fortune, Wisdom & Higher Truth", 10:"Career, Status & Public Life",
        11:"Gains, Aspirations & Networks", 12:"Liberation, Dreams & Solitude"
    };

    var _PLANET_GLYPHS = { sun:"\u2609",moon:"\u263D",mars:"\u2642",mercury:"\u263F",venus:"\u2640",jupiter:"\u2643",saturn:"\u2644",rahu:"\u260A",ketu:"\u260B" };
    var _PLANET_NAMES = { sun:"Sun",moon:"Moon",mars:"Mars",mercury:"Mercury",venus:"Venus",jupiter:"Jupiter",saturn:"Saturn",rahu:"Rahu",ketu:"Ketu" };
    var _ZODIAC_LIST = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"];
    var _ZODIAC_GLYPHS = { Aries:"\u2648",Taurus:"\u2649",Gemini:"\u264A",Cancer:"\u264B",Leo:"\u264C",Virgo:"\u264D",Libra:"\u264E",Scorpio:"\u264F",Sagittarius:"\u2650",Capricorn:"\u2651",Aquarius:"\u2652",Pisces:"\u2653" };

    function _invertHouseMap(houses) {
        var r = {}; for (var h = 1; h <= 12; h++) r[h] = [];
        if (!houses) return r;
        Object.keys(houses).forEach(function(p) { var hh = houses[p]; if (r[hh]) r[hh].push(p); });
        return r;
    }

    function _signForHouse(num, asc) {
        var idx = _ZODIAC_LIST.indexOf(asc); if (idx < 0) idx = 0;
        return _ZODIAC_LIST[(idx + num - 1) % 12];
    }

    function _buildKundliSVG(parent, asc, hpMap, mini) {
        var ns = "http://www.w3.org/2000/svg";
        var svg = document.createElementNS(ns, "svg");
        svg.setAttribute("viewBox", "0 0 500 500");
        svg.setAttribute("class", mini ? "mini-kundli-svg" : "kundli-chart-svg");

        // Glow filter
        var defs = document.createElementNS(ns, "defs");
        var filt = document.createElementNS(ns, "filter"); filt.id = "kGlow";
        var blur = document.createElementNS(ns, "feGaussianBlur"); blur.setAttribute("stdDeviation","3"); blur.setAttribute("result","g");
        var merge = document.createElementNS(ns, "feMerge");
        var mn1 = document.createElementNS(ns, "feMergeNode"); mn1.setAttribute("in","g");
        var mn2 = document.createElementNS(ns, "feMergeNode"); mn2.setAttribute("in","SourceGraphic");
        merge.appendChild(mn1); merge.appendChild(mn2); filt.appendChild(blur); filt.appendChild(merge);
        defs.appendChild(filt); svg.appendChild(defs);

        // Outer square
        var outer = document.createElementNS(ns, "path");
        outer.setAttribute("d", "M50,50 L450,50 L450,450 L50,450 Z");
        outer.setAttribute("class", "chart-line chart-outer");
        var outerLen = 1600;
        outer.style.strokeDasharray = outerLen; outer.style.strokeDashoffset = outerLen;
        svg.appendChild(outer);

        // Diamond
        var diamond = document.createElementNS(ns, "path");
        diamond.setAttribute("d", "M250,50 L450,250 L250,450 L50,250 Z");
        diamond.setAttribute("class", "chart-line chart-diamond");
        var diaLen = 1132;
        diamond.style.strokeDasharray = diaLen; diamond.style.strokeDashoffset = diaLen;
        svg.appendChild(diamond);

        // Diagonal lines from corners to center
        [[50,50,250,250],[450,50,250,250],[450,450,250,250],[50,450,250,250]].forEach(function(d) {
            var ln = document.createElementNS(ns, "line");
            ln.setAttribute("x1",d[0]); ln.setAttribute("y1",d[1]);
            ln.setAttribute("x2",d[2]); ln.setAttribute("y2",d[3]);
            ln.setAttribute("class", "chart-line chart-diag");
            var len = Math.ceil(Math.sqrt(Math.pow(d[2]-d[0],2)+Math.pow(d[3]-d[1],2)));
            ln.style.strokeDasharray = len; ln.style.strokeDashoffset = len;
            svg.appendChild(ln);
        });

        // House polygons
        _KUNDLI_HOUSES.forEach(function(h) {
            var poly = document.createElementNS(ns, "polygon");
            poly.setAttribute("points", h.pts);
            poly.setAttribute("class", "kundli-house-poly");
            poly.setAttribute("data-house", h.id);
            svg.appendChild(poly);
        });

        // House numbers
        _KUNDLI_HOUSES.forEach(function(h) {
            var t = document.createElementNS(ns, "text");
            t.setAttribute("x", h.cx); t.setAttribute("y", h.cy - 14);
            t.setAttribute("class", "kundli-house-num-text"); t.setAttribute("data-house", h.id);
            t.textContent = String(h.id); svg.appendChild(t);
        });

        // Zodiac sign glyphs
        _KUNDLI_HOUSES.forEach(function(h) {
            var sign = _signForHouse(h.id, asc);
            var t = document.createElementNS(ns, "text");
            t.setAttribute("x", h.cx); t.setAttribute("y", h.cy + 2);
            t.setAttribute("class", "kundli-sign-label"); t.setAttribute("data-house", h.id);
            t.textContent = _ZODIAC_GLYPHS[sign] || sign.substring(0,3); svg.appendChild(t);
        });

        // Planet glyphs
        _KUNDLI_HOUSES.forEach(function(h) {
            var planets = hpMap[h.id] || [];
            planets.forEach(function(p, idx) {
                var g = _PLANET_GLYPHS[p] || "?";
                var t = document.createElementNS(ns, "text");
                var ox = (idx - (planets.length - 1) / 2) * 16;
                t.setAttribute("x", h.cx + ox); t.setAttribute("y", h.cy + 16);
                t.setAttribute("class", "kundli-planet-glyph");
                t.setAttribute("data-house", h.id); t.setAttribute("data-planet", p);
                t.textContent = g; svg.appendChild(t);
            });
        });

        parent.appendChild(svg);
        return svg;
    }

    function _createStars(container, n) {
        for (var i = 0; i < n; i++) {
            var s = document.createElement("div"); s.className = "kundli-star";
            s.style.left = Math.random()*100 + "%"; s.style.top = Math.random()*100 + "%";
            s.style.setProperty("--dur", (2+Math.random()*4)+"s");
            s.style.animationDelay = Math.random()*3+"s";
            var sz = (1+Math.random()*2)+"px"; s.style.width = sz; s.style.height = sz;
            container.appendChild(s);
        }
    }

    async function _playKundliAnimation(chartData, doneCallback) {
        var anim = document.getElementById("kundliAnimation");
        var stars = document.getElementById("kundliStars");
        var grid = document.getElementById("kundliGrid");
        var portal = document.getElementById("kundliPortal");
        var chartArea = document.getElementById("kundliChartArea");
        var infoPnl = document.getElementById("kundliInfoPanel");
        var statusTxt = document.getElementById("kundliStatusText");
        var progFill = document.getElementById("kundliProgressFill");
        var completeOv = document.getElementById("kundliComplete");
        var skipBtn = document.getElementById("kundliSkip");

        var skipped = false;
        function doSkip() { skipped = true; }
        if (skipBtn) skipBtn.addEventListener("click", doSkip);

        function wait(ms) {
            if (skipped) return Promise.resolve();
            return new Promise(function(r) { setTimeout(r, ms); });
        }
        function setSt(t) { if (statusTxt) statusTxt.textContent = t; }
        function setProg(p) { if (progFill) progFill.style.width = p + "%"; }

        var vedic = chartData.vedic || {};
        var profile = chartData.profile || {};
        var houses = vedic.houses || {};
        var ascSign = profile.ascendant || vedic.lagna_sign || "Aries";
        var hpMap = _invertHouseMap(houses);

        // Clean previous
        if (stars) stars.innerHTML = "";
        chartArea.innerHTML = "";

        // Show overlay
        anim.classList.remove("hidden");
        await wait(30);
        anim.classList.add("active");

        // Phase 0: Stars
        if (stars) _createStars(stars, 80);
        setSt("CONNECTING TO CELESTIAL COORDINATES");
        await wait(700);
        if (skipped) { _finish(); return; }

        // Phase 1: Portal
        setSt("OPENING COSMIC GATEWAY");
        if (grid) grid.classList.add("active");
        if (portal) portal.classList.add("active");
        setProg(5);
        await wait(1800);
        if (skipped) { _finish(); return; }

        // Phase 2: Chart draws
        setSt("MATERIALIZING YOUR BIRTH CHART");
        if (portal) portal.classList.remove("active");
        chartArea.classList.add("active");

        var svg = _buildKundliSVG(chartArea, ascSign, hpMap, false);
        setProg(10);
        await wait(200);
        if (skipped) { _finish(); return; }

        // Draw lines with stagger
        var allLines = svg.querySelectorAll(".chart-line");
        for (var li = 0; li < allLines.length; li++) {
            if (skipped) break;
            allLines[li].style.strokeDashoffset = "0";
            await wait(250);
        }
        setProg(15);
        await wait(400);
        if (skipped) { _finish(); return; }

        // Show house numbers
        svg.querySelectorAll(".kundli-house-num-text").forEach(function(el) { el.classList.add("visible"); });
        await wait(300);
        if (skipped) { _finish(); return; }

        // Phase 3: Scan each house
        setSt("SCANNING PLANETARY POSITIONS");

        for (var h = 1; h <= 12; h++) {
            if (skipped) break;
            var pct = 15 + (h / 12) * 75;
            setProg(Math.round(pct));

            var sign = _signForHouse(h, ascSign);
            var planets = hpMap[h] || [];
            var meaning = _HOUSE_MEANINGS[h] || "";

            // Highlight polygon
            var poly = svg.querySelector('.kundli-house-poly[data-house="' + h + '"]');
            svg.querySelectorAll(".kundli-house-poly.scanning").forEach(function(el) {
                el.classList.remove("scanning"); el.classList.add("scanned");
            });
            if (poly) poly.classList.add("scanning");

            // Highlight house number
            svg.querySelectorAll(".kundli-house-num-text.active").forEach(function(el) { el.classList.remove("active"); });
            var numEl = svg.querySelector('.kundli-house-num-text[data-house="' + h + '"]');
            if (numEl) numEl.classList.add("active");

            // Show zodiac
            var signEl = svg.querySelector('.kundli-sign-label[data-house="' + h + '"]');
            if (signEl) signEl.classList.add("visible");

            // Update status & info panel
            setSt("ANALYZING HOUSE " + h + " \u00B7 " + sign.toUpperCase());
            var iHL = document.getElementById("kundliInfoHouseLabel");
            var iSN = document.getElementById("kundliInfoSignName");
            var iMN = document.getElementById("kundliInfoMeaning");
            var iPL = document.getElementById("kundliInfoPlanets");
            if (iHL) iHL.textContent = "HOUSE " + h;
            if (iSN) iSN.textContent = (_ZODIAC_GLYPHS[sign] || "") + " " + sign;
            if (iMN) iMN.textContent = meaning;
            if (iPL) {
                iPL.innerHTML = "";
                if (planets.length === 0) {
                    var ec = document.createElement("span");
                    ec.className = "kundli-info-chip visible"; ec.style.opacity = "0.35";
                    ec.textContent = "No planets"; iPL.appendChild(ec);
                }
            }
            infoPnl.classList.add("active");

            await wait(700);
            if (skipped) break;

            // Reveal planets
            for (var pi = 0; pi < planets.length; pi++) {
                if (skipped) break;
                var pl = planets[pi];
                var gEl = svg.querySelector('.kundli-planet-glyph[data-house="' + h + '"][data-planet="' + pl + '"]');
                if (gEl) gEl.classList.add("visible");
                if (iPL) {
                    var chip = document.createElement("span");
                    chip.className = "kundli-info-chip";
                    chip.innerHTML = '<span class="kundli-info-chip-glyph">' + escapeHtml(_PLANET_GLYPHS[pl]||"?") + "</span> " + escapeHtml(_PLANET_NAMES[pl]||pl);
                    iPL.appendChild(chip);
                    chip.offsetHeight; // reflow
                    chip.classList.add("visible");
                }
                await wait(400);
            }

            var hold = planets.length > 0 ? 2200 : 1200;
            await wait(hold);
        }

        if (skipped) { _finish(); return; }

        // Phase 4: Complete
        svg.querySelectorAll(".kundli-house-poly.scanning").forEach(function(el) {
            el.classList.remove("scanning"); el.classList.add("scanned");
        });
        svg.querySelectorAll(".kundli-house-num-text").forEach(function(el) { el.classList.remove("active"); });
        svg.querySelectorAll(".kundli-sign-label, .kundli-planet-glyph").forEach(function(el) { el.classList.add("visible"); });

        setProg(95);
        setSt("SYNTHESIS COMPLETE");
        infoPnl.classList.remove("active");
        await wait(600);

        if (completeOv) completeOv.classList.add("active");
        setProg(100);
        await wait(2200);

        _finish();

        function _finish() {
            if (skipBtn) skipBtn.removeEventListener("click", doSkip);
            anim.classList.remove("active");
            setTimeout(function() {
                anim.classList.add("hidden");
                if (portal) portal.classList.remove("active");
                if (grid) grid.classList.remove("active");
                chartArea.classList.remove("active");
                infoPnl.classList.remove("active");
                if (completeOv) completeOv.classList.remove("active");
                setProg(0);
                if (doneCallback) doneCallback();
            }, 700);
        }
    }
    window.playKundliAnimation = _playKundliAnimation;
    window.renderResultsForTesting = renderResults;

    function _initReadingReveals() {
        var cards = document.querySelectorAll(".report-card.reveal-hidden");
        if (!cards.length) return;
        var autoCount = 3;
        cards.forEach(function(card, idx) {
            if (idx < autoCount) {
                setTimeout(function() {
                    card.classList.remove("reveal-hidden");
                    card.classList.add("reveal-visible");
                    card.querySelectorAll(".reading-intensity-fill").forEach(function(bar) {
                        var t = bar.getAttribute("data-target") || "50%";
                        setTimeout(function() { bar.style.width = t; }, 200);
                    });
                }, idx * 350);
            }
        });
        if ("IntersectionObserver" in window) {
            var obs = new IntersectionObserver(function(entries) {
                entries.forEach(function(entry) {
                    if (entry.isIntersecting) {
                        entry.target.classList.remove("reveal-hidden");
                        entry.target.classList.add("reveal-visible");
                        entry.target.querySelectorAll(".reading-intensity-fill").forEach(function(bar) {
                            var t = bar.getAttribute("data-target") || "50%";
                            setTimeout(function() { bar.style.width = t; }, 200);
                        });
                        obs.unobserve(entry.target);
                    }
                });
            }, { threshold: 0.12 });
            cards.forEach(function(card, idx) {
                if (idx >= autoCount) obs.observe(card);
            });
        } else {
            cards.forEach(function(card) {
                card.classList.remove("reveal-hidden");
                card.classList.add("reveal-visible");
            });
        }
    }

    // Ask Guru CTA delegation
    if (reportSections) {
        reportSections.addEventListener("click", function(e) {
            var btn = e.target.closest(".reading-ask-cta");
            if (!btn) return;
            var topic = btn.getAttribute("data-topic") || "";
            if (chatInput) {
                chatInput.value = "Tell me more about my " + topic;
                var gc = document.getElementById("guruChat");
                if (gc) gc.scrollIntoView({ behavior: "smooth" });
                chatInput.focus();
            }
        });
    }

    // ============================================
    // IN-PAGE CHAT (GURU)
    // ============================================

    function appendChatBubble(role, text, meta) {
        if (!chatLog) return;
        const wrap = document.createElement("div");
        wrap.className =
            "chat-bubble " + (role === "user" ? "chat-bubble-user" : "chat-bubble-guru");
        if (meta) {
            const m = document.createElement("div");
            m.className = "chat-meta";
            m.textContent = meta;
            wrap.appendChild(m);
        }
        const body = document.createElement("div");
        body.textContent = text;
        wrap.appendChild(body);
        chatLog.appendChild(wrap);
        chatLog.scrollTop = chatLog.scrollHeight;
    }

    function sendChat() {
        if (!chatInput || !lastReportId) return;
        const text = String(chatInput.value || "").trim();
        if (!text) return;
        appendChatBubble("user", text, "You");
        chatInput.value = "";
        if (chatSend) chatSend.disabled = true;
        fetch("/api/chat", {
            method: "POST",
            headers: Object.assign(
                { "Content-Type": "application/json" },
                csrfToken ? { "X-CSRF-Token": csrfToken } : {}
            ),
            body: JSON.stringify({ report_id: lastReportId, message: text })
        })
            .then(function (res) {
                return res.json().then(function (json) {
                    if (!res.ok || !json.success) throw new Error(json.error || "Chat failed.");
                    return json;
                });
            })
            .then(function (json) {
                const meta = json.source === "ai" ? "Guru · AI" : "Guru · rules";
                appendChatBubble("guru", json.reply || "", meta);
            })
            .catch(function (err) {
                appendChatBubble("guru", err.message || "Unable to reach Guru.", "Guru");
            })
            .finally(function () {
                if (chatSend) chatSend.disabled = false;
            });
    }

    // ============================================
    // FORM SUBMISSION
    // ============================================

    function submitAnalysis() {
        if (busy) return;
        syncHiddenBirthDate();
        if (!validateRequired()) {
            onlyStep(step1, 1);
            return;
        }
        if (palmEnabled && palmEnabled.value === "yes" && handChoice && !handChoice.value) {
            showError("Please choose left or right hand for palm reading.");
            onlyStep(step3, 3);
            return;
        }

        busy = true;
        clearError();
        onlyStep(processing, 4);
        startProgress();

        fetch("/api/analyze", {
            method: "POST",
            headers: csrfToken ? { "X-CSRF-Token": csrfToken } : {},
            body: new FormData(form)
        })
            .then(function (res) {
                return res.json().then(function (json) {
                    if (!res.ok || !json.success) throw new Error(json.error || "Request failed.");
                    return json;
                });
            })
            .then(function (data) {
                finishProgress();
                setTimeout(function () {
                    if (processing) processing.classList.add("hidden");
                    try {
                        _playKundliAnimation(data, function () {
                            renderResults(data);
                            onlyStep(results, 4);
                        });
                    } catch (animErr) {
                        console.error("Animation error:", animErr);
                        renderResults(data);
                        onlyStep(results, 4);
                    }
                }, 320);
            })
            .catch(function (err) {
                resetProgress();
                showError(err.message || "Something went wrong.");
                onlyStep(step1, 1);
            })
            .finally(function () {
                busy = false;
            });
    }

    // ============================================
    // EVENT LISTENERS — STEPS
    // ============================================

    if (goStep2) {
        goStep2.addEventListener("click", function () {
            if (!validateRequired()) return;
            onlyStep(step2, 2);
        });
    }

    if (palmYes) {
        palmYes.addEventListener("click", function () {
            if (palmEnabled) palmEnabled.value = "yes";
            onlyStep(step3, 3);
        });
    }

    if (palmNo) {
        palmNo.addEventListener("click", function () {
            if (palmEnabled) palmEnabled.value = "no";
            // Reset palm fields
            if (form.elements.hand_choice) form.elements.hand_choice.value = "";
            const palmImageInput = form.elements.palm_image;
            if (palmImageInput) palmImageInput.value = "";
            // Skip palm step and submit directly
            submitAnalysis();
        });
    }

    if (submitBtn) {
        submitBtn.addEventListener("click", function () {
            submitAnalysis();
        });
    }

    if (downloadPdf) {
        downloadPdf.addEventListener("click", function () {
            // Use browser print as PDF export (no server-side PDF route needed)
            window.print();
        });
    }

    if (tryAgain) {
        tryAgain.addEventListener("click", function () {
            form.reset();
            if (palmEnabled) palmEnabled.value = "no";
            if (birthDateHidden) birthDateHidden.value = "";
            if (birthYear) birthYear.value = "";
            if (birthMonth) birthMonth.value = "";
            if (birthDay) birthDay.innerHTML = '<option value="">Day</option>';
            clearPlaceSelection();
            hidePlaceDropdown();
            clearError();
            var kundliAnimReset = document.getElementById("kundliAnimation");
            if (kundliAnimReset) { kundliAnimReset.classList.add("hidden"); kundliAnimReset.classList.remove("active"); }
            resetProgress();
            if (reportPrintBlock) reportPrintBlock.innerHTML = "";
            if (chatLog) chatLog.innerHTML = "";
            lastReportId = null;
            onlyStep(step1, 1);
        });
    }

    // ============================================
    // EVENT LISTENERS — CHAT
    // ============================================

    if (chatSend) {
        chatSend.addEventListener("click", sendChat);
    }
    if (chatInput) {
        chatInput.addEventListener("keydown", function (e) {
            if (e.key === "Enter") {
                e.preventDefault();
                sendChat();
            }
        });
    }

    // ============================================
    // FORM SUBMIT PREVENT DEFAULT
    // ============================================

    if (form) {
        form.addEventListener("submit", function (event) {
            event.preventDefault();
        });
    }

    // ============================================
    // FLOATING CHAT WIDGET
    // ============================================

    const floatingChatWidget = document.getElementById("floatingChatWidget");
    const floatingChatToggle = document.getElementById("floatingChatToggle");
    const floatingChatInput = document.getElementById("floatingChatInput");
    const floatingChatSend = document.getElementById("floatingChatSend");
    const floatingChatMessages = document.getElementById("floatingChatMessages");

    if (floatingChatToggle) {
        floatingChatToggle.addEventListener("click", function () {
            if (floatingChatWidget) floatingChatWidget.classList.add("active");
            floatingChatToggle.style.display = "none";
            if (floatingChatInput) floatingChatInput.focus();
        });
    }

    function sendFloatingChat() {
        if (!floatingChatInput || !floatingChatMessages) return;
        const message = floatingChatInput.value.trim();
        if (!message) return;

        // Add user message
        const userMsg = document.createElement("div");
        userMsg.className = "floating-chat-message user-msg";
        userMsg.innerHTML = "<p>" + escapeHtml(message) + "</p>";
        floatingChatMessages.appendChild(userMsg);

        floatingChatInput.value = "";

        // Add loading indicator
        const loadingMsg = document.createElement("div");
        loadingMsg.className = "floating-chat-message";
        loadingMsg.innerHTML = '<div style="color: var(--neo-cyan); padding: 0.8rem;">thinking...</div>';
        floatingChatMessages.appendChild(loadingMsg);
        floatingChatMessages.scrollTop = floatingChatMessages.scrollHeight;

        // Use lastReportId if a chart has been generated
        const reportId = lastReportId || null;

        if (!reportId) {
            loadingMsg.remove();
            const noReport = document.createElement("div");
            noReport.className = "floating-chat-message guru-msg";
            noReport.innerHTML = "<p>🔮 Please complete your birth chart reading first, then I can answer your questions based on your chart!</p>";
            floatingChatMessages.appendChild(noReport);
            floatingChatMessages.scrollTop = floatingChatMessages.scrollHeight;
            return;
        }

        fetch("/api/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRF-Token": csrfToken || ""
            },
            body: JSON.stringify({
                report_id: reportId,
                message: message
            })
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                loadingMsg.remove();
                // API returns data.reply (not data.guru_response)
                if (data && data.success && data.reply) {
                    const guruMsg = document.createElement("div");
                    guruMsg.className = "floating-chat-message guru-msg";
                    guruMsg.innerHTML = "<p>" + escapeHtml(data.reply) + "</p>";
                    floatingChatMessages.appendChild(guruMsg);
                } else {
                    const errorMsg = document.createElement("div");
                    errorMsg.className = "floating-chat-message guru-msg";
                    const errText = (data && data.error) || "Unable to respond. Please check your chart.";
                    errorMsg.innerHTML = "<p>⚠️ " + escapeHtml(errText) + "</p>";
                    floatingChatMessages.appendChild(errorMsg);
                }
                floatingChatMessages.scrollTop = floatingChatMessages.scrollHeight;
            })
            .catch(function (err) {
                console.error("Floating chat error:", err);
                loadingMsg.remove();
                const errorMsg = document.createElement("div");
                errorMsg.className = "floating-chat-message guru-msg";
                errorMsg.innerHTML = "<p>⚠️ Connection error. Please try again.</p>";
                floatingChatMessages.appendChild(errorMsg);
                floatingChatMessages.scrollTop = floatingChatMessages.scrollHeight;
            });
    }

    if (floatingChatSend) {
        floatingChatSend.addEventListener("click", sendFloatingChat);
    }

    if (floatingChatInput) {
        floatingChatInput.addEventListener("keypress", function (e) {
            if (e.key === "Enter") {
                e.preventDefault();
                sendFloatingChat();
            }
        });
    }

    // ============================================
    // INITIALIZE
    // ============================================

    fetchChatHint();
    fetchCsrfToken();
    initDobSelectors();
    onlyStep(step1, 1);
});
