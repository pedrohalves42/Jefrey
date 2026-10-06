/* Jefrey para WhatsApp Web: logica pura (sem timers nem rede), testada contra uma pagina simulada.
 * Os seletores do WhatsApp mudam de tempos em tempos: tudo que depende deles fica AQUI, em um lugar so. */
(function (g) {
  "use strict";

  function norm(s) {
    return String(s || "")
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .replace(/[^a-z0-9+ ]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function sameChat(a, b) {
    const x = norm(a);
    return x !== "" && x === norm(b);
  }

  var TITLE_SELECTORS = [
    '#main header [data-testid="conversation-info-header-chat-title"]',
    "#main header span[dir='auto'][title]",
    "#main header span[dir='auto']",
  ];

  function chatTitle(doc) {
    for (var i = 0; i < TITLE_SELECTORS.length; i++) {
      var el = doc.querySelector(TITLE_SELECTORS[i]);
      if (el) {
        var t = (el.getAttribute("title") || el.textContent || "").trim();
        if (t) return t.slice(0, 100);
      }
    }
    return "";
  }

  function rowNodes(doc) {
    return Array.prototype.slice.call(doc.querySelectorAll("#main [data-id]")).filter(function (el) {
      return /^(true|false)_/.test(el.getAttribute("data-id") || "");
    });
  }

  /* Grupo: o identificador das mensagens termina em @g.us. Grupos nunca sao atendidos. */
  function isGroup(doc) {
    return rowNodes(doc).some(function (el) {
      return (el.getAttribute("data-id") || "").indexOf("@g.us") !== -1;
    });
  }

  var TEXT_SELECTORS = ["span.selectable-text.copyable-text", '[data-testid="selectable-text"]', "span.selectable-text"];

  function rowText(el) {
    for (var i = 0; i < TEXT_SELECTORS.length; i++) {
      var nodes = el.querySelectorAll(TEXT_SELECTORS[i]);
      if (nodes.length) {
        return Array.prototype.map
          .call(nodes, function (n) {
            return n.textContent || "";
          })
          .join("\n")
          .trim();
      }
    }
    return "";
  }

  /* [{id, text, from_me, kind}] na ordem da tela. kind: "text" ou "other" (audio, imagem, figurinha...). */
  function parseRows(doc) {
    return rowNodes(doc).map(function (el) {
      var id = el.getAttribute("data-id") || "";
      var text = rowText(el);
      // sem texto = audio, imagem, figurinha ou outro tipo: o Jefrey nunca responde sozinho a isso (pede aprovacao)
      return { id: id, text: text.slice(0, 2000), from_me: id.indexOf("true_") === 0, kind: text ? "text" : "other" };
    });
  }

  function newIncoming(rows, seen) {
    return rows.filter(function (r) {
      return !r.from_me && !seen.has(r.id);
    });
  }

  function context(rows, n) {
    return rows.slice(-(n || 6)).map(function (r) {
      return { text: r.text, from_me: r.from_me };
    });
  }

  function composer(doc) {
    return doc.querySelector('footer div[contenteditable="true"][data-tab="10"]') || doc.querySelector('footer div[contenteditable="true"]');
  }

  function sendButton(doc) {
    var b = doc.querySelector('footer button[aria-label="Enviar"], footer button[aria-label="Send"]');
    if (b) return b;
    var icon = doc.querySelector('footer [data-icon="send"]');
    return icon ? icon.closest("button") || icon : null;
  }

  function composerText(doc) {
    var c = composer(doc);
    return c ? (c.textContent || "").trim() : "";
  }

  /* Digita em um campo editavel como uma pessoa (o editor do WhatsApp ignora simples troca de texto). */
  function insertInto(doc, el, text) {
    if (!el) return false;
    el.focus();
    var done = false;
    try {
      done = !!(doc.execCommand && doc.execCommand("insertText", false, text));
    } catch (e) {
      done = false;
    }
    if (!done || (el.textContent || "").trim() !== text.trim()) {
      el.textContent = text;
      var view = doc.defaultView || g;
      el.dispatchEvent(new view.InputEvent("input", { bubbles: true, data: text, inputType: "insertText" }));
    }
    return (el.textContent || "").trim() === text.trim();
  }

  function typeText(doc, text) {
    return insertInto(doc, composer(doc), text);
  }

  /* ---- abrir a conversa certa (so para enviar o que a pessoa aprovou) ---- */
  var CELL_SELECTORS = ['#pane-side [data-testid="cell-frame-container"]', '#pane-side [role="listitem"]', '#pane-side [role="row"]'];

  function cellTitle(el) {
    var t = el.querySelector("span[title]");
    var s = t ? t.getAttribute("title") : "";
    if (!s) {
      var d = el.querySelector("span[dir='auto']");
      s = d ? d.textContent : "";
    }
    return (s || "").trim().slice(0, 100);
  }

  function findChatCell(doc, chat) {
    for (var i = 0; i < CELL_SELECTORS.length; i++) {
      var cells = Array.prototype.slice.call(doc.querySelectorAll(CELL_SELECTORS[i]));
      for (var j = 0; j < cells.length; j++) {
        if (sameChat(cellTitle(cells[j]), chat)) return cells[j];
      }
    }
    return null;
  }

  /* Clica na conversa da lista lateral. Nunca clica em grupo (o nome so e comparado por igualdade exata, sem acento/maiuscula). */
  function openChat(doc, chat) {
    var cell = findChatCell(doc, chat);
    if (!cell) return { ok: false, why: "nao-achei" };
    var view = doc.defaultView || g;
    ["mousedown", "mouseup", "click"].forEach(function (type) {
      cell.dispatchEvent(new view.MouseEvent(type, { bubbles: true, cancelable: true }));
    });
    return { ok: true, why: "" };
  }

  function searchBox(doc) {
    return doc.querySelector('#side div[contenteditable="true"][data-tab="3"]') || doc.querySelector('#side div[contenteditable="true"]');
  }

  function typeInSearch(doc, text) {
    return insertInto(doc, searchBox(doc), text);
  }

  function clearSearch(doc) {
    var b = searchBox(doc);
    if (b) {
      b.textContent = "";
      var view = doc.defaultView || g;
      b.dispatchEvent(new view.InputEvent("input", { bubbles: true, data: "", inputType: "deleteContentBackward" }));
    }
  }

  /* Seguranca antes de enviar: so no chat certo, so com o campo vazio (nunca apaga o que a pessoa esta digitando). */
  function canSendNow(doc, chat) {
    if (!sameChat(chatTitle(doc), chat)) return { ok: false, why: "outro-chat" };
    if (!composer(doc)) return { ok: false, why: "sem-campo" };
    if (composerText(doc) !== "") return { ok: false, why: "digitando" };
    return { ok: true, why: "" };
  }

  /* Pausa humana entre ler e responder (5 a 14 segundos), para nao parecer robo e dar tempo de a pessoa mudar de ideia. */
  function humanDelayMs(rand) {
    var r = typeof rand === "number" ? rand : Math.random();
    return 5000 + Math.floor(r * 9000);
  }

  var api = {
    norm: norm, sameChat: sameChat, chatTitle: chatTitle, isGroup: isGroup, parseRows: parseRows, newIncoming: newIncoming,
    context: context, composer: composer, sendButton: sendButton, composerText: composerText, typeText: typeText,
    canSendNow: canSendNow, humanDelayMs: humanDelayMs,
    findChatCell: findChatCell, openChat: openChat, typeInSearch: typeInSearch, clearSearch: clearSearch, searchBox: searchBox,
  };
  if (typeof module === "object" && module.exports) module.exports = api;
  g.JefreyWACore = api;
})(typeof globalThis !== "undefined" ? globalThis : typeof self !== "undefined" ? self : this);
