(function () {
  "use strict";

  var KEY = "sec_advanced_settings";

  if (new URLSearchParams(window.location.search).get("menu") !== KEY) {
    return;
  }

  if (window.MtSecAdv && typeof window.MtSecAdv.wire === "function") {
    window.MtSecAdv.wire();
    return;
  }

  var definitions = [
    {
      name: "status_ipbx_frontend",
      type: "checkbox",
      title: "فعال‌سازی دسترسی مستقیم به کنسول",
      help: "دسترسی مستقیم به کنسول IssabelPBX را خارج از محیط یکپارچه فعال می‌کند.",
      card: 0
    },
    {
      name: "status_anonymous_sip",
      type: "checkbox",
      title: "تماس‌های SIP ناشناس",
      help: "پذیرش تماس‌های ناشناس می‌تواند خطر سوءاستفاده را افزایش دهد؛ فقط در صورت نیاز فعال کنید.",
      card: 0
    },
    {
      name: "ipbx_password",
      type: "password",
      title: "رمز عبور جدید",
      help: "رمز مربوط به پایگاه داده و مدیریت وب IssabelPBX است.",
      card: 1
    },
    {
      /* Stock spelling is intentional. */
      name: "ipbx_confirm_passwrod",
      type: "password",
      title: "تکرار رمز",
      help: "همان رمز عبور جدید را دوباره وارد کنید.",
      card: 1
    }
  ];

  var sequence = 0;
  var queued = false;
  var observer;

  function node(tag, className, text) {
    var element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function uniqueId(prefix) {
    var id;
    do {
      sequence += 1;
      id = prefix + "-" + sequence;
    } while (document.getElementById(id));
    return id;
  }

  function normalize(value) {
    return String(value || "")
      .replace(/ي/g, "ی")
      .replace(/ك/g, "ک")
      .replace(/[\u200c\u200e\u200f\u202a-\u202e\u2066-\u2069]/g, "")
      .replace(/[:：*]/g, "")
      .replace(/\s+/g, " ")
      .trim()
      .toLowerCase();
  }

  var stockLabels = new Set([
    "Enable direct access (Non-embedded) to IssabelPBX:",
    "Enable anonymous SIP calls:",
    "Database and Web Administration IssabelPBX Password:",
    "Change Password:",
    "Password:",
    "New Password:",
    "Confirm Password:",
    "Password Confirmation:",
    "فعال کردن دسترسي",
    "فعال کردن دسترسی",
    "تغيير رمز",
    "تغییر رمز",
    "تغيير رمز عبور",
    "تغییر رمز عبور",
    "رمز عبور",
    "تاييد رمز",
    "تایید رمز",
    "تأیید رمز",
    "تکرار رمز"
  ].map(normalize));

  function findInput(definition) {
    var matches = Array.prototype.filter.call(
      document.querySelectorAll("input"),
      function (input) {
        return input.type === definition.type &&
          (input.name === definition.name || input.id === definition.name);
      }
    );
    return matches.length === 1 ? matches[0] : null;
  }

  function appendToken(element, attribute, token) {
    var tokens = (element.getAttribute(attribute) || "")
      .split(/\s+/)
      .filter(Boolean);
    if (tokens.indexOf(token) === -1) tokens.push(token);
    element.setAttribute(attribute, tokens.join(" "));
  }

  function isSubmit(element) {
    return element.tagName === "INPUT"
      ? element.type === "submit"
      : element.tagName === "BUTTON" && element.type === "submit";
  }

  function findActionTable(form, source) {
    var candidates = Array.prototype.filter.call(
      form.querySelectorAll("table"),
      function (table) {
        if (table === source || source.contains(table) ||
            table.contains(source) || table.rows.length !== 1) {
          return false;
        }

        var controls = Array.prototype.slice.call(
          table.querySelectorAll("input, button, select, textarea")
        );

        var submits = controls.filter(function (control) {
          return isSubmit(control) && control.form === form;
        });

        if (!submits.length) return false;

        /* Never relocate a search/filter table or another form's controls. */
        return controls.every(function (control) {
          return control.form === form &&
            (isSubmit(control) ||
             (control.tagName === "INPUT" && control.type === "hidden"));
        });
      }
    );

    /* Ambiguity must leave the stock layout usable. */
    return candidates.length === 1 ? candidates[0] : null;
  }

  function createCard(title, introduction) {
    var section = node("section", "mt-secadv__card");
    var header = node("div", "mt-secadv__header");
    var heading = node("h2", "mt-secadv__title", title);
    var fields = node("div", "mt-secadv__fields");

    heading.id = uniqueId("mt-secadv-heading");
    section.setAttribute("aria-labelledby", heading.id);
    header.appendChild(heading);
    header.appendChild(node("p", "mt-secadv__intro", introduction));
    section.appendChild(header);
    section.appendChild(fields);

    return { section: section, fields: fields };
  }

  function buildField(definition, input, cell) {
    var field = node(
      "div",
      "mt-secadv__field mt-secadv__field--" +
        (definition.type === "checkbox" ? "toggle" : "password")
    );
    var copy = node("div", "mt-secadv__copy");
    var label = node("label", "mt-secadv__label", definition.title);
    var help = node("p", "mt-secadv__help", definition.help);
    var control = node("div", "mt-secadv__control");

    if (!input.id) input.id = uniqueId("mt-secadv-input");
    label.id = uniqueId("mt-secadv-label");
    label.htmlFor = input.id;
    help.id = uniqueId("mt-secadv-help");

    /* Override a legacy accessible English name without deleting its label. */
    input.setAttribute("aria-labelledby", label.id);
    appendToken(input, "aria-describedby", help.id);

    copy.appendChild(label);
    copy.appendChild(help);
    field.appendChild(copy);
    field.appendChild(control);

    /* Move original nodes; never clone or recreate a successful control. */
    while (cell.firstChild) {
      control.appendChild(cell.firstChild);
    }

    if (definition.type === "checkbox") {
      var switchElement = node("span", "mt-secadv__switch");
      var track = node("span", "mt-secadv__track");
      track.setAttribute("aria-hidden", "true");

      input.parentNode.insertBefore(switchElement, input);
      switchElement.appendChild(input);
      switchElement.appendChild(track);
    } else {
      input.classList.add("mt-secadv__password");
      input.setAttribute("autocomplete", "new-password");
    }

    return field;
  }

  function cleanSource(source) {
    Array.prototype.forEach.call(source.rows, function (row) {
      Array.prototype.forEach.call(row.cells, function (cell) {
        /* Do not hide unknown controls, messages, links or interactive help. */
        var protectedContent = cell.querySelector(
          "input, select, textarea, button, a, img, svg, " +
          "[role='alert'], [aria-live], .error, .errors, .alert, " +
          ".validation-error, [id]"
        );

        if (protectedContent) return;

        var text = normalize(cell.textContent);

        if (!text) {
          cell.classList.add("mt-secadv__legacy-empty");
        } else if (stockLabels.has(text)) {
          cell.classList.add("mt-secadv__legacy-label");
        }
      });
    });
  }

  function wire() {
    if (!document.body) return false;
    document.body.classList.add("mt-secadv-page");

    if (document.querySelector(".mt-secadv")) return true;

    var inputs = definitions.map(findInput);
    if (inputs.some(function (input) { return !input; })) return false;

    var form = inputs[0].form;
    var source = inputs[0].closest("table.tabForm");
    if (!form || !source || !form.contains(source)) return false;

    if (!inputs.every(function (input) {
      return input.form === form &&
        input.closest("table.tabForm") === source;
    })) {
      return false;
    }

    var cells = inputs.map(function (input) {
      return input.closest("td");
    });

    /* The supplied stock layout has one target control per value cell.
       A different template is left untouched rather than partially rebuilt. */
    if (cells.some(function (cell) { return !cell; }) ||
        new Set(cells).size !== inputs.length) {
      return false;
    }

    if (!cells.every(function (cell, index) {
      var visibleControls = Array.prototype.filter.call(
        cell.querySelectorAll("input, select, textarea, button"),
        function (control) {
          return !(control.tagName === "INPUT" && control.type === "hidden");
        }
      );
      return visibleControls.length === 1 &&
        visibleControls[0] === inputs[index];
    })) {
      return false;
    }

    var actionTable = findActionTable(form, source);
    if (!actionTable) return false;

    var root = node("div", "mt-secadv");
    var grid = node("div", "mt-secadv__grid");
    var cards = [
      createCard(
        "دسترسی و امنیت تماس",
        "دسترسی به کنسول و پذیرش تماس‌های ناشناس را مدیریت کنید."
      ),
      createCard(
        "تغییر رمز عبور",
        "رمز جدید و تکرار آن باید یکسان باشند."
      )
    ];
    var actions = node("div", "mt-secadv__actions");

    root.lang = "fa";
    root.dir = "rtl";

    cards.forEach(function (card) {
      grid.appendChild(card.section);
    });

    root.appendChild(grid);
    root.appendChild(actions);

    /* This insertion keeps every relocated control inside its original form. */
    source.parentNode.insertBefore(root, source);

    definitions.forEach(function (definition, index) {
      cards[definition.card].fields.appendChild(
        buildField(definition, inputs[index], cells[index])
      );
    });

    actions.appendChild(node(
      "p",
      "mt-secadv__action-note",
      "برای ثبت تغییرات، ذخیره را بزنید و پیام نتیجه را بررسی کنید."
    ));

    actionTable.classList.add("mt-secadv__action-table");
    Array.prototype.forEach.call(
      actionTable.querySelectorAll("input, button"),
      function (control) {
        if (isSubmit(control)) {
          control.classList.add("mt-secadv__submit");
        }
      }
    );
    actions.appendChild(actionTable);

    source.classList.add("mt-secadv__source");
    cleanSource(source);

    /* No change/submit interception, synthetic clicks or password copying. */
    return true;
  }

  function schedule() {
    if (queued) return;
    queued = true;
    window.requestAnimationFrame(function () {
      queued = false;
      if (wire() && observer) {
        observer.disconnect();
        observer = null;
      }
    });
  }

  function start() {
    if (wire()) return;

    /* Supports scripts loaded before the module markup arrives. */
    observer = new MutationObserver(schedule);
    observer.observe(document.body, { childList: true, subtree: true });
  }

  window.MtSecAdv = { wire: wire };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
}());
