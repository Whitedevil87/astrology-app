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

        birthYear.addEventListener("change", function () {
            refillDays();
            syncHiddenBirthDate();
        });
        birthMonth.addEventListener("change", function () {
            refillDays();
            syncHiddenBirthDate();
        });
        birthDay.addEventListener("change", function () {
            syncHiddenBirthDate();
        });
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
    fetchCsrfToken();

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
        onlyStep(step3, 3);
    });

    submitBtn.addEventListener("click", function () {
        if (!validateRequired() || !handChoice.value) {
            if (!handChoice.value && palmEnabled.value === "yes") {
                errorBox.textContent = "Please select which hand for palm.";
                errorBox.classList.remove("hidden");
            }
            return;
        }

        const formData = new FormData(form);
        onlyStep(processing, 4);
        progressBar.style.width = "0%";
        progressText.textContent = "0%";
        let p = 0;
        progressInterval = setInterval(function () {
            p = Math.min(p + Math.random() * 35, 90);
            progressBar.style.width = p + "%";
            progressText.textContent = Math.floor(p) + "%";
        }, 500);

        fetch("/api/analyze", {
            method: "POST",
            body: formData,
            headers: { "X-CSRF-Token": csrfToken || "" }
        })
            .then(function (r) {
                return r.json();
            })
            .then(function (data) {
                clearInterval(progressInterval);
                progressBar.style.width = "100%";
                progressText.textContent = "100%";
                setTimeout(function () {
                    if (data && data.success) {
                        displayResults(data);
                        onlyStep(results, 4);
                    } else {
                        errorBox.textContent = (data && data.error) || "Analysis failed.";
                        errorBox.classList.remove("hidden");
                        onlyStep(step1, 1);
                    }
                }, 400);
            })
            .catch(function (err) {
                clearInterval(progressInterval);
                console.error("Fetch error:", err);
                errorBox.textContent = "Network or server error.";
                errorBox.classList.remove("hidden");
                onlyStep(step1, 1);
            });
    });

    tryAgain.addEventListener("click", function () {
        form.reset();
        form.querySelectorAll("select").forEach(function (s) { s.value = ""; });
        errorBox.classList.add("hidden");
        onlyStep(step1, 1);
        window.scrollTo(0, 0);
    });

    downloadPdf.addEventListener("click", function () {
        if (!lastReportId) return;
        window.open("/api/pdf/" + lastReportId, "_blank");
    });
});

/* ============================================
   FLOATING CHAT WIDGET FUNCTIONALITY
   ============================================ */

document.addEventListener('DOMContentLoaded', function() {
    const floatingChatWidget = document.getElementById('floatingChatWidget');
    const floatingChatToggle = document.getElementById('floatingChatToggle');
    const floatingChatInput = document.getElementById('floatingChatInput');
    const floatingChatSend = document.getElementById('floatingChatSend');
    const floatingChatMessages = document.getElementById('floatingChatMessages');

    // Handle send button click
    if (floatingChatSend) {
        floatingChatSend.addEventListener('click', sendFloatingChat);
    }

    // Handle Enter key in input
    if (floatingChatInput) {
        floatingChatInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                sendFloatingChat();
            }
        });
    }

    function sendFloatingChat() {
        const message = floatingChatInput.value.trim();
        if (!message) return;

        // Add user message
        const userMsg = document.createElement('div');
        userMsg.className = 'floating-chat-message user-msg';
        userMsg.innerHTML = `<p>${escapeHtml(message)}</p>`;
        floatingChatMessages.appendChild(userMsg);

        // Clear input
        floatingChatInput.value = '';
        floatingChatInput.focus();

        // Add loading indicator
        const loadingMsg = document.createElement('div');
        loadingMsg.className = 'floating-chat-message';
        loadingMsg.innerHTML = `<div style="color: var(--neo-cyan); padding: 0.8rem;">thinking...</div>`;
        floatingChatMessages.appendChild(loadingMsg);
        floatingChatMessages.scrollTop = floatingChatMessages.scrollHeight;

        // Try to get from last report ID (if saved chart exists)
        const reportId = lastReportId || null;
        
        fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-Token': csrfToken || ''
            },
            body: JSON.stringify({
                user_message: message,
                report_id: reportId
            })
        })
            .then(r => r.json())
            .then(data => {
                loadingMsg.remove();
                if (data && data.success && data.guru_response) {
                    const guruMsg = document.createElement('div');
                    guruMsg.className = 'floating-chat-message guru-msg';
                    guruMsg.innerHTML = `<p>${escapeHtml(data.guru_response)}</p>`;
                    floatingChatMessages.appendChild(guruMsg);
                } else {
                    const errorMsg = document.createElement('div');
                    errorMsg.className = 'floating-chat-message guru-msg';
                    errorMsg.innerHTML = `<p>⚠️ ${escapeHtml((data && data.error) || 'Unable to respond. Please check your chart.')}</p>`;
                    floatingChatMessages.appendChild(errorMsg);
                }
                floatingChatMessages.scrollTop = floatingChatMessages.scrollHeight;
            })
            .catch(err => {
                console.error('Floating chat error:', err);
                loadingMsg.remove();
                const errorMsg = document.createElement('div');
                errorMsg.className = 'floating-chat-message guru-msg';
                errorMsg.innerHTML = `<p>⚠️ Connection error. Please try again.</p>`;
                floatingChatMessages.appendChild(errorMsg);
                floatingChatMessages.scrollTop = floatingChatMessages.scrollHeight;
            });
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
});
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
        if (birthDateHidden) birthDateHidden.value = "";
        if (birthYear) birthYear.value = "";
        if (birthMonth) birthMonth.value = "";
        if (birthDay) birthDay.innerHTML = '<option value="">Day</option>';
        clearPlaceSelection();
        hidePlaceDropdown();
        clearError();
        resetProgress();
        if (reportPrintBlock) reportPrintBlock.innerHTML = "";
        if (chatLog) chatLog.innerHTML = "";
        lastReportId = null;
        onlyStep(step1, 1);
    });

    initDobSelectors();

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
