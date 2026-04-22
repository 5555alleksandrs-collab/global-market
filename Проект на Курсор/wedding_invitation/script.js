(function () {
  "use strict";

  var WEDDING_MS = new Date("2026-08-15T15:00:00").getTime();

  function pad(n) {
    return String(n).padStart(2, "0");
  }

  function tickCountdown() {
    var root = document.getElementById("countdown");
    var doneEl = document.getElementById("countdown-done");
    if (!root) return;

    function update() {
      var now = Date.now();
      var diff = WEDDING_MS - now;

      if (diff <= 0) {
        root.classList.add("hidden");
        if (doneEl) doneEl.classList.remove("hidden");
        return;
      }

      var s = Math.floor(diff / 1000);
      var days = Math.floor(s / 86400);
      var hours = Math.floor((s % 86400) / 3600);
      var minutes = Math.floor((s % 3600) / 60);
      var seconds = s % 60;

      var map = {
        days: pad(days),
        hours: pad(hours),
        minutes: pad(minutes),
        seconds: pad(seconds),
      };

      root.querySelectorAll("[data-unit]").forEach(function (el) {
        var u = el.getAttribute("data-unit");
        if (map[u] !== undefined) el.textContent = map[u];
      });
    }

    update();
    setInterval(update, 1000);
  }

  function initReveal() {
    var reduced =
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    var nodes = document.querySelectorAll(".reveal");
    if (reduced) {
      nodes.forEach(function (el) {
        el.classList.add("is-visible");
      });
      return;
    }

    if (!("IntersectionObserver" in window)) {
      nodes.forEach(function (el) {
        el.classList.add("is-visible");
      });
      return;
    }

    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            io.unobserve(entry.target);
          }
        });
      },
      { root: null, rootMargin: "0px 0px -8% 0px", threshold: 0.08 }
    );

    nodes.forEach(function (el) {
      if (el.classList.contains("is-visible")) return;
      io.observe(el);
    });
  }

  function initForm() {
    var form = document.getElementById("rsvp-form");
    var note = document.getElementById("rsvp-note");
    if (!form || !note) return;

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var first = form.querySelector('[name="firstname"]');
      var last = form.querySelector('[name="lastname"]');
      var attend = form.querySelector('[name="attend"]:checked');

      if (!first || !first.value.trim()) {
        note.textContent = "Пожалуйста, укажите имя.";
        return;
      }
      if (!last || !last.value.trim()) {
        note.textContent = "Пожалуйста, укажите фамилию.";
        return;
      }
      if (!attend) {
        note.textContent = "Выберите, пожалуйста, вариант участия.";
        return;
      }

      note.textContent =
        "Спасибо! Ваш ответ принят — мы с нетерпением ждём встречи.";

      form.querySelectorAll("input, textarea, button").forEach(function (el) {
        if (el.type === "submit") return;
        el.disabled = true;
      });
      form.querySelector("button[type='submit']").disabled = true;
    });
  }

  function initMusic() {
    var audio = document.getElementById("bg-music");
    var btn = document.getElementById("music-toggle");
    var wrap = document.getElementById("music-player");
    if (!audio || !btn || !wrap) return;

    var iconPlay = btn.querySelector(".music-player__icon--play");
    var iconPause = btn.querySelector(".music-player__icon--pause");

    audio.volume = 0.45;

    function setPlaying(playing) {
      btn.setAttribute("aria-pressed", playing ? "true" : "false");
      btn.setAttribute(
        "aria-label",
        playing ? "Выключить фоновую музыку" : "Включить фоновую музыку"
      );
      wrap.classList.toggle("music-player--playing", playing);
      if (iconPlay && iconPause) {
        iconPlay.classList.toggle("hidden", playing);
        iconPause.classList.toggle("hidden", !playing);
      }
    }

    function toggle() {
      if (audio.paused) {
        var p = audio.play();
        if (p && typeof p.catch === "function") {
          p.catch(function () {
            setPlaying(false);
          });
        } else {
          setPlaying(true);
        }
      } else {
        audio.pause();
        setPlaying(false);
      }
    }

    btn.addEventListener("click", function () {
      toggle();
    });

    audio.addEventListener("play", function () {
      setPlaying(true);
    });
    audio.addEventListener("pause", function () {
      if (!audio.ended) setPlaying(false);
    });

    audio.addEventListener("error", function () {
      btn.disabled = true;
      btn.setAttribute("aria-label", "Музыка недоступна — добавьте файл audio/music.mp3");
      wrap.classList.add("music-player--error");
    });
  }

  tickCountdown();
  initReveal();
  initForm();
  initMusic();
})();
