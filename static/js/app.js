/**
 * Celestial Arc — step flow, manual DOB validation,
 * API call, blueprint chips, and rich report rendering.
 */

function escapeHtml(value) {
    return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

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
    let placeAbortCtrl = null;
    const placeCache = new Map();   // query → results (LRU, max 32)

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
                        "Offline Guru: rule-based guidance from your saved reading.";
                }
            })
            .catch(function () {
                if (chatHint) {
                    chatHint.textContent = "Ask about Rahu/Ketu, marriage, career, dasha, or remedies.";
                }
            });
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

    function showPlaceLoading() {
        if (!placeDropdown) return;
        placeDropdown.innerHTML =
            '<div class="neo-option neo-option-loading" style="pointer-events:none;display:flex;align-items:center;gap:10px;color:rgba(200,180,255,0.75);font-style:italic;font-size:0.85em;">'
            + '<span class="place-spinner" style="display:inline-block;width:14px;height:14px;border:2px solid rgba(180,140,255,0.35);border-top-color:#b57bee;border-radius:50%;animation:placeSpin 0.7s linear infinite;flex-shrink:0;"></span>'
            + 'Loading your place…</div>';
        placeDropdown.classList.remove("hidden");
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

    // Country priority: South Asia first, then rest of world, then US/Mexico last
    var _COUNTRY_PRIORITY = {
        "India": 0, "Nepal": 1, "Sri Lanka": 1, "Bangladesh": 1, "Pakistan": 1,
        "Bhutan": 1, "Maldives": 1, "Afghanistan": 2
    };
    function _countryScore(country) {
        if (_COUNTRY_PRIORITY.hasOwnProperty(country)) return _COUNTRY_PRIORITY[country];
        // US and Mexico pushed to bottom
        if (country === "United States" || country === "Mexico" || country === "Canada") return 99;
        return 50;
    }

    function _parseOpenMeteoResults(data) {
        var raw = (data && data.results) || [];
        var places = [];
        for (var i = 0; i < raw.length; i++) {
            var res = raw[i];
            var lat = res.latitude, lon = res.longitude;
            if (lat == null || lon == null) continue;
            var country = res.country || "";
            var parts = [res.name || "", res.admin1 || "", country].filter(function(p) { return p && p.trim(); });
            var seen = {};
            var unique = parts.filter(function(p) { if (seen[p]) return false; seen[p] = true; return true; });
            var label = unique.join(", ").substring(0, 140);
            if (!label) continue;
            places.push({ label: label, lat: parseFloat(lat), lon: parseFloat(lon), tz: res.timezone || "", _score: _countryScore(country) });
        }
        // Sort: India/South-Asia first, then global, then US/Mexico last
        places.sort(function(a, b) { return a._score - b._score; });
        // Take top 5 only
        return places.slice(0, 5).map(function(p) { return { label: p.label, lat: p.lat, lon: p.lon, tz: p.tz }; });
    }

    function _cachePlaces(q, places) {
        if (placeCache.size >= 32) {
            placeCache.delete(placeCache.keys().next().value);
        }
        placeCache.set(q, places);
    }

    function fetchPlaceSuggestions(query) {
        var q = String(query || "").trim();
        if (!q || q.length < 2) {
            hidePlaceDropdown();
            return;
        }
        lastPlaceQuery = q;

        // Instant hit from cache
        if (placeCache.has(q)) {
            showPlaceDropdown(placeCache.get(q));
            return;
        }

        clearTimeout(placeTimeout);
        // Show loading immediately (before debounce fires)
        showPlaceLoading();
        placeTimeout = setTimeout(function () {
            // Abort any in-flight request
            if (placeAbortCtrl) placeAbortCtrl.abort();
            placeAbortCtrl = new AbortController();
            var sig = placeAbortCtrl.signal;

            // Primary: Open-Meteo geocoding API
            var directUrl = "https://geocoding-api.open-meteo.com/v1/search?name="
                + encodeURIComponent(q) + "&count=15&language=en&format=json";

            // Fallback 1: Nominatim (OpenStreetMap) - better for small Indian towns
            function tryNominatim() {
                var nominatimUrl = "https://nominatim.openstreetmap.org/search?q="
                    + encodeURIComponent(q) + "&format=json&limit=8&addressdetails=1";
                return fetch(nominatimUrl, { signal: sig, headers: { "Accept-Language": "en" } })
                    .then(function (r) { return r.json(); })
                    .then(function (data) {
                        if (lastPlaceQuery !== q) return;
                        if (!data || !data.length) { hidePlaceDropdown(); return; }
                        var places = data.slice(0, 5).map(function (item) {
                            var parts = [];
                            if (item.address) {
                                var a = item.address;
                                var city = a.city || a.town || a.village || a.county || "";
                                var state = a.state || "";
                                var country = a.country || "";
                                [city, state, country].forEach(function (p) {
                                    if (p && p.trim()) parts.push(p.trim());
                                });
                            }
                            var seen = {};
                            var unique = parts.filter(function (p) { if (seen[p]) return false; seen[p] = true; return true; });
                            var label = unique.join(", ") || item.display_name || "";
                            return { label: label.substring(0, 140), lat: parseFloat(item.lat), lon: parseFloat(item.lon), tz: "" };
                        }).filter(function (p) { return p.label; });
                        _cachePlaces(q, places);
                        showPlaceDropdown(places);
                    });
            }

            fetch(directUrl, { signal: sig })
                .then(function (r) {
                    if (!r.ok) throw new Error("HTTP " + r.status);
                    return r.json();
                })
                .then(function (data) {
                    if (lastPlaceQuery !== q) return;
                    var places = _parseOpenMeteoResults(data);
                    if (places.length) {
                        _cachePlaces(q, places);
                        showPlaceDropdown(places);
                    } else {
                        // Open-Meteo found nothing - try Nominatim
                        return tryNominatim().catch(function () {
                            return fetch("/api/places?q=" + encodeURIComponent(q), { signal: sig })
                                .then(function (r) { return r.json(); })
                                .then(function (d) {
                                    if (lastPlaceQuery !== q) return;
                                    var ps = (d && d.places) || [];
                                    _cachePlaces(q, ps);
                                    showPlaceDropdown(ps);
                                });
                        });
                    }
                })
                .catch(function (err) {
                    if (err && err.name === "AbortError") return;
                    // Open-Meteo failed - try Nominatim, then backend
                    tryNominatim().catch(function () {
                        fetch("/api/places?q=" + encodeURIComponent(q), { signal: sig })
                            .then(function (r) { return r.json(); })
                            .then(function (data) {
                                if (lastPlaceQuery !== q) return;
                                var places = (data && data.places) || [];
                                _cachePlaces(q, places);
                                showPlaceDropdown(places);
                            })
                            .catch(function (err2) {
                                if (err2 && err2.name === "AbortError") return;
                                hidePlaceDropdown();
                            });
                    });
                });
        }, 200);
    }

    if (birthPlace) {
        birthPlace.addEventListener("input", function () {
            clearPlaceSelection();
            fetchPlaceSuggestions(this.value);
        });
        birthPlace.addEventListener("blur", function () {
            setTimeout(hidePlaceDropdown, 220);
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
        // User MUST pick a suggestion from the dropdown (sets lat/lon)
        if (!placeLat || !placeLat.value || !placeLon || !placeLon.value) {
            showError("Please pick a place from the suggestions dropdown for accurate results.");
            if (birthPlace) birthPlace.focus();
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

        var cleanBody = (body || "").replace(/\n/g, ' ').replace(/\*/g, '');
        var sentences = cleanBody.match(/[^.!?]+[.!?]+/g) || [cleanBody];
        var bulletsHtml = '<ul class="mt-4 space-y-2 text-sm text-purple-200/80 leading-relaxed list-disc pl-5" style="list-style-position:outside">';
        for (var i = 0; i < Math.min(sentences.length, 4); i++) {
            var s = sentences[i].trim();
            if (s.length > 5) {
                bulletsHtml += '<li>' + escapeHtml(s) + '</li>';
            }
        }
        bulletsHtml += '</ul>';

        return (
            '<div class="report-card reveal-hidden flex flex-col h-full bg-purple-950/20 border border-purple-500/30 p-6 rounded-2xl">' +
            '<div class="flex items-center gap-3 mb-2">' +
            '<span class="text-2xl pt-1">' + (icon || "✦") + "</span>" +
            '<h3 class="font-display font-bold text-lg m-0">' + escapeHtml(title) + "</h3>" +
            "</div>" +
            bulletsHtml +
            '<div class="mt-auto pt-6">' +
            '<div class="reading-intensity mb-3"><span class="text-xs uppercase tracking-widest text-purple-300/75 font-semibold">Cosmic Intensity</span>' +
            '<div class="h-1 bg-purple-950/40 rounded-full mt-1 overflow-hidden"><div class="h-full bg-gradient-to-r from-purple-500 to-cyan-500 transition-all duration-1000 reading-intensity-fill" data-target="' + intensity + '%"></div></div></div>' +
            '<button type="button" class="reading-ask-cta text-xs px-4 py-1.5 rounded-full border border-purple-500/30 bg-purple-500/10 text-purple-200/90 hover:bg-purple-500/20 hover:text-white transition-colors" data-topic="' + escapeHtml(title) + '">✨ Ask Guru</button>' +
            "</div>" +
            "</div>"
        );
    }

    function renderResults(data) {
        ["ca-dasha-section", "ca-panchanga-section", "ca-ashtakavarga-section", "vedicInfoBanner"]
            .forEach(function (id) {
                var el = document.getElementById(id);
                if (el) el.remove();
            });

        const profile = data.profile || {};
        const bp = data.blueprint || {};
        var westernSign = profile.western_zodiac || "";

        if (resultTitle) resultTitle.textContent = (profile.zodiac || "") + " · Your Cosmic Brief";
        if (resultMeta) {
            var metaText = "Vedic Sun " + (profile.zodiac || "—") +
                " · Moon " + (profile.moon_sign || "—") +
                " · Asc " + (profile.ascendant || "—");
            if (westernSign && westernSign !== profile.zodiac) {
                metaText += "  ·  Western Sun " + westernSign;
            }
            resultMeta.textContent = metaText;
        }

        // Vedic system info banner — injected after resultMeta
        var existingBanner = document.getElementById("vedicInfoBanner");
        if (existingBanner) existingBanner.remove();
        if (resultMeta && resultMeta.parentNode) {
            var banner = document.createElement("div");
            banner.id = "vedicInfoBanner";
            banner.className = "mt-4 rounded-xl border border-purple-500/25 bg-purple-950/30 px-4 py-3 flex items-start gap-3";
            var bannerNote = westernSign && westernSign !== profile.zodiac
                ? " Your Western sign is <strong>" + escapeHtml(westernSign) + "</strong> (Tropical)."
                : "";
            banner.innerHTML =
                '<span class="text-lg mt-0.5">🔮</span>' +
                '<p class="text-xs text-purple-200/80 leading-relaxed">' +
                '<strong class="text-purple-100">Lahiri Sidereal (Vedic) Reading</strong> — ' +
                'Your Vedic Sun sign is <strong>' + escapeHtml(profile.zodiac || "—") + '</strong> (Lahiri Ayanamsa). ' +
                bannerNote +
                ' Both systems are valid — Vedic astrology aligns with the fixed star positions.' +
                '</p>';
            resultMeta.parentNode.insertBefore(banner, resultMeta.nextSibling);
        }

        if (profileCards) {
            // Build zodiac card with both systems
            var zodiacValue = (profile.zodiac || "—") + " (Vedic)";
            var zodiacExtra = "";
            if (westernSign) {
                zodiacExtra = '<p class="text-xs text-purple-300/70 mt-1">' +
                    'Western: ' + escapeHtml(westernSign) + ' (Tropical)</p>';
            }

            function profileCardHtml(label, value, extra) {
                return (
                    '<div class="profile-card">' +
                    '<p class="profile-label">' + escapeHtml(label) + '</p>' +
                    '<p class="profile-value">' + escapeHtml(value) + '</p>' +
                    (extra || "") +
                    "</div>"
                );
            }

            if (bp && bp.element) {
                profileCards.innerHTML = [
                    { l: "Sun Sign", v: zodiacValue, x: zodiacExtra },
                    { l: "Moon Sign", v: profile.moon_sign || "—", x: "" },
                    { l: "Ascendant (Lagna)", v: profile.ascendant || "—", x: "" },
                    { l: "Element · Modality", v: (bp.element || "—") + " · " + (bp.modality || "—"), x: "" },
                    { l: "Ruling Planet", v: bp.ruling_planet || "—", x: "" },
                    { l: "Energy Focus", v: bp.energy_focus || "—", x: "" }
                ].map(function(c) {
                    return '<div class="profile-card">' +
                        '<p class="profile-label">' + escapeHtml(c.l) + '</p>' +
                        '<p class="profile-value">' + escapeHtml(c.v) + '</p>' +
                        c.x + '</div>';
                }).join("");
            } else {
                profileCards.innerHTML = [
                    { l: "Sun Sign", v: zodiacValue, x: zodiacExtra },
                    { l: "Moon Sign", v: profile.moon_sign || "Unknown", x: "" },
                    { l: "Ascendant", v: profile.ascendant || "Unknown", x: "" }
                ].map(function(c) {
                    return '<div class="profile-card">' +
                        '<p class="profile-label">' + escapeHtml(c.l) + '</p>' +
                        '<p class="profile-value">' + escapeHtml(c.v) + '</p>' +
                        c.x + '</div>';
                }).join("");
            }
        }

        if (blueprintChips) {
            var luckyChipDefs = [
                { icon: "🔢", label: "Lucky number", key: "lucky_number" },
                { icon: "📅", label: "Lucky day",    key: "lucky_day" },
                { icon: "🎨", label: "Lucky colors", key: "lucky_color" },
                { icon: "⭐", label: "Best signs",   key: "best_matches" },
                { icon: "🌱", label: "Growth signs", key: "growth_signs" }
            ];
            var dashaBp = data.dasha || {};
            var curBp   = dashaBp.current || {};
            var panchBp = data.panchanga || {};

            function luckyChip(icon, label, value) {
                if (!value || value === "—") return "";
                return "<span class=\"ca-lucky-chip\">" +
                    "<span class=\"ca-lucky-chip-icon\">" + icon + "</span>" +
                    "<span class=\"ca-lucky-chip-label\">" + escapeHtml(label) + "</span>" +
                    "<span class=\"ca-lucky-chip-value\">" + escapeHtml(String(value)) + "</span>" +
                    "</span>";
            }

            var chipsHtml = "";
            luckyChipDefs.forEach(function(def) {
                var raw = bp[def.key];
                if (raw != null && raw !== "") {
                    chipsHtml += luckyChip(def.icon, def.label, String(raw));
                }
            });
            if (curBp.mahadasha) {
                chipsHtml += luckyChip("🪐", "Mahadasha", curBp.mahadasha + " (until " + (curBp.mahadasha_ends || "—") + ")");
            }
            if (panchBp.nakshatra && panchBp.nakshatra.name) {
                chipsHtml += luckyChip("🌙", "Birth nakshatra", panchBp.nakshatra.name + " Pada " + (panchBp.nakshatra.pada || ""));
            }
            if (panchBp.yoga && panchBp.yoga.name) {
                chipsHtml += luckyChip("✨", "Birth yoga", panchBp.yoga.name + " (" + (panchBp.yoga.quality || "") + ")");
            }
            blueprintChips.innerHTML = "<div class=\"ca-lucky-grid\">" + chipsHtml + "</div>";
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

        try {
            _renderAtAGlanceCard(data);
            _renderDashaSection(data.dasha);
            _renderPanchangaSection(data.panchanga);
            _renderAshtakavargaSection(data.ashtakavarga, (data.profile || {}).ascendant);
        } catch (featureErr) {
            console.error("Feature section render error:", featureErr);
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
            kundliChartDiv.querySelectorAll(".chart-line").forEach(function (el) {
                el.style.strokeDashoffset = "0";
            });
            kundliChartDiv.querySelectorAll(".kundli-house-num-text, .kundli-sign-label, .kundli-planet-glyph").forEach(function (el) {
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
        { id: 1, pts: "250,50 350,150 250,250 150,150", cx: 250, cy: 150 },
        { id: 2, pts: "250,50 450,50 350,150", cx: 350, cy: 83 },
        { id: 3, pts: "450,50 450,250 350,150", cx: 417, cy: 150 },
        { id: 4, pts: "350,150 450,250 350,350 250,250", cx: 350, cy: 250 },
        { id: 5, pts: "450,250 450,450 350,350", cx: 417, cy: 350 },
        { id: 6, pts: "450,450 250,450 350,350", cx: 350, cy: 417 },
        { id: 7, pts: "350,350 250,450 150,350 250,250", cx: 250, cy: 350 },
        { id: 8, pts: "250,450 50,450 150,350", cx: 150, cy: 417 },
        { id: 9, pts: "50,450 50,250 150,350", cx: 83, cy: 350 },
        { id: 10, pts: "150,350 50,250 150,150 250,250", cx: 150, cy: 250 },
        { id: 11, pts: "50,250 50,50 150,150", cx: 83, cy: 150 },
        { id: 12, pts: "50,50 250,50 150,150", cx: 150, cy: 83 }
    ];

    var _HOUSE_MEANINGS = {
        1: "Self, Identity & Life Path", 2: "Wealth, Speech & Family",
        3: "Courage, Siblings & Skills", 4: "Home, Mother & Inner Peace",
        5: "Creativity, Children & Romance", 6: "Health, Service & Competition",
        7: "Marriage, Partnerships & Desires", 8: "Transformation & Hidden Forces",
        9: "Fortune, Wisdom & Higher Truth", 10: "Career, Status & Public Life",
        11: "Gains, Aspirations & Networks", 12: "Liberation, Dreams & Solitude"
    };

    var _PLANET_GLYPHS = { sun: "\u2609", moon: "\u263D", mars: "\u2642", mercury: "\u263F", venus: "\u2640", jupiter: "\u2643", saturn: "\u2644", rahu: "\u260A", ketu: "\u260B" };
    var _PLANET_NAMES = { sun: "Sun", moon: "Moon", mars: "Mars", mercury: "Mercury", venus: "Venus", jupiter: "Jupiter", saturn: "Saturn", rahu: "Rahu", ketu: "Ketu" };
    var _ZODIAC_LIST = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"];
    var _ZODIAC_GLYPHS = { Aries: "\u2648", Taurus: "\u2649", Gemini: "\u264A", Cancer: "\u264B", Leo: "\u264C", Virgo: "\u264D", Libra: "\u264E", Scorpio: "\u264F", Sagittarius: "\u2650", Capricorn: "\u2651", Aquarius: "\u2652", Pisces: "\u2653" };

    function _invertHouseMap(houses) {
        var r = {}; for (var h = 1; h <= 12; h++) r[h] = [];
        if (!houses) return r;
        Object.keys(houses).forEach(function (p) { var hh = houses[p]; if (r[hh]) r[hh].push(p); });
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
        var blur = document.createElementNS(ns, "feGaussianBlur"); blur.setAttribute("stdDeviation", "3"); blur.setAttribute("result", "g");
        var merge = document.createElementNS(ns, "feMerge");
        var mn1 = document.createElementNS(ns, "feMergeNode"); mn1.setAttribute("in", "g");
        var mn2 = document.createElementNS(ns, "feMergeNode"); mn2.setAttribute("in", "SourceGraphic");
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
        [[50, 50, 250, 250], [450, 50, 250, 250], [450, 450, 250, 250], [50, 450, 250, 250]].forEach(function (d) {
            var ln = document.createElementNS(ns, "line");
            ln.setAttribute("x1", d[0]); ln.setAttribute("y1", d[1]);
            ln.setAttribute("x2", d[2]); ln.setAttribute("y2", d[3]);
            ln.setAttribute("class", "chart-line chart-diag");
            var len = Math.ceil(Math.sqrt(Math.pow(d[2] - d[0], 2) + Math.pow(d[3] - d[1], 2)));
            ln.style.strokeDasharray = len; ln.style.strokeDashoffset = len;
            svg.appendChild(ln);
        });

        // House polygons
        _KUNDLI_HOUSES.forEach(function (h) {
            var poly = document.createElementNS(ns, "polygon");
            poly.setAttribute("points", h.pts);
            poly.setAttribute("class", "kundli-house-poly");
            poly.setAttribute("data-house", h.id);
            svg.appendChild(poly);
        });

        // House numbers
        _KUNDLI_HOUSES.forEach(function (h) {
            var t = document.createElementNS(ns, "text");
            t.setAttribute("x", h.cx); t.setAttribute("y", h.cy - 14);
            t.setAttribute("class", "kundli-house-num-text"); t.setAttribute("data-house", h.id);
            t.textContent = String(h.id); svg.appendChild(t);
        });

        // Zodiac sign glyphs
        _KUNDLI_HOUSES.forEach(function (h) {
            var sign = _signForHouse(h.id, asc);
            var t = document.createElementNS(ns, "text");
            t.setAttribute("x", h.cx); t.setAttribute("y", h.cy + 2);
            t.setAttribute("class", "kundli-sign-label"); t.setAttribute("data-house", h.id);
            t.textContent = _ZODIAC_GLYPHS[sign] || sign.substring(0, 3); svg.appendChild(t);
        });

        // Planet glyphs
        _KUNDLI_HOUSES.forEach(function (h) {
            var planets = hpMap[h.id] || [];
            planets.forEach(function (p, idx) {
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
            s.style.left = Math.random() * 100 + "%"; s.style.top = Math.random() * 100 + "%";
            s.style.setProperty("--dur", (2 + Math.random() * 4) + "s");
            s.style.animationDelay = Math.random() * 3 + "s";
            var sz = (1 + Math.random() * 2) + "px"; s.style.width = sz; s.style.height = sz;
            container.appendChild(s);
        }
    }

    async function _playKundliAnimation(chartData, doneCallback) {
        var anim = document.getElementById("kundliAnimation");
        if (!anim) {
            if (doneCallback) doneCallback();
            return;
        }
        var stars = document.getElementById("kundliStars");
        var grid = document.getElementById("kundliGrid");
        var portal = document.getElementById("kundliPortal");
        var chartArea = document.getElementById("kundliChartArea");
        var infoPnl = document.getElementById("kundliInfoPanel");
        var statusTxt = document.getElementById("kundliStatusText");
        var progFill = document.getElementById("kundliProgressFill");
        var completeOv = document.getElementById("kundliComplete");
        var skipBtn = document.getElementById("kundliSkip");
        if (!chartArea) {
            if (doneCallback) doneCallback();
            return;
        }

        var skipped = false;
        function doSkip() { skipped = true; }
        if (skipBtn) skipBtn.addEventListener("click", doSkip);

        function wait(ms) {
            if (skipped) return Promise.resolve();
            return new Promise(function (r) { setTimeout(r, ms); });
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
        svg.querySelectorAll(".kundli-house-num-text").forEach(function (el) { el.classList.add("visible"); });
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
            svg.querySelectorAll(".kundli-house-poly.scanning").forEach(function (el) {
                el.classList.remove("scanning"); el.classList.add("scanned");
            });
            if (poly) poly.classList.add("scanning");

            // Highlight house number
            svg.querySelectorAll(".kundli-house-num-text.active").forEach(function (el) { el.classList.remove("active"); });
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
                    chip.innerHTML = '<span class="kundli-info-chip-glyph">' + escapeHtml(_PLANET_GLYPHS[pl] || "?") + "</span> " + escapeHtml(_PLANET_NAMES[pl] || pl);
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
        svg.querySelectorAll(".kundli-house-poly.scanning").forEach(function (el) {
            el.classList.remove("scanning"); el.classList.add("scanned");
        });
        svg.querySelectorAll(".kundli-house-num-text").forEach(function (el) { el.classList.remove("active"); });
        svg.querySelectorAll(".kundli-sign-label, .kundli-planet-glyph").forEach(function (el) { el.classList.add("visible"); });

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
            setTimeout(function () {
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
        cards.forEach(function (card, idx) {
            if (idx < autoCount) {
                setTimeout(function () {
                    card.classList.remove("reveal-hidden");
                    card.classList.add("reveal-visible");
                    card.querySelectorAll(".reading-intensity-fill").forEach(function (bar) {
                        var t = bar.getAttribute("data-target") || "50%";
                        setTimeout(function () { bar.style.width = t; }, 200);
                    });
                }, idx * 350);
            }
        });
        if ("IntersectionObserver" in window) {
            var obs = new IntersectionObserver(function (entries) {
                entries.forEach(function (entry) {
                    if (entry.isIntersecting) {
                        entry.target.classList.remove("reveal-hidden");
                        entry.target.classList.add("reveal-visible");
                        entry.target.querySelectorAll(".reading-intensity-fill").forEach(function (bar) {
                            var t = bar.getAttribute("data-target") || "50%";
                            setTimeout(function () { bar.style.width = t; }, 200);
                        });
                        obs.unobserve(entry.target);
                    }
                });
            }, { threshold: 0.12 });
            cards.forEach(function (card, idx) {
                if (idx >= autoCount) obs.observe(card);
            });
        } else {
            cards.forEach(function (card) {
                card.classList.remove("reveal-hidden");
                card.classList.add("reveal-visible");
            });
        }
    }

    // Ask Guru CTA delegation
    if (reportSections) {
        reportSections.addEventListener("click", function (e) {
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

    function appendChatLoader(isSimple) {
        if (!chatLog) return null;
        const wrap = document.createElement("div");
        wrap.className = "chat-bubble chat-bubble-guru chat-loader-active";
        wrap.id = "activeChatLoader";

        const m = document.createElement("div");
        m.className = "chat-meta";
        m.textContent = "Guru \u00b7 thinking";
        wrap.appendChild(m);

        const body = document.createElement("div");
        body.className = "loader-text";
        
        if (isSimple) {
            body.innerHTML = "<span class='spinner'>\u2727</span> <span id='loaderMsg'>Guru is typing...</span>";
            wrap.appendChild(body);
            chatLog.appendChild(wrap);
            chatLog.scrollTop = chatLog.scrollHeight;
            return { wrap: wrap, interval: null };
        }
        
        body.innerHTML = "<span class='spinner'>\u2727</span> <span id='loaderMsg'>Guru is reading your kundli...</span>";
        wrap.appendChild(body);

        chatLog.appendChild(wrap);
        chatLog.scrollTop = chatLog.scrollHeight;

        const msgs = [
            "Guru is reading your kundli...",
            "Analyzing planetary dashas...",
            "Checking house lords...",
            "Aligning sidereal positions...",
            "Finding karmic patterns...",
            "Interpreting nakshatras...",
            "Consulting the stars...",
            "Formulating deep insights...",
            "Almost done..."
        ];
        let i = 0;
        const interval = setInterval(function () {
            const msgEl = document.getElementById("loaderMsg");
            if (msgEl) {
                if (i < msgs.length - 1) {
                    i++;
                }
                msgEl.textContent = msgs[i];
            } else {
                clearInterval(interval);
            }
        }, 1800);

        return { wrap: wrap, interval: interval };
    }

    function sendChat() {
        if (!chatInput || !lastReportId) return;
        const text = String(chatInput.value || "").trim();
        if (!text) return;
        appendChatBubble("user", text, "You");
        chatInput.value = "";
        if (chatSend) chatSend.disabled = true;

        const lowerText = text.toLowerCase();
        const isSimple = /^(hi|hello|hey|namaste|kaise ho|hii+|helo|hola|sup|good morning|good evening|good afternoon)\b/.test(lowerText) && text.length < 25;
        const loader = appendChatLoader(isSimple);

        const token = localStorage.getItem('celestial_token');
        const headers = Object.assign(
            { "Content-Type": "application/json" },
            csrfToken ? { "X-CSRF-Token": csrfToken } : {}
        );
        if (token) {
            headers["Authorization"] = "Bearer " + token;
        }

        fetch("/api/chat", {
            method: "POST",
            headers: headers,
            body: JSON.stringify({ report_id: lastReportId, message: text })
        })
            .then(function (res) {
                return res.json().then(function (json) {
                    if (!res.ok || !json.success) throw new Error(json.error || "Chat failed.");
                    return json;
                });
            })
            .then(function (json) {
                if (loader) {
                    clearInterval(loader.interval);
                    if (loader.wrap.parentNode) loader.wrap.parentNode.removeChild(loader.wrap);
                }
                const meta = json.source === "ai" ? "Guru \u00b7 AI" : "Guru \u00b7 rules";
                appendChatBubble("guru", json.reply || "", meta);
            })
            .catch(function (err) {
                if (loader) {
                    clearInterval(loader.interval);
                    if (loader.wrap.parentNode) loader.wrap.parentNode.removeChild(loader.wrap);
                }
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
        if (palmEnabled && palmEnabled.value === "yes") {
            if (handChoice && !handChoice.value) {
                showError("Please choose left or right hand for palm reading.");
                onlyStep(step3, 3);
                return;
            }
            
            const palmInput = document.getElementById("palmImage");
            if (palmInput && palmInput.files && palmInput.files.length > 0) {
                const file = palmInput.files[0];
                const validTypes = ["image/jpeg", "image/png", "image/webp"];
                
                if (!validTypes.includes(file.type)) {
                    showError("Palm image must be png, jpg, jpeg, or webp.");
                    onlyStep(step3, 3);
                    return;
                }
                
                if (file.size > 5 * 1024 * 1024) {
                    showError("Palm image is too large. Please upload an image under 5MB.");
                    onlyStep(step3, 3);
                    return;
                }
                
                if (file.size < 10 * 1024) {
                    showError("Palm image is too small. Please upload a clear photo of your palm.");
                    onlyStep(step3, 3);
                    return;
                }
            }
        }

        busy = true;
        clearError();
        onlyStep(processing, 4);
        startProgress();

        const token = localStorage.getItem('celestial_token');
        const headers = csrfToken ? { "X-CSRF-Token": csrfToken } : {};
        if (token) {
            headers["Authorization"] = "Bearer " + token;
        }

        fetch("/api/analyze", {
            method: "POST",
            headers: headers,
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
                    try {
                        renderResults(data);
                        onlyStep(results, 4);
                        if (processing) processing.classList.add("hidden");

                        var skipAnim = window.matchMedia("(max-width: 768px)").matches
                            || window.matchMedia("(prefers-reduced-motion: reduce)").matches;
                        if (!skipAnim && data.vedic && data.vedic.houses) {
                            try {
                                _playKundliAnimation(data, function () {});
                            } catch (animErr) {
                                console.warn("Kundli animation skipped:", animErr);
                            }
                        }
                    } catch (renderErr) {
                        console.error("Render error:", renderErr);
                        resetProgress();
                        if (processing) processing.classList.add("hidden");
                        showError("Your reading was created but could not be shown. Please refresh and try again.");
                        onlyStep(step1, 1);
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
    
    // Check if loading a specific report from URL
    const urlParams = new URLSearchParams(window.location.search);
    const reportParam = urlParams.get('report');
    if (reportParam) {
        busy = true;
        onlyStep(processing, 4);
        const token = localStorage.getItem('celestial_token');
        const headers = {};
        if (token) headers["Authorization"] = "Bearer " + token;
        
        fetch(`/api/reports/${reportParam}`, { headers: headers })
            .then(res => res.json())
            .then(json => {
                if (json.success && json.report) {
                    const r = json.report;
                    let extras = {};
                    try { extras = JSON.parse(r.report_extras || "{}"); } catch(e){}
                    
                    lastReportId = r.public_id || r.id || reportParam;
                    renderResults({
                        success: true,
                        report_id: lastReportId,
                        profile: {
                            zodiac: r.zodiac,
                            moon_sign: r.moon_sign,
                            ascendant: r.ascendant
                        },
                        blueprint: extras.blueprint || {},
                        vedic: extras.vedic || {},
                        sections: {
                            personality: r.personality,
                            career: r.career,
                            love: r.love_life,
                            future: r.future_outlook,
                            strengths: r.strengths,
                            weaknesses: r.weaknesses,
                            wellness: r.wellness,
                            compatibility: r.compatibility,
                            seasonal_energy: r.seasonal_energy
                        },
                        palm_analysis: r.palm_analysis,
                        report_html: r.report_html,
                        created_at: r.created_at,
                        dasha: extras.dasha || {},
                        panchanga: extras.panchanga || {},
                        ashtakavarga: extras.ashtakavarga || {}
                    });
                    onlyStep(results, 4);
                    if (processing) processing.classList.add("hidden");
                } else {
                    showError(json.error || "Report not found.");
                    onlyStep(step1, 1);
                }
            })
            .catch(err => {
                console.error(err);
                showError("Failed to load report.");
                onlyStep(step1, 1);
            })
            .finally(() => { busy = false; });
    } else {
        onlyStep(step1, 1);
    }
});

// ═══════════════════════════════════════════════════════════════════
// NEW FEATURE RENDERERS — Dasha, Panchanga, Ashtakavarga
// ═══════════════════════════════════════════════════════════════════

// ── Inject styles once ───────────────────────────────────────────────
(function _injectNewStyles() {
    if (document.getElementById("ca-new-feature-styles")) return;
    const s = document.createElement("style");
    s.id = "ca-new-feature-styles";
    s.textContent = `
        /* ── Shared card wrapper ── */
        .ca-feature-card {
            margin-top: 2rem;
            background: rgba(30,18,60,0.55);
            border: 1px solid rgba(139,92,246,0.22);
            border-radius: 1rem;
            padding: 1.5rem;
            backdrop-filter: blur(8px);
        }
        .ca-feature-heading {
            display: flex; align-items: center; gap: .6rem;
            font-size: 1.15rem; font-weight: 600; color: #e8d5ff;
            margin-bottom: 1rem; padding-bottom: .6rem;
            border-bottom: 1px solid rgba(139,92,246,0.2);
        }
        .ca-feature-heading .ca-icon { font-size: 1.3rem; }

        /* ── Dasha ── */
        .ca-dasha-current {
            background: rgba(139,92,246,0.15);
            border: 1px solid rgba(139,92,246,0.35);
            border-radius: .75rem; padding: 1rem 1.2rem; margin-bottom: 1rem;
        }
        .ca-dasha-current .ca-dasha-label {
            font-size: .7rem; letter-spacing: .12em; color: #c4b5fd;
            text-transform: uppercase; margin-bottom: .25rem;
        }
        .ca-dasha-row {
            display: flex; flex-wrap: wrap; gap: .5rem; align-items: center;
            font-size: .95rem; color: #f3f0ff;
        }
        .ca-dasha-lord {
            background: rgba(192,132,252,0.18);
            border: 1px solid rgba(192,132,252,0.35);
            border-radius: .4rem; padding: .15rem .6rem;
            font-weight: 700; color: #ddd6fe;
        }
        .ca-dasha-sep { color: rgba(192,132,252,0.5); font-size: 1.2rem; }
        .ca-dasha-end { font-size: .8rem; color: #a78bfa; margin-left:.2rem; }
        .ca-dasha-pred {
            font-size: .88rem; color: #c4b5fd; line-height: 1.55;
            margin-top: .6rem;
        }
        .ca-dasha-timeline { overflow-x: auto; }
        .ca-dasha-table {
            width: 100%; border-collapse: collapse;
            font-size: .82rem; color: #ddd6fe;
        }
        .ca-dasha-table th {
            text-align: left; padding: .4rem .7rem;
            color: #a78bfa; font-weight: 600; font-size: .72rem;
            text-transform: uppercase; letter-spacing: .08em;
            border-bottom: 1px solid rgba(139,92,246,0.25);
        }
        .ca-dasha-table td {
            padding: .4rem .7rem;
            border-bottom: 1px solid rgba(139,92,246,0.1);
        }
        .ca-dasha-table tr.ca-current-row td {
            background: rgba(139,92,246,0.12);
            color: #f3f0ff; font-weight: 600;
        }
        .ca-dasha-table .ca-cur-badge {
            display:inline-block; font-size:.65rem; padding:.1rem .4rem;
            background:rgba(192,132,252,0.25); border-radius:.3rem;
            color:#c4b5fd; margin-left:.4rem;
        }
        .ca-toggle-btn {
            margin-top: .6rem; font-size: .78rem;
            color: #a78bfa; background: none; border: none; cursor: pointer;
            padding: .2rem 0; text-decoration: underline; text-underline-offset: 3px;
        }
        .ca-antar-table { margin-top: .5rem; width: 100%; border-collapse: collapse; font-size: .8rem; color:#c4b5fd; }
        .ca-antar-table td { padding: .3rem .5rem; border-bottom: 1px solid rgba(139,92,246,0.08); }
        .ca-antar-table tr.ca-current-row td { color:#f3f0ff; font-weight:600; background:rgba(139,92,246,0.1); }

        /* ── Panchanga ── */
        .ca-panch-grid {
            display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
            gap: .7rem; margin-bottom: 1rem;
        }
        .ca-panch-cell {
            background: rgba(139,92,246,0.1);
            border: 1px solid rgba(139,92,246,0.2);
            border-radius: .6rem; padding: .7rem .9rem;
        }
        .ca-panch-cell .ca-panch-lbl {
            font-size: .68rem; color: #a78bfa; text-transform: uppercase;
            letter-spacing: .1em; margin-bottom: .2rem;
        }
        .ca-panch-cell .ca-panch-val {
            font-size: .92rem; color: #f3f0ff; font-weight: 600;
        }
        .ca-panch-cell .ca-panch-sub {
            font-size: .75rem; color: #c4b5fd; margin-top: .15rem;
        }
        .ca-timing-row {
            display: flex; flex-wrap: wrap; gap: .6rem; margin-top: .8rem;
        }
        .ca-timing-pill {
            display: flex; flex-direction: column;
            background: rgba(30,18,60,0.6);
            border: 1px solid rgba(139,92,246,0.2);
            border-radius: .6rem; padding: .5rem .9rem; font-size: .8rem;
        }
        .ca-timing-pill.ca-rahu { border-color: rgba(239,68,68,0.35); }
        .ca-timing-pill.ca-abhijit { border-color: rgba(52,211,153,0.35); }
        .ca-timing-pill .ca-tl { font-size: .68rem; color: #a78bfa; margin-bottom: .15rem; }
        .ca-timing-pill.ca-rahu .ca-tl { color: #fca5a5; }
        .ca-timing-pill.ca-abhijit .ca-tl { color: #6ee7b7; }
        .ca-timing-pill .ca-tv { color: #f3f0ff; font-weight: 600; }
        .ca-auspicious-bar {
            display: flex; align-items: center; gap: .8rem; margin-top: .8rem;
        }
        .ca-aus-track {
            flex: 1; height: 8px; background: rgba(139,92,246,0.15);
            border-radius: 99px; overflow: hidden;
        }
        .ca-aus-fill {
            height: 100%; border-radius: 99px;
            background: linear-gradient(90deg, #7c3aed, #c084fc);
            transition: width .6s ease;
        }
        .ca-aus-label { font-size: .8rem; color: #c4b5fd; white-space: nowrap; }
        .ca-aus-score { font-size: .9rem; font-weight: 700; color: #ddd6fe; }

        /* ── Ashtakavarga ── */
        .ca-sav-grid {
            display: grid; grid-template-columns: repeat(6, 1fr);
            gap: 4px; margin: .8rem 0;
        }
        @media (max-width: 500px) { .ca-sav-grid { grid-template-columns: repeat(4, 1fr); } }
        .ca-sav-cell {
            aspect-ratio: 1; display: flex; flex-direction: column;
            align-items: center; justify-content: center;
            border-radius: .4rem; font-size: .72rem;
            border: 1px solid rgba(139,92,246,0.15);
            transition: transform .15s;
        }
        .ca-sav-cell:hover { transform: scale(1.08); }
        .ca-sav-cell .ca-sav-sign { font-size: .6rem; color: #a78bfa; }
        .ca-sav-cell .ca-sav-pts { font-weight: 700; font-size: .9rem; }
        .ca-sav-strong { background: rgba(52,211,153,0.18); border-color: rgba(52,211,153,0.35); }
        .ca-sav-strong .ca-sav-pts { color: #6ee7b7; }
        .ca-sav-good { background: rgba(139,92,246,0.15); border-color: rgba(139,92,246,0.3); }
        .ca-sav-good .ca-sav-pts { color: #c4b5fd; }
        .ca-sav-avg { background: rgba(251,191,36,0.1); border-color: rgba(251,191,36,0.25); }
        .ca-sav-avg .ca-sav-pts { color: #fcd34d; }
        .ca-sav-weak { background: rgba(239,68,68,0.1); border-color: rgba(239,68,68,0.25); }
        .ca-sav-weak .ca-sav-pts { color: #fca5a5; }
        .ca-life-areas {
            display: grid; grid-template-columns: repeat(auto-fill, minmax(200px,1fr));
            gap: .6rem; margin-top: .8rem;
        }
        .ca-la-cell {
            background: rgba(139,92,246,0.08);
            border: 1px solid rgba(139,92,246,0.18);
            border-radius: .6rem; padding: .6rem .8rem;
        }
        .ca-la-header { display: flex; justify-content: space-between; align-items: center; }
        .ca-la-name { font-size: .8rem; color: #e8d5ff; font-weight: 600; }
        .ca-la-pts { font-size: .85rem; font-weight: 700; }
        .ca-la-pts.strong { color: #6ee7b7; }
        .ca-la-pts.good { color: #c4b5fd; }
        .ca-la-pts.avg { color: #fcd34d; }
        .ca-la-pts.weak { color: #fca5a5; }
        .ca-la-bar-track { height: 4px; background: rgba(139,92,246,0.15); border-radius:99px; margin:.35rem 0; }
        .ca-la-bar-fill { height: 100%; border-radius:99px; background: linear-gradient(90deg,#7c3aed,#c084fc); }
        .ca-la-pred { font-size: .72rem; color: #a78bfa; line-height: 1.45; }
    `;
    document.head.appendChild(s);
})();
// ── 0. At-a-Glance Summary Card ──────────────────────────────────────
function _renderAtAGlanceCard(data) {
    const container = document.getElementById("results");
    if (!container) return;

    const dasha  = data.dasha  || {};
    const cur    = dasha.current || {};
    const panch  = data.panchanga || {};
    const ashtak = data.ashtakavarga || {};
    const aus    = (panch.auspiciousness_score) || {};
    const strong = (ashtak.strongest_signs || []).slice(0, 2).map(s => s[0]).join(" & ");
    const maha   = cur.mahadasha || "";
    const anti   = cur.antardasha || "";

    const _DASHA_KEYWORDS = {
        "Saturn":  "discipline, endurance & hard work — shortcuts won't stick",
        "Jupiter": "wisdom, growth & big opportunities — say yes to expansion",
        "Venus":   "love, creativity & abundance — relationships take center stage",
        "Mars":    "energy, ambition & bold action — courage is rewarded",
        "Sun":     "identity, authority & confidence — step into the spotlight",
        "Moon":    "emotions, intuition & change — trust your gut",
        "Mercury": "communication, business & learning — ideas move fast",
        "Rahu":    "ambition, transformation & new paths — comfort zone is the enemy",
        "Ketu":    "spirituality, detachment & past karma — simplify to gain clarity",
    };

    const _HOUSE_SIMPLE = {
        1: "Self & Identity", 2: "Wealth & Family", 3: "Courage & Communication",
        4: "Home & Happiness", 5: "Children & Creativity", 6: "Health & Service",
        7: "Marriage & Partnerships", 8: "Hidden depths & Change", 9: "Luck & Dharma",
        10: "Career & Status", 11: "Gains & Network", 12: "Spirituality & Liberation",
    };

    const lifeAreas = ashtak.life_areas || {};
    let bestHouseNum = 0, bestHousePts = 0;
    for (let h = 1; h <= 12; h++) {
        const pts = (lifeAreas[h] || {}).points || 0;
        if (pts > bestHousePts) { bestHousePts = pts; bestHouseNum = h; }
    }
    const bestHouseName = _HOUSE_SIMPLE[bestHouseNum] || "";
    const dashaKeyword  = _DASHA_KEYWORDS[maha] || "change and growth";
    const todayLabel    = aus.label || "";
    const todayRec      = aus.recommendation || "";
    const lagna         = (data.profile || {}).ascendant || "";

    const wrap = document.createElement("div");
    wrap.className = "ca-glance-card";
    wrap.id = "ca-glance-section";

    wrap.innerHTML = `
        <div class="ca-glance-heading">⭐ Your Reading at a Glance</div>
        <div class="ca-glance-grid">
            ${maha ? `<div class="ca-glance-item">
                <div class="ca-glance-item-label">🪐 Current life chapter</div>
                <div class="ca-glance-item-value">${escapeHtml(maha)} Mahadasha${anti ? " → " + escapeHtml(anti) : ""}</div>
                <div class="ca-glance-item-sub">Theme: ${escapeHtml(dashaKeyword)}</div>
            </div>` : ""}
            ${bestHouseName ? `<div class="ca-glance-item">
                <div class="ca-glance-item-label">💪 Strongest life area</div>
                <div class="ca-glance-item-value">${escapeHtml(bestHouseName)}</div>
                <div class="ca-glance-item-sub">${bestHousePts} pts — effort here gives above-average results</div>
            </div>` : ""}
            ${strong ? `<div class="ca-glance-item">
                <div class="ca-glance-item-label">🌟 Favored energy</div>
                <div class="ca-glance-item-value">${escapeHtml(strong)}</div>
                <div class="ca-glance-item-sub">Natural planetary support flows through these signs</div>
            </div>` : ""}
            ${todayLabel ? `<div class="ca-glance-item">
                <div class="ca-glance-item-label">📅 Birth day quality</div>
                <div class="ca-glance-item-value">${escapeHtml(todayLabel)}</div>
                <div class="ca-glance-item-sub">${escapeHtml(todayRec)}</div>
            </div>` : ""}
            ${lagna ? `<div class="ca-glance-item">
                <div class="ca-glance-item-label">⬆ Ascendant (Lagna)</div>
                <div class="ca-glance-item-value">${escapeHtml(lagna)}</div>
                <div class="ca-glance-item-sub">Your outer self, body & how the world sees you</div>
            </div>` : ""}
        </div>`;

    container.appendChild(wrap);
}
// ── 1. Dasha Section ────────────────────────────────────────────────
function _renderDashaSection(dasha) {
    if (!dasha || dasha.error || !dasha.current) return;

    const cur   = dasha.current || {};
    const bb    = dasha.birth_balance || {};
    const tl    = dasha.timeline || [];

    const container = document.getElementById("results");
    if (!container) return;

    const wrap = document.createElement("div");
    wrap.className = "ca-feature-card";
    wrap.id = "ca-dasha-section";

    // Current dasha summary
    const maha  = cur.mahadasha  || "—";
    const antar = cur.antardasha || "—";
    const prat  = cur.pratyantar || "—";
    const pred  = cur.prediction || "";

    // Build timeline rows (show all mahadashas, collapse antardashas)
    let timelineHtml = "";
    tl.forEach(function(m) {
        const isCur = m.is_current;
        const id = "antar-" + m.lord.replace(/\s/g, "");
        timelineHtml += `
        <tr class="${isCur ? "ca-current-row" : ""}">
            <td><strong>${escapeHtml(m.lord)}</strong>${isCur ? '<span class="ca-cur-badge">NOW</span>' : ""}</td>
            <td>${escapeHtml(m.start_date)}</td>
            <td>${escapeHtml(m.end_date)}</td>
            <td>${(Number(m.years) || 0).toFixed(1)} yrs</td>
            <td>${m.antardashas && m.antardashas.length
                ? `<button class="ca-toggle-btn" onclick="_toggleAntar('${id}')">▶ Show sub-periods</button>`
                : ""}</td>
        </tr>
        ${m.antardashas && m.antardashas.length ? `
        <tr id="${id}" style="display:none"><td colspan="5" style="padding:0 .5rem .6rem 1.5rem">
            <table class="ca-antar-table">
                <tr><th style="color:#a78bfa;font-size:.68rem;padding:.25rem .5rem">Antardasha</th>
                    <th style="color:#a78bfa;font-size:.68rem;padding:.25rem .5rem">Start</th>
                    <th style="color:#a78bfa;font-size:.68rem;padding:.25rem .5rem">End</th>
                    <th style="color:#a78bfa;font-size:.68rem;padding:.25rem .5rem">Months</th></tr>
                ${m.antardashas.map(a => `
                <tr class="${a.is_current ? "ca-current-row" : ""}">
                    <td>${escapeHtml(a.lord)}${a.is_current ? '<span class="ca-cur-badge">NOW</span>' : ""}</td>
                    <td>${escapeHtml(a.start_date)}</td>
                    <td>${escapeHtml(a.end_date)}</td>
                    <td>${(a.months || 0).toFixed(1)}</td>
                </tr>`).join("")}
            </table>
        </td></tr>` : ""}`;
    });

    wrap.innerHTML = `
        <div class="ca-feature-heading"><span class="ca-icon">⏱</span> Vimshottari Dasha — Exact Timeline</div>
        <p style="font-size:.85rem;color:#c4b5fd;margin-bottom:.8rem">${escapeHtml(bb.message || "")}</p>
        <div class="ca-dasha-current">
            <div class="ca-dasha-label">Currently Running</div>
            <div class="ca-dasha-row">
                <span class="ca-dasha-lord">${escapeHtml(maha)}</span>
                <span class="ca-dasha-sep">›</span>
                <span class="ca-dasha-lord">${escapeHtml(antar)}</span>
                <span class="ca-dasha-sep">›</span>
                <span class="ca-dasha-lord">${escapeHtml(prat)}</span>
            </div>
            <div class="ca-dasha-row" style="margin-top:.35rem">
                <span class="ca-dasha-end">Mahadasha ends: ${escapeHtml(cur.mahadasha_ends || "—")}</span>
                <span style="color:rgba(192,132,252,0.4)">·</span>
                <span class="ca-dasha-end">Antardasha ends: ${escapeHtml(cur.antardasha_ends || "—")}</span>
            </div>
            ${pred ? `<p class="ca-dasha-pred">${escapeHtml(pred)}</p>` : ""}
        </div>
        <div class="ca-dasha-timeline">
            <table class="ca-dasha-table">
                <thead><tr>
                    <th>Mahadasha Lord</th><th>Start</th><th>End</th><th>Duration</th><th>Sub-periods</th>
                </tr></thead>
                <tbody>${timelineHtml}</tbody>
            </table>
        </div>`;

    container.appendChild(wrap);
}

window._toggleAntar = function(id) {
    const el = document.getElementById(id);
    if (!el) return;
    const hidden = el.style.display === "none";
    el.style.display = hidden ? "table-row" : "none";
    const btn = el.previousElementSibling && el.previousElementSibling.querySelector(".ca-toggle-btn");
    if (btn) btn.textContent = hidden ? "▼ Hide sub-periods" : "▶ Show sub-periods";
};

// ── 2. Panchanga Section ─────────────────────────────────────────────
function _renderPanchangaSection(panch) {
    if (!panch || panch.error || !panch.tithi) return;

    const container = document.getElementById("results");
    if (!container) return;

    const wrap = document.createElement("div");
    wrap.className = "ca-feature-card";
    wrap.id = "ca-panchanga-section";

    const vara    = panch.vara    || {};
    const tithi   = panch.tithi   || {};
    const nak     = panch.nakshatra || {};
    const yoga    = panch.yoga    || {};
    const karana  = panch.karana  || {};
    const timing  = panch.timing  || {};
    const rahu    = timing.rahukalam       || {};
    const abhijit = timing.abhijit_muhurta || {};
    const aus     = panch.auspiciousness_score || {};
    const score   = aus.score || 50;

   const PANCH_MEANINGS = {
    // Yoga
    "Vishkambha":"⚠ Obstacles likely — patience needed","Preeti":"✓ Harmony energy — great for relationships",
    "Ayushman":"✓ Vitality — good for health matters","Saubhagya":"✓ Fortune — luck is on your side",
    "Shobhana":"✓ Brilliance — auspicious for new ventures","Atiganda":"⚠ Turbulence — avoid risky decisions",
    "Sukarman":"✓ Good deeds — karma rewards effort","Dhriti":"✓ Steadiness — stable and resolute",
    "Shula":"⚠ Pain energy — avoid conflict or surgery","Ganda":"⚠ Knot energy — delays are likely",
    "Vriddhi":"✓ Growth energy — expand and initiate","Dhruva":"✓ Stability — ideal for long-term plans",
    "Vyaghata":"⚠ Challenging — avoid major decisions","Harshana":"✓ Joy — uplifting and optimistic",
    "Vajra":"⚠ Thunderbolt — intense, sharp energy","Siddhi":"✓ Success — excellent for new starts",
    "Vyatipata":"⚠ Calamity — extra caution advised","Variyana":"✓ Pleasant — good for socialising",
    "Parigha":"⚠ Obstruction — things may stall","Shiva":"✓ Auspicious — deeply positive",
    "Siddha":"✓ Accomplished — efforts pay off","Sadhya":"✓ Achievement — goals within reach",
    "Shubha":"✓ Auspicious — generally positive day","Shukla":"✓ Pure energy — clarity of mind",
    "Brahma":"✓ Creative power — inspired thinking","Indra":"✓ Kingly — authority and power",
    "Vaidhriti":"⚠ Separation energy — avoid travel or new bonds",
    // Nakshatra brief meanings
    "Ashwini":"⚡ Speed & healing","Bharani":"🔥 Transformation & intensity","Krittika":"🔪 Purification & focus",
    "Rohini":"🌸 Growth & abundance","Mrigashira":"🦌 Curiosity & seeking","Ardra":"🌪 Storms & breakthroughs",
    "Punarvasu":"🔄 Renewal & return","Pushya":"🙏 Nourishment & prosperity","Ashlesha":"🐍 Depth & mystery",
    "Magha":"👑 Ancestry & authority","Purva Phalguni":"💫 Pleasure & creativity","Uttara Phalguni":"☀ Partnership & commitment",
    "Hasta":"🤲 Skill & precision","Chitra":"✨ Beauty & perfection","Swati":"🌬 Independence & freedom",
    "Vishakha":"🏹 Purpose & achievement","Anuradha":"🌸 Devotion & friendship","Jyeshtha":"🛡 Protection & leadership",
    "Mula":"🌿 Root causes & liberation","Purva Ashadha":"💧 Invincibility & purification","Uttara Ashadha":"🐘 Victory & ethics",
    "Shravana":"👂 Listening & learning","Dhanishta":"🥁 Rhythm & ambition","Shatabhisha":"⭕ Healing & mystery",
    "Purva Bhadrapada":"⚡ Intensity & transformation","Uttara Bhadrapada":"🐉 Depth & compassion","Revati":"🐟 Completion & safe journeys",
    // Karana
    "Bava":"✓ Auspicious for all good work","Balava":"✓ Good for trade & abundance","Kaulava":"✓ Favors family & friends",
    "Taitila":"✓ Good for stability","Garija":"✓ Favors enterprise","Vanija":"✓ Excellent for business",
    "Vishti":"⚠ Bhadra — avoid new ventures","Chatushpada":"✓ Stable fixed energy","Naga":"✓ Serpent energy — hidden depth",
    "Sakuni":"✓ End-of-cycle clarity","Kimstughna":"✓ Beneficial for beginnings",
};

function cell(lbl, val, sub) {
    const cleanVal = val.split(" Pada ")[0].trim();
    const meaning  = PANCH_MEANINGS[cleanVal] || "";
    return `<div class="ca-panch-cell">
        <div class="ca-panch-lbl">${escapeHtml(lbl)}</div>
        <div class="ca-panch-val">${escapeHtml(val)}</div>
        ${sub ? `<div class="ca-panch-sub">${escapeHtml(sub)}</div>` : ""}
        ${meaning ? `<div class="ca-panch-meaning">${escapeHtml(meaning)}</div>` : ""}
    </div>`;
}

    wrap.innerHTML = `
        <div class="ca-feature-heading"><span class="ca-icon">📅</span> Birth Panchanga (Pancha-anga)</div>
        <div class="ca-panch-grid">
            ${cell("Vara (Day)", vara.name || "—", "Lord: " + (vara.lord || "—"))}
            ${cell("Tithi", tithi.name || "—", tithi.paksha || "")}
            ${cell("Nakshatra", (nak.name || "—") + " Pada " + (nak.pada || ""), "Lord: " + (nak.lord || "—"))}
            ${cell("Yoga", yoga.name || "—", yoga.quality || "")}
            ${cell("Karana", karana.name || "—", "")}
            ${cell("Lunar Month", panch.lunar_month || "—", panch.paksha || "")}
        </div>

        <div class="ca-auspicious-bar">
            <span class="ca-aus-label">Auspiciousness</span>
            <div class="ca-aus-track">
                <div class="ca-aus-fill" style="width:${score}%"></div>
            </div>
            <span class="ca-aus-score">${score}/100</span>
            <span class="ca-aus-label" style="color:#e8d5ff;font-weight:600">${escapeHtml(aus.label || "")}</span>
        </div>
        ${aus.recommendation ? `<p style="font-size:.82rem;color:#c4b5fd;margin-top:.5rem">${escapeHtml(aus.recommendation)}</p>` : ""}

        <div class="ca-timing-row">
            <div class="ca-timing-pill">
                <span class="ca-tl">Sunrise / Sunset</span>
                <span class="ca-tv">${escapeHtml(timing.sunrise || "—")} — ${escapeHtml(timing.sunset || "—")}</span>
            </div>
            ${rahu.start ? `<div class="ca-timing-pill ca-rahu">
                <span class="ca-tl">⚠ Rahukalam (avoid new starts)</span>
                <span class="ca-tv">${escapeHtml(rahu.start)} — ${escapeHtml(rahu.end)}</span>
            </div>` : ""}
            ${abhijit.start ? `<div class="ca-timing-pill ca-abhijit">
                <span class="ca-tl">✓ Abhijit Muhurta (most auspicious)</span>
                <span class="ca-tv">${escapeHtml(abhijit.start)} — ${escapeHtml(abhijit.end)}</span>
            </div>` : ""}
            ${timing.hora && timing.hora.lord ? `<div class="ca-timing-pill">
                <span class="ca-tl">Current Hora</span>
                <span class="ca-tv">${escapeHtml(timing.hora.lord)} (until ${escapeHtml(timing.hora.ends_at || "—")})</span>
            </div>` : ""}
        </div>`;

    container.appendChild(wrap);
}

// ── 3. Ashtakavarga Section ──────────────────────────────────────────
function _renderAshtakavargaSection(ashtak, lagna) {
    if (!ashtak || ashtak.error || !ashtak.sarva_by_sign) return;

    const container = document.getElementById("results");
    if (!container) return;

    const wrap = document.createElement("div");
    wrap.className = "ca-feature-card";
    wrap.id = "ca-ashtakavarga-section";

    const sarva = ashtak.sarva_by_sign || {};
    const lifeAreas = ashtak.life_areas || {};
    const avg  = ashtak.average_per_sign || 0;
    const interp = ashtak.interpretation || "";
    const strong = ashtak.strongest_signs || [];
    const weak   = ashtak.weakest_signs   || [];

    // Sarvashtakavarga 12-sign grid
    const SIGNS_SHORT = ["Ari","Tau","Gem","Can","Leo","Vir","Lib","Sco","Sag","Cap","Aqu","Pis"];
    const SIGNS_FULL  = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo",
                         "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"];
    let gridHtml = "";
    SIGNS_FULL.forEach(function(sign, i) {
        const pts = sarva[sign] || 0;
        let cls = "ca-sav-weak";
        if (pts >= 30) cls = "ca-sav-strong";
        else if (pts >= 25) cls = "ca-sav-good";
        else if (pts >= 20) cls = "ca-sav-avg";
        const isLagna = sign === lagna;
        gridHtml += `<div class="ca-sav-cell ${cls}" title="${sign}: ${pts} points${isLagna?" (Lagna)":""}">
            <span class="ca-sav-sign">${SIGNS_SHORT[i]}${isLagna?"✦":""}</span>
            <span class="ca-sav-pts">${pts}</span>
        </div>`;
    });

    // Life areas grid (12 houses)
    let areasHtml = "";
    for (let h = 1; h <= 12; h++) {
        const la = lifeAreas[h] || {};
        const pts = la.points || 0;
        let ptsClass = "weak";
        if (pts >= 30) ptsClass = "strong";
        else if (pts >= 25) ptsClass = "good";
        else if (pts >= 20) ptsClass = "avg";
        const barW = Math.round((pts / 45) * 100);
        areasHtml += `<div class="ca-la-cell">
            <div class="ca-la-header">
                <span class="ca-la-name">H${h}: ${escapeHtml(la.name || "")}</span>
                <span class="ca-la-pts ${ptsClass}">${pts}</span>
            </div>
            <div class="ca-la-bar-track"><div class="ca-la-bar-fill" style="width:${barW}%"></div></div>
            <div class="ca-la-pred">${escapeHtml((la.prediction || "").slice(0, 90))}${(la.prediction||"").length > 90 ? "…" : ""}</div>
        </div>`;
    }

    const strongStr = strong.slice(0,3).map(s => `${s[0]} (${s[1]})`).join(", ");
    const weakStr   = weak.slice(0,3).map(s  => `${s[0]} (${s[1]})`).join(", ");

    wrap.innerHTML = `
        <div class="ca-feature-heading"><span class="ca-icon">⭐</span> Ashtakavarga — Planetary Strength Grid</div>
        <p style="font-size:.85rem;color:#c4b5fd;margin-bottom:.8rem">${escapeHtml(interp)}</p>

        <div style="display:flex;flex-wrap:wrap;gap:1rem;margin-bottom:.8rem;font-size:.82rem">
            <span style="color:#a78bfa">Average/sign: <strong style="color:#ddd6fe">${avg}/28</strong></span>
            <span style="color:#a78bfa">Strongest: <strong style="color:#6ee7b7">${escapeHtml(strongStr)}</strong></span>
            <span style="color:#a78bfa">Weakest: <strong style="color:#fca5a5">${escapeHtml(weakStr)}</strong></span>
        </div>

       <p style="font-size:.75rem;color:#a78bfa;margin-bottom:.5rem;text-transform:uppercase;letter-spacing:.1em">
            Life Area Analysis (House-wise)
        </p>
        <div class="ca-life-areas">${areasHtml}</div>

        <details class="ca-expert-toggle">
            <summary>Show zodiac sign grid (for astrologers)</summary>
            <p style="font-size:.75rem;color:#a78bfa;margin:.75rem 0 .5rem;text-transform:uppercase;letter-spacing:.1em">
                Sarvashtakavarga — Benefic Points Per Sign (✦ = Your Lagna)
            </p>
            <div class="ca-sav-grid">${gridHtml}</div>
            <div style="display:flex;gap:1rem;flex-wrap:wrap;font-size:.7rem;color:#a78bfa;margin-bottom:1rem">
                <span><span style="color:#6ee7b7">■</span> Strong (30+)</span>
                <span><span style="color:#c4b5fd">■</span> Good (25–29)</span>
                <span><span style="color:#fcd34d">■</span> Average (20–24)</span>
                <span><span style="color:#fca5a5">■</span> Weak (&lt;20)</span>
            </div>
        </details>
    `;

    container.appendChild(wrap);
}
