      const landingScreen = document.getElementById("landingScreen");
      const setupScreen = document.getElementById("setupScreen");
      const mainScreen = document.getElementById("mainScreen");

      const goToSetupBtn = document.getElementById("goToSetupBtn");
      const aboutBtn = document.getElementById("aboutBtn");
      const backToLandingBtn = document.getElementById("backToLandingBtn");
      const launchAppBtn = document.getElementById("launchAppBtn");
      const resetProjectBtn = document.getElementById("resetProjectBtn");

      const languageSelect = document.getElementById("languageSelect");
      const speechModeSelect = document.getElementById("speechModeSelect");
      const voiceLangSelect = document.getElementById("voiceLangSelect");
      const recognitionModeSelect = document.getElementById(
        "recognitionModeSelect",
      );
      const liveLanguage = document.getElementById("liveLanguage");
      const liveSpeechMode = document.getElementById("liveSpeechMode");
      const configPreview = document.getElementById("configPreview");

      const video = document.getElementById("video");
      const canvas = document.getElementById("canvas");
      const ctx = canvas.getContext("2d");

      const startCameraBtn = document.getElementById("startCameraBtn");
      const stopCameraBtn = document.getElementById("stopCameraBtn");
      const speakNowBtn = document.getElementById("speakNowBtn");
      const clearSentenceBtn = document.getElementById("clearSentenceBtn");
      const backspaceBtn = document.getElementById("backspaceBtn");

      const gestureText = document.getElementById("gestureText");
      const metricsText = document.getElementById("metricsText");
      const sentenceDisplay = document.getElementById("sentenceDisplay");
      const historyList = document.getElementById("historyList");
      const statusTag = document.getElementById("statusTag");
      const outputBox = document.getElementById("outputBox");

      let appConfig = {
        language: "ASL",
        speechMode: "instant",
        voiceLang: "en-US",
        recognitionMode: "prototype",
      };

      const recognitionGate = new SignBridgeGestures.Stabilizer();
      let starting = false;
      let cameraGeneration = 0;
      let lastVideoTime = -1;
      let hands = null;
      let mediaStream = null;
      let animationId = null;
      let isProcessing = false;

      let sentenceWords = [];
      let historyItems = [];
      let currentHand = null;
      let customPrediction = null;
      let customPredictionAt = 0;
      let lastPredictRequestAt = 0;
      let predictionInFlight = false;
      const backendStatus = document.getElementById("backendStatus");
      const sampleStatus = document.getElementById("sampleStatus");
      const sampleLabel = document.getElementById("sampleLabel");

      async function api(path, options = {}) {
        const response = await fetch(path, {
          headers: { "Content-Type": "application/json" },
          ...options,
        });
        let result;
        try { result = await response.json(); }
        catch { throw new Error(`Backend returned HTTP ${response.status}`); }
        if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
        return result;
      }

      async function checkBackend() {
        try {
          await api("/api/health");
          backendStatus.textContent = "● Database connected";
          await Promise.all([loadHistory(), loadSamples()]);
        } catch (error) {
          backendStatus.textContent = "● Database unavailable";
          sampleStatus.textContent = "Cannot connect to the Python API. Run python server.py (not index.html directly).";
          console.warn(error);
        }
      }

      async function loadHistory() {
        try {
          const { items } = await api("/api/history?limit=25");
          historyItems = items.map(item => `${item.event_type.toUpperCase()}: ${item.phrase}`);
          renderHistory(historyItems);
        } catch (error) { backendStatus.textContent = "● Database unavailable"; console.warn(error); }
      }

      async function loadSamples() {
        try {
          const [stats, { items }] = await Promise.all([api("/api/stats"), api("/api/samples?limit=20")]);
          document.getElementById("datasetStats").textContent = `${stats.sample_count} real samples`;
          document.getElementById("statSamples").textContent = stats.sample_count;
          document.getElementById("statLabels").textContent = Object.keys(stats.labels).length;
          document.getElementById("statTrained").textContent = stats.trained_labels.length;
          const list = document.getElementById("sampleList");
          list.replaceChildren();
          if (!items.length) {
            const empty = document.createElement("div");
            empty.className = "history-item";
            empty.textContent = "No labeled samples yet.";
            list.append(empty);
          }
          for (const item of items) {
            const line = document.createElement("div");
            line.className = "history-item";
            line.style.cssText = "display:flex;justify-content:space-between;align-items:center;gap:8px";
            const name = document.createElement("span");
            name.textContent = `${item.label} · ${item.handedness}`;
            const del = document.createElement("button");
            del.className = "btn subtle";
            del.textContent = "Remove";
            del.setAttribute("aria-label", `Remove sample ${item.id}`);
            del.onclick = async () => {
              try { await api(`/api/samples/${item.id}`, { method: "DELETE" }); await loadSamples(); }
              catch (err) { sampleStatus.textContent = err.message; }
            };
            line.append(name, del);
            list.append(line);
          }
          const examples = Object.entries(stats.labels).map(([name, n]) => `${name}: ${n}`).join(" · ");
          sampleStatus.textContent = examples ? `Collected: ${examples}. At least 3 examples per label activate custom recognition.` : "Start your webcam, hold one gesture, and capture samples.";
        } catch (error) { sampleStatus.textContent = `Dataset could not load: ${error.message}`; }
      }

      async function captureSample() {
        const label = sampleLabel.value.trim();
        if (!/^[A-Za-z][A-Za-z0-9 _'-]{0,47}$/.test(label)) {
          sampleStatus.textContent = "Enter a label up to 48 characters (letters, numbers, spaces).";
          return;
        }
        if (!currentHand || Date.now() - currentHand.seen > 1800) {
          sampleStatus.textContent = "Show exactly one hand to the camera, then capture again.";
          return;
        }
        try {
          await api("/api/samples", { method: "POST", body: JSON.stringify({label, landmarks: currentHand.landmarks, handedness: currentHand.handedness}) });
          await loadSamples();
          sampleStatus.textContent = `Saved a real 21-landmark sample for “${label}”. Move your hand slightly before capturing another.`;
        } catch (error) { sampleStatus.textContent = `Could not save: ${error.message}`; }
      }

      async function requestPrediction(landmarks, handedness) {
        if (predictionInFlight || Date.now() - lastPredictRequestAt < 280) return;
        predictionInFlight = true;
        lastPredictRequestAt = Date.now();
        try {
          const result = await api("/api/predict", { method: "POST", body: JSON.stringify({landmarks, handedness}) });
          customPrediction = result;
          customPredictionAt = Date.now();
        } catch (err) {
          customPrediction = null;
          backendStatus.textContent = "● Recognition server unavailable";
        } finally { predictionInFlight = false; }
      }

      let stableLabel = "";
      let stableCount = 0;
      let lastAcceptedLabel = "";
      let lastAcceptedAt = 0;
      let lastSpokenAt = 0;

      const ACCEPT_THRESHOLD = 8;
      const QUICK_ACCEPT_COOLDOWN = 2200;
      const QUICK_SPEAK_COOLDOWN = 1400;

      const gestureMap = {
        single: {
          thumbs_up: "Yes",
          thumbs_down: "No",
          open_palm: "Hello",
          closed_fist: "Stop",
          one_finger: "Help",
          two_fingers: "Water",
          three_fingers: "Food",
          four_fingers: "Thank You",
          phone_gesture: "Call",
          v_sign: "Wait",
        },
        combo: {
          "open_palm + open_palm": "I Need Assistance",
          "closed_fist + open_palm": "Emergency",
          "open_palm + two_fingers": "Please Wait",
          "open_palm + thumbs_up": "Call Family",
        },
      };

      function showScreen(screen) {
        landingScreen.classList.add("hidden");
        setupScreen.classList.add("hidden");
        mainScreen.classList.add("hidden");
        screen.classList.remove("hidden");
      }

      function updateConfigPreview() {
        const speaker =
          appConfig.speechMode === "instant"
            ? "Instant"
            : appConfig.speechMode === "sentence"
              ? "Sentence"
              : "Mute";

        configPreview.textContent = `Mode: ${appConfig.recognitionMode === "custom" ? "My dataset" : "Built-in"} · Speaker: ${speaker} · Voice: English`;
        liveLanguage.value = appConfig.language;
        liveSpeechMode.value = appConfig.speechMode;
      }

      function setStatus(message) {
        statusTag.textContent = `Status: ${message}`;
      }

      function resizeCanvas() {
        canvas.width = video.videoWidth || 960;
        canvas.height = video.videoHeight || 640;
      }

      function speak(text) {
        if (!window.speechSynthesis || appConfig.speechMode === "mute" || !text)
          return;

        const now = Date.now();
        // Recognition dwell/release gating handles repeats. Never drop a new assistance phrase.

        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = "en-US";
        utterance.rate = 1;
        window.speechSynthesis.speak(utterance);

        lastSpokenAt = now;
      }

      function updateSentenceDisplay() {
        sentenceDisplay.textContent = sentenceWords.length
          ? sentenceWords.join(" ")
          : "Your recognized words will appear here...";
      }

      function renderHistory(items) {
        historyList.replaceChildren();
        const values = items.length ? items : ["No history yet."];
        for (const item of values) {
          const line = document.createElement("div");
          line.className = "history-item";
          line.textContent = item;
          historyList.append(line);
        }
      }

      function addToHistory(text, event_type = "recognized", source = "gesture") {
        if (!text) return;
        historyItems.unshift(text);
        historyItems = historyItems.slice(0, 25);
        renderHistory(historyItems);
        api("/api/history", {method: "POST", body: JSON.stringify({phrase: text.includes(": ") ? text.split(": ").slice(1).join(": ") : text, event_type, source})})
          .catch(err => { backendStatus.textContent = "● History not saved"; console.warn(err); });
      }

      function appendWord(word, source = "gesture") {
        if (!word) return;
        sentenceWords.push(word);
        updateSentenceDisplay();
        addToHistory(`${source.toUpperCase()}: ${word}`, source === "quick" ? "quick" : "recognized", source);

        if (appConfig.speechMode === "instant") {
          speak(word);
        }
      }

      function setOutputTheme(text) {
        const emergencyTexts = ["Emergency", "I Need Assistance", "Help"];

        if (emergencyTexts.includes(text)) {
          outputBox.classList.add("danger-output");
        } else {
          outputBox.classList.remove("danger-output");
        }
      }

      function distance(a, b) {
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        return Math.sqrt(dx * dx + dy * dy);
      }

      function detectGesture(landmarks) {
        return SignBridgeGestures.classify(landmarks, (video.videoWidth || 640) / (video.videoHeight || 480));
      }
      function getMappedPhraseFromHands(hands) { return SignBridgeGestures.mapHands(hands); }

      async function initHands() {
        if (typeof Hands === "undefined" || typeof drawConnectors === "undefined") {
          throw new Error("MediaPipe scripts were not loaded. Check your internet connection.");
        }
        hands = new Hands({
          locateFile: (file) =>
            `./vendor/hands/${file}`,
        });

        hands.setOptions({
          maxNumHands: 2,
          modelComplexity: 1,
          minDetectionConfidence: 0.6,
          minTrackingConfidence: 0.6,
        });

        hands.onResults((results) => {
          ctx.save();
          ctx.clearRect(0, 0, canvas.width, canvas.height);
          if (results.image) ctx.drawImage(results.image, 0, 0, canvas.width, canvas.height);

          if (
            results.multiHandLandmarks &&
            results.multiHandLandmarks.length > 0
          ) {
            const detectedHands = [];

            currentHand = results.multiHandLandmarks.length === 1 ? {
              landmarks: results.multiHandLandmarks[0].map(p => ({x: p.x, y: p.y, z: p.z})),
              handedness: results.multiHandedness?.[0]?.label || "Unknown",
              seen: Date.now(),
            } : null;
            if (currentHand && appConfig.recognitionMode === "custom") {
              requestPrediction(currentHand.landmarks, currentHand.handedness);
            }

            results.multiHandLandmarks.forEach((landmarks) => {
              drawConnectors(ctx, landmarks, HAND_CONNECTIONS, {
                color: "#38bdf8",
                lineWidth: 3,
              });
              drawLandmarks(ctx, landmarks, {
                color: "#22c55e",
                lineWidth: 2,
                radius: 4,
              });

              const detected = detectGesture(landmarks);

              detectedHands.push({
                gesture: detected,
              });
            });

            const mapped = getMappedPhraseFromHands(detectedHands);
            let { phrase, debugText, usedGestures } = mapped;
            if (appConfig.recognitionMode === "custom") {
              phrase = results.multiHandLandmarks.length === 1 &&
                customPrediction && Date.now() - customPredictionAt < 900 &&
                customPrediction.label ? customPrediction.label : "Unknown Gesture";
              debugText = phrase === "Unknown Gesture" ? "Collect at least 3 labeled samples / show one hand" :
                `Custom dataset confidence: ${Math.round(customPrediction.confidence*100)}%`;
              usedGestures = ["custom"];
            }
            gestureText.textContent = phrase || "No gesture detected";
            metricsText.textContent = `${results.multiHandLandmarks.length} hands · ${debugText}`;
            setOutputTheme(phrase);

            if (recognitionGate.update(phrase, performance.now(), results.multiHandLandmarks.length)) {
              appendWord(phrase, usedGestures.length >= 2 ? "combo" : "gesture");
            }
          } else {
            recognitionGate.update("", performance.now(), 0);
            currentHand = null;
            customPrediction = null;
            stableLabel = "";
            stableCount = 0;
            lastAcceptedLabel = "";
            gestureText.textContent = "No gesture detected";
            metricsText.textContent = "0 hands";
            setOutputTheme("");
          }

          ctx.restore();
        });
      }

      async function processFrame() {
        if (!mediaStream || !hands) return;

        if (video.readyState >= 2 && !isProcessing && video.currentTime !== lastVideoTime) {
          isProcessing = true;
          try {
            lastVideoTime = video.currentTime;
            await hands.send({ image: video });
          } catch (error) {
            console.error(error);
            setStatus("processing error");
          } finally {
            isProcessing = false;
          }
        }

        if (mediaStream) animationId = requestAnimationFrame(processFrame);
      }

      async function startCamera() {
        if (mediaStream || starting) return;
        starting = true; startCameraBtn.disabled = true;
        const generation = ++cameraGeneration;
        try {
          if (!navigator.mediaDevices?.getUserMedia) throw new Error("Camera requires HTTPS or localhost.");
          if (!hands) await initHands();

          const stream = await navigator.mediaDevices.getUserMedia({
            video: { width: 1280, height: 720 },
            audio: false,
          });

          if (generation !== cameraGeneration) { stream.getTracks().forEach(t=>t.stop()); return; }
          mediaStream = stream; lastVideoTime = -1; recognitionGate.reset();
          video.srcObject = mediaStream;
          await video.play();
          resizeCanvas();
          setStatus("camera started");
          processFrame();
        } catch (error) {
          console.error(error);
          if (mediaStream) mediaStream.getTracks().forEach(t=>t.stop());
          mediaStream = null;
          setStatus(error.message || "camera unavailable or permission denied");
        } finally { starting = false; startCameraBtn.disabled = false; }
      }

      function stopCamera() {
        ++cameraGeneration; recognitionGate.reset();
        if (animationId) cancelAnimationFrame(animationId);
        animationId = null;

        if (mediaStream) {
          mediaStream.getTracks().forEach((track) => track.stop());
          mediaStream = null;
        }

        currentHand = null;
        customPrediction = null;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        gestureText.textContent = "No gesture detected";
        metricsText.textContent = "0 hands";
        stableLabel = "";
        stableCount = 0;
        lastAcceptedLabel = "";
        if (window.speechSynthesis) window.speechSynthesis.cancel();
        setOutputTheme("");
        setStatus("camera stopped");
      }

      goToSetupBtn.addEventListener("click", () => showScreen(setupScreen));

      aboutBtn.addEventListener("click", () => {
        alert(
          "SignBridge recognizes a small set of custom gesture shortcuts. It is not a full ASL translator or an emergency service. You can collect real 21-point samples and use KNN classification through the Python backend.",
        );
      });

      backToLandingBtn.addEventListener("click", () =>
        showScreen(landingScreen),
      );

      launchAppBtn.addEventListener("click", () => {
        appConfig.language = languageSelect.value;
        appConfig.speechMode = speechModeSelect.value;
        appConfig.voiceLang = voiceLangSelect.value;
        appConfig.recognitionMode = recognitionModeSelect.value;
        updateConfigPreview();
        showScreen(mainScreen);
        checkBackend();
      });

      resetProjectBtn.addEventListener("click", () => {
        stopCamera();
        showScreen(setupScreen);
      });

      liveLanguage.addEventListener("change", (e) => {
        appConfig.language = e.target.value;
        updateConfigPreview();
      });

      liveSpeechMode.addEventListener("change", (e) => {
        appConfig.speechMode = e.target.value;
        updateConfigPreview();
      });

      startCameraBtn.addEventListener("click", startCamera);
      stopCameraBtn.addEventListener("click", stopCamera);

      speakNowBtn.addEventListener("click", () => {
        if (!sentenceWords.length) return;
        const fullSentence = sentenceWords.join(" ");
        addToHistory(`SPOKEN: ${fullSentence}`, "spoken", "button");
        speak(fullSentence);
      });

      clearSentenceBtn.addEventListener("click", () => {
        sentenceWords = [];
        updateSentenceDisplay();
      });

      backspaceBtn.addEventListener("click", () => {
        sentenceWords.pop();
        updateSentenceDisplay();
      });

      document.querySelectorAll("[data-quick]").forEach((btn) => {
        btn.addEventListener("click", () =>
          appendWord(btn.dataset.quick, "quick"),
        );
      });

      document.getElementById("captureSampleBtn").addEventListener("click", captureSample);
      document.getElementById("refreshSamplesBtn").addEventListener("click", loadSamples);
      document.getElementById("refreshHistoryBtn").addEventListener("click", loadHistory);
      document.getElementById("clearHistoryBtn").addEventListener("click", async () => {
        if (!confirm("Delete all saved activity?")) return;
        try { await api("/api/history", {method:"DELETE"}); await loadHistory(); }
        catch(err) { backendStatus.textContent = err.message; }
      });
      document.getElementById("clearDatasetBtn").addEventListener("click", async () => {
        if (!confirm("Permanently delete ALL collected samples? Export first if needed.")) return;
        try { await api("/api/samples", {method:"DELETE"}); customPrediction = null; await loadSamples(); }
        catch(err) { sampleStatus.textContent = err.message; }
      });
      document.getElementById("exportCsvBtn").addEventListener("click", () => { window.location.href = "/api/export.csv"; });
      document.getElementById("exportJsonBtn").addEventListener("click", () => { window.location.href = "/api/export.json"; });
      window.addEventListener("resize", resizeCanvas);
      window.addEventListener("pagehide", stopCamera);

      updateConfigPreview();
      renderHistory([]);
      updateSentenceDisplay();

      checkBackend();
