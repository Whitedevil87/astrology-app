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

    const birthDateText = document.getElementById("birthDateText");
    const birthDateHidden = document.getElementById("birthDateHidden");

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

    function fetchChatHint() {
        fetch("/api/config")
            .then(function (r) {
                return r.json();
            })
            .then(function (cfg) {
                if (!chatHint) return;
                if (cfg && cfg.ai_chat) {
                    chatHint.textContent =
                        "AI-enhanced Guru is on (OpenAI). Answers blend your saved chart context with your question.";
                } else {
                    chatHint.textContent =
                        "Offline Guru: rule-based guidance from your saved reading. Add OPENAI_API_KEY on the server for deeper AI replies.";
                }
            })
            .catch(function () {
                if (chatHint) {
                    chatHint.textContent = "Ask about Rahu/Ketu, marriage, career, dasha, or remedies.";
                }
            });
    }

    function escapeHtml(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function clearPlaceSelection() {
        if (placeLat) placeLat.value = "";
        if (placeLon) placeLon.value = "";
        if (placeLabel) placeLabel.value = "";
        if (placeTz) placeTz.value = "";
    }

    function normalizeBirthDateText(raw) {
        const value = String(raw || "").trim();
        if (!value) return "";

        // Accept YYYY-MM-DD or DD-MM-YYYY (and / separators).
        const cleaned = value.replace(/\//g, "-");
        const iso = cleaned.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
        const dmy = cleaned.match(/^(\d{1,2})-(\d{1,2})-(\d{4})$/);

        let y, m, d;
        if (iso) {
            y = parseInt(iso[1], 10);
            m = parseInt(iso[2], 10);
            d = parseInt(iso[3], 10);
        } else if (dmy) {
            d = parseInt(dmy[1], 10);
            m = parseInt(dmy[2], 10);
            y = parseInt(dmy[3], 10);
        } else {
            return "";
        }

        if (!(y >= 1900 && y <= 2100)) return "";
        if (!(m >= 1 && m <= 12)) return "";
        if (!(d >= 1 && d <= 31)) return "";

        // Validate actual calendar date.
        const dt = new Date(Date.UTC(y, m - 1, d));
        if (
            dt.getUTCFullYear() !== y ||
            dt.getUTCMonth() !== (m - 1) ||
            dt.getUTCDate() !== d
        ) {
            return "";
        }

        const mm = m < 10 ? "0" + m : String(m);
        const dd = d < 10 ? "0" + d : String(d);
        return y + "-" + mm + "-" + dd;
    }

    function syncHiddenBirthDate() {
        if (!birthDateHidden) return;
        const normalized = normalizeBirthDateText(birthDateText ? birthDateText.value : "");
        birthDateHidden.value = normalized;
    }

    function validateRequired() {
        clearError();
        if (!String(form.elements.full_name.value || "").trim()) {
            showError("Please enter your full name.");
            return false;
        }
        syncHiddenBirthDate();
        if (!birthDateHidden || !birthDateHidden.value) {
            showError("Please enter your date of birth as YYYY-MM-DD.");
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

    function setStepTrack(active) {
        [track1, track2, track3, track4].forEach(function (el) {
            el.classList.remove("neo-step-active");
        });
        if (active === 1) track1.classList.add("neo-step-active");
        if (active === 2) track2.classList.add("neo-step-active");
        if (active === 3) track3.classList.add("neo-step-active");
        if (active === 4) track4.classList.add("neo-step-active");
    }

    function onlyStep(stepEl, trackNum) {
        step1.classList.add("hidden");
        step2.classList.add("hidden");
        step3.classList.add("hidden");
        processing.classList.add("hidden");
        results.classList.add("hidden");
        stepEl.classList.remove("hidden");
        if (typeof trackNum === "number") {
            setStepTrack(trackNum);
        }
    }

    function showError(msg) {
        errorBox.textContent = msg;
        errorBox.classList.remove("hidden");
    }

    function clearError() {
        errorBox.textContent = "";
        errorBox.classList.add("hidden");
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
                // mousedown so input doesn't blur before selection
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
                    if (!data || !data.success) {
                        hidePlaceDropdown();
                        return;
                    }
                    if (String(birthPlace.value || "").trim() !== lastPlaceQuery) {
                        // stale response
                        return;
                    }
                    showPlaceDropdown(data.places || []);
                })
                .catch(function () {
                    hidePlaceDropdown();
                });
        }, 220);
    }

    function resetProgress() {
        if (progressInterval) {
            clearInterval(progressInterval);
            progressInterval = null;
        }
        progressBar.style.width = "0%";
        progressText.textContent = "0%";
    }

    function startProgress() {
        resetProgress();
        let p = 0;
        progressInterval = setInterval(function () {
            if (p < 92) {
                p += Math.floor(Math.random() * 8) + 3;
                if (p > 92) p = 92;
            }
            progressBar.style.width = p + "%";
            progressText.textContent = p + "%";
        }, 250);
    }

    function finishProgress() {
        if (progressInterval) {
            clearInterval(progressInterval);
            progressInterval = null;
        }
        progressBar.style.width = "100%";
        progressText.textContent = "100%";
    }

    function chip(label, value) {
        return (
            '<span class="cosmic-chip"><span class="cosmic-chip-label">' +
            escapeHtml(label) +
            '</span><span class="cosmic-chip-value">' +
            escapeHtml(value) +
            "</span></span>"
        );
    }

    function sectionCard(title, body, icon) {
        return (
            '<article class="report-card fade-in">' +
            '<h3><span class="icon-glow mr-2">' +
            escapeHtml(icon) +
            "</span>" +
            escapeHtml(title) +
            "</h3><p>" +
            escapeHtml(body) +
            "</p></article>"
        );
    }

    function renderResults(data) {
        const name = String(form.elements.full_name.value || "").trim();
        resultTitle.textContent = (name || "Your") + " — Cosmic brief";
        resultMeta.textContent =
            "Report #" + data.report_id + " · " + (data.created_at || "") + " · Big Three + timing cues";

        const profile = data.profile || {};
        const bp = data.blueprint || {};

        if (bp.glyph) {
            profileCards.innerHTML = [
                ["Sun sign", (bp.glyph || "") + " " + (profile.zodiac || "")],
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

        const pairs = [
            ["Lucky #", String(bp.lucky_number ?? "—")],
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

        if (reportPrintBlock && data.report_html) {
            reportPrintBlock.innerHTML = data.report_html;
        }

        lastReportId = data.report_id;
        if (chatLog) {
            chatLog.innerHTML = "";
        }
    }

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
        chatSend.disabled = true;
        fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ report_id: lastReportId, message: text })
        })
            .then(function (res) {
                return res.json().then(function (json) {
                    if (!res.ok || !json.success) throw new Error(json.error || "Chat failed.");
                    return json;
                });
            })
            .then(function (json) {
                const meta = json.source === "openai" ? "Guru · AI" : "Guru · rules";
                appendChatBubble("guru", json.reply || "", meta);
            })
            .catch(function (err) {
                appendChatBubble("guru", err.message || "Unable to reach Guru.", "Guru");
            })
            .finally(function () {
                chatSend.disabled = false;
            });
    }

    function submitAnalysis() {
        if (busy) return;
        syncHiddenBirthDate();
        if (!validateRequired()) {
            onlyStep(step1, 1);
            return;
        }
        if (palmEnabled.value === "yes" && !handChoice.value) {
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
                    renderResults(data);
                    onlyStep(results, 4);
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

    fetchChatHint();

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

    goStep2.addEventListener("click", function () {
        if (!validateRequired()) return;
        onlyStep(step2, 2);
    });

    palmYes.addEventListener("click", function () {
        palmEnabled.value = "yes";
        onlyStep(step3, 3);
    });

    palmNo.addEventListener("click", function () {
        palmEnabled.value = "no";
        form.elements.hand_choice.value = "";
        form.elements.palm_image.value = "";
        submitAnalysis();
    });

    submitBtn.addEventListener("click", function () {
        submitAnalysis();
    });

    downloadPdf.addEventListener("click", function () {
        window.print();
    });

    tryAgain.addEventListener("click", function () {
        form.reset();
        palmEnabled.value = "no";
        if (birthDateText) birthDateText.value = "";
        if (birthDateHidden) birthDateHidden.value = "";
        clearPlaceSelection();
        hidePlaceDropdown();
        clearError();
        resetProgress();
        if (reportPrintBlock) reportPrintBlock.innerHTML = "";
        if (chatLog) chatLog.innerHTML = "";
        lastReportId = null;
        onlyStep(step1, 1);
    });

    if (birthDateText) {
        birthDateText.addEventListener("input", function () {
            syncHiddenBirthDate();
        });
        birthDateText.addEventListener("blur", function () {
            syncHiddenBirthDate();
            if (birthDateHidden && birthDateHidden.value) {
                birthDateText.value = birthDateHidden.value;
            }
        });
    }

    if (birthPlace) {
        birthPlace.addEventListener("input", function () {
            clearPlaceSelection();
            fetchPlaceSuggestions(this.value);
        });
        birthPlace.addEventListener("blur", function () {
            // allow click selection via mousedown; delay hide
            setTimeout(hidePlaceDropdown, 120);
        });
        birthPlace.addEventListener("focus", function () {
            fetchPlaceSuggestions(this.value);
        });
    }

    form.addEventListener("submit", function (event) {
        event.preventDefault();
    });

    onlyStep(step1, 1);
});
