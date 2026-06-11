(function () {
  const NAMESPACE = "YesodAdminTour";
  const ROOT_ID = "yesod-admin-tour-root";
  const LAUNCHER_ID = "yesod-admin-tour-launcher";
  const WAIT_TIMEOUT_MS = 6000;
  const WAIT_INTERVAL_MS = 100;

  function getDriverFactory() {
    return window.driver && window.driver.js && window.driver.js.driver;
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function waitForElement(selector) {
    return new Promise((resolve) => {
      const startedAt = Date.now();
      const timer = window.setInterval(() => {
        const element = document.querySelector(selector);
        if (element) {
          window.clearInterval(timer);
          resolve(element);
          return;
        }
        if (Date.now() - startedAt > WAIT_TIMEOUT_MS) {
          window.clearInterval(timer);
          resolve(null);
        }
      }, WAIT_INTERVAL_MS);
    });
  }

  function updateQuery(config, pageId, stepIndex) {
    const url = new URL(window.location.href);
    url.searchParams.set(config.query.page, pageId);
    url.searchParams.set(config.query.tour, "1");
    url.searchParams.set(config.query.step, String(stepIndex));
    window.location.href = url.toString();
  }

  function clearTourQuery(config) {
    const url = new URL(window.location.href);
    url.searchParams.delete(config.query.tour);
    url.searchParams.delete(config.query.step);
    window.history.replaceState({}, "", url.toString());
  }

  function normalizeStepIndex(config, stepIndex) {
    if (!Number.isInteger(stepIndex) || stepIndex < 0) {
      return 0;
    }
    if (stepIndex >= config.steps.length) {
      return config.steps.length - 1;
    }
    return stepIndex;
  }

  async function driveStep(config, requestedIndex) {
    const driverFactory = getDriverFactory();
    if (!driverFactory || !config || !Array.isArray(config.steps) || config.steps.length === 0) {
      return;
    }

    const stepIndex = normalizeStepIndex(config, requestedIndex);
    const step = config.steps[stepIndex];

    if (step.pageId !== config.pageId) {
      updateQuery(config, step.pageId, stepIndex);
      return;
    }

    const element = await waitForElement(step.selector);
    const targetSelector = element ? step.selector : config.fallbackSelector;
    const tour = driverFactory({
      animate: !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
      allowClose: true,
      overlayOpacity: 0.56,
      smoothScroll: true,
      showButtons: ["next", "close"],
      popoverClass: "yesod-admin-tour-popover",
      doneBtnText: escapeHtml(stepIndex + 1 >= config.steps.length ? config.labels.done : config.labels.next),
      nextBtnText: escapeHtml(config.labels.next),
      prevBtnText: escapeHtml(config.labels.previous),
      progressText: escapeHtml(config.labels.progress),
      onDestroyed: () => clearTourQuery(config),
      steps: [
        {
          element: targetSelector,
          popover: {
            title: `${stepIndex + 1}/${config.steps.length} · ${escapeHtml(step.title)}`,
            description: element ? escapeHtml(step.description) : escapeHtml(config.labels.missingTarget),
            side: step.side || "bottom",
            align: step.align || "start",
            onNextClick: () => {
              tour.destroy();
              if (stepIndex + 1 >= config.steps.length) {
                clearTourQuery(config);
                return;
              }
              driveStep(config, stepIndex + 1);
            },
            onPrevClick: () => {
              tour.destroy();
              if (stepIndex === 0) {
                driveStep(config, 0);
                return;
              }
              driveStep(config, stepIndex - 1);
            },
          },
        },
      ],
    });

    tour.drive();
  }

  function ensureLauncher(config) {
    let root = document.getElementById(ROOT_ID);
    if (!root) {
      root = document.createElement("div");
      root.id = ROOT_ID;
      document.body.appendChild(root);
    }

    let button = document.getElementById(LAUNCHER_ID);
    if (!button) {
      button = document.createElement("button");
      button.id = LAUNCHER_ID;
      button.className = "yesod-tour-launcher";
      button.type = "button";
      root.appendChild(button);
    }

    button.textContent = config.labels.launcher;
    button.setAttribute("aria-label", config.labels.launcherAria);
    button.onclick = () => driveStep(config, 0);
  }

  window[NAMESPACE] = {
    mount(config) {
      if (!config || !Array.isArray(config.steps)) {
        return;
      }
      ensureLauncher(config);
      const params = new URLSearchParams(window.location.search);
      if (params.get(config.query.tour) === "1") {
        driveStep(config, Number.parseInt(params.get(config.query.step) || "0", 10));
      }
    },
  };
})();
