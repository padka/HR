(function () {
  const NotificationCenter = {
    root: null,
    endpoint: "/api/notifications/feed",
    pollInterval: 12000,
    seeded: false,
    afterId: null,
    timer: null,

    init(options = {}) {
      this.root = document.getElementById(options.rootId || "toast-root");
      if (!this.root) {
        return;
      }
      this.endpoint = options.endpoint || this.endpoint;
      this.pollInterval = Math.max(5000, options.pollInterval || this.pollInterval);
      this.seeded = false;
      this.afterId = null;
      this.poll(true);
      this.timer = window.setInterval(() => this.poll(), this.pollInterval);
    },

    tone(status) {
      const normalized = (status || "").toLowerCase();
      if (normalized === "sent") {
        return "success";
      }
      if (normalized === "failed") {
        return "danger";
      }
      if (normalized === "pending") {
        return "warning";
      }
      return "info";
    },

    typeLabel(type) {
      const map = {
        interview_confirmed_candidate: "Подтверждение интервью",
        slot_reminder: "Напоминание",
        candidate_reschedule_prompt: "Напоминание о переносе",
      };
      if (type && map[type]) {
        return map[type];
      }
      return type || "Уведомление";
    },

    statusLabel(status) {
      const map = {
        sent: "Доставлено",
        failed: "Ошибка доставки",
        pending: "В очереди",
      };
      return map[status] || "Обновлено";
    },

    dismiss(toast) {
      if (!toast) {
        return;
      }
      toast.classList.remove("toast--visible");
      window.setTimeout(() => {
        if (toast.parentNode) {
          toast.parentNode.removeChild(toast);
        }
      }, 250);
    },

    show(item) {
      const toast = document.createElement("section");
      toast.className = `toast toast--${this.tone(item.status)}`;
      const createdAt = item.created_at ? new Date(item.created_at) : new Date();
      const timeLabel = createdAt.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
      toast.innerHTML = `
        <button class="toast__close" type="button" aria-label="Закрыть уведомление">×</button>
        <div class="toast__body">
          <p class="toast__title">${this.typeLabel(item.type)}</p>
          <p class="toast__text">${this.statusLabel(item.status)}</p>
          <p class="toast__meta">${timeLabel}</p>
        </div>
      `;
      toast.querySelector(".toast__close").addEventListener("click", () => this.dismiss(toast));
      this.root.appendChild(toast);
      window.requestAnimationFrame(() => toast.classList.add("toast--visible"));
      window.setTimeout(() => this.dismiss(toast), 8000);
      while (this.root.children.length > 5) {
        this.root.removeChild(this.root.firstChild);
      }
    },

    async poll(initial = false) {
      if (!this.root) {
        return;
      }
      try {
        const url = new URL(this.endpoint, window.location.origin);
        if (this.afterId) {
          url.searchParams.set("after_id", String(this.afterId));
        }
        const response = await fetch(url.toString(), { headers: { Accept: "application/json" } });
        if (!response.ok) {
          return;
        }
        const data = await response.json();
        const items = Array.isArray(data.items) ? data.items : [];
        if (!this.seeded) {
          if (data.latest_id) {
            this.afterId = data.latest_id;
          } else if (items.length) {
            this.afterId = items[items.length - 1].id;
          }
          this.seeded = true;
          return;
        }
        if (!items.length) {
          if (data.latest_id) {
            this.afterId = data.latest_id;
          }
          return;
        }
        items.forEach((item) => {
          this.afterId = item.id;
          this.show(item);
        });
      } catch (err) {
        // Silently ignore networking issues
      }
    },
  };

  function bootstrap() {
    NotificationCenter.init();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootstrap);
  } else {
    bootstrap();
  }

  window.TGNotificationCenter = NotificationCenter;
})();
