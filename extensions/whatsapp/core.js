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

  /* O editor do WhatsApp (Lexical) guarda o texto em spans proprios e o atualiza um instante DEPOIS do comando de digitar:
   * le-se so o que a pessoa de fato ve (nunca o texto de dica) e confere-se depois de esperar o editor. */
  function readText(el) {
    if (!el) return "";
    var spans = el.querySelectorAll('[data-lexical-text="true"]');
    if (spans.length) {
      return Array.prototype.map
        .call(spans, function (n) {
          return n.textContent || "";
        })
        .join("")
        .trim();
    }
    return (el.textContent || "").trim();
  }

  function composerText(doc) {
    return readText(composer(doc));
  }

  /* Apaga o que ha no campo (como selecionar tudo e apagar). Usado para nao deixar rascunho solto quando algo da errado. */
  function clearField(doc, el) {
    if (!el) return;
    el.focus();
    try {
      var view = doc.defaultView || g;
      var range = doc.createRange();
      range.selectNodeContents(el);
      var sel = view.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
      doc.execCommand("delete");
    } catch (e) {
      /* sem selecao: tenta o jeito simples */
    }
    if (readText(el) !== "") {
      el.textContent = "";
      var v2 = doc.defaultView || g;
      el.dispatchEvent(new v2.InputEvent("input", { bubbles: true, data: "", inputType: "deleteContentBackward" }));
    }
  }

  function wait(ms) {
    return new Promise(function (r) {
      setTimeout(r, ms);
    });
  }

  /* Digita em um campo editavel como uma pessoa. Devolve uma promessa: o editor demora um instante para mostrar o texto,
   * e conferir antes disso fazia o Jefrey digitar de novo (texto duplicado) e desistir de enviar. */
  async function insertInto(doc, el, text, sleep) {
    if (!el) return false;
    var pause = sleep || wait;
    el.focus();
    var done = false;
    try {
      done = !!(doc.execCommand && doc.execCommand("insertText", false, text));
    } catch (e) {
      done = false;
    }
    for (var i = 0; i < 6; i++) {
      await pause(done ? 250 : 100);
      if (readText(el) === text.trim()) return true;
    }
    // nao apareceu (ou apareceu errado): limpa e tenta UMA vez pelo jeito alternativo
    clearField(doc, el);
    el.textContent = text;
    var view = doc.defaultView || g;
    el.dispatchEvent(new view.InputEvent("input", { bubbles: true, data: text, inputType: "insertText" }));
    await pause(300);
    if (readText(el) === text.trim()) return true;
    clearField(doc, el); // nunca deixa texto pela metade
    return false;
  }

  function typeText(doc, text, sleep) {
    return insertInto(doc, composer(doc), text, sleep);
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

  function typeInSearch(doc, text, sleep) {
    return insertInto(doc, searchBox(doc), text, sleep);
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

  /* ---- lista de conversas: quem escreveu, previa e nao lidas (sem abrir nenhuma conversa) ---- */
  var TIME_RX = /^(\d{1,2}[:h]\d{2}|ontem|hoje|yesterday|today|\d{1,2}\/\d{1,2}(\/\d{2,4})?|seg|ter|qua|qui|sex|s[aá]b|dom)\.?$/i;

  function cellUnread(el) {
    var found = 0;
    Array.prototype.forEach.call(el.querySelectorAll("[aria-label]"), function (n) {
      var label = n.getAttribute("aria-label") || "";
      var m = label.match(/(\d+)\s*(mensagens?\s*)?(n[aã]o\s*lidas?|unread)/i);
      if (m) found = Math.max(found, parseInt(m[1], 10));
      else if (/(n[aã]o\s*lida|unread)/i.test(label) && !found) found = 1;
    });
    return found;
  }

  /* Previa de grupo: "Fulano: texto". "Voce: texto" e conversa individual onde a ultima mensagem foi da pessoa. */
  function looksLikeGroupPreview(prev) {
    var m = /^([^:]{1,40}):\s/.exec(String(prev || ""));
    return !!m && !/^(voc[eê]|you)$/i.test(m[1].trim());
  }

  function cellPreview(el, title, unread) {
    var st = el.querySelector('[data-testid="last-msg-status"]'); // o WhatsApp de hoje: a previa tem um marcador proprio
    if (st) {
      var tt = (st.textContent || "").trim();
      if (tt) return tt.slice(0, 120);
    }
    var best = "";
    Array.prototype.forEach.call(el.querySelectorAll("span[dir], span[title]"), function (n) {
      var t = (n.getAttribute("title") || n.textContent || "").trim();
      if (!t || sameChat(t, title) || TIME_RX.test(t) || (unread && t === String(unread))) return;
      if (t.length > best.length) best = t;
    });
    return best.slice(0, 120);
  }

  function parseSidebar(doc) {
    var seen = {};
    var out = [];
    for (var i = 0; i < CELL_SELECTORS.length && !out.length; i++) {
      Array.prototype.forEach.call(doc.querySelectorAll(CELL_SELECTORS[i]), function (cell) {
        var title = cellTitle(cell);
        var key = norm(title);
        if (!key || seen[key]) return;
        seen[key] = true;
        var unread = cellUnread(cell);
        var preview = cellPreview(cell, title, unread);
        out.push({
          title: title,
          preview: preview,
          unread: unread,
          // grupo: icone de grupo OU previa "Fulano: texto" (na duvida, trata como grupo: o Jefrey nunca mostra nem guarda grupos)
          group: !!cell.querySelector('[data-icon*="group"]') || looksLikeGroupPreview(preview),
        });
      });
    }
    return out.slice(0, 40);
  }

  /* A conversa da pessoa com ela mesma ("Nome (Você)"): e por ali que ela escreve para o Jefrey. */
  var SELF_RX = /\((voc[eê]|you|tu|eu)\)\s*$/i;
  var BOT_MARK = "🤖";

  function isSelfChat(title) {
    return SELF_RX.test(String(title || "").trim());
  }

  function isBotText(text) {
    return String(text || "").trim().indexOf(BOT_MARK) === 0;
  }

  /* Mensagens que a pessoa escreveu para si mesma e o Jefrey ainda nao viu (as respostas do proprio Jefrey comecam com o robozinho). */
  function newCommands(rows, seen) {
    return rows.filter(function (r) {
      return r.from_me && r.kind === "text" && r.text && !isBotText(r.text) && !seen.has(r.id);
    });
  }

  var api = {
    parseSidebar: parseSidebar, looksLikeGroupPreview: looksLikeGroupPreview, isSelfChat: isSelfChat, isBotText: isBotText, newCommands: newCommands,
    norm: norm, sameChat: sameChat, chatTitle: chatTitle, isGroup: isGroup, parseRows: parseRows, newIncoming: newIncoming,
    context: context, composer: composer, sendButton: sendButton, composerText: composerText, typeText: typeText,
    canSendNow: canSendNow, readText: readText, clearField: clearField, humanDelayMs: humanDelayMs,
    findChatCell: findChatCell, openChat: openChat, typeInSearch: typeInSearch, clearSearch: clearSearch, searchBox: searchBox,
  };
  if (typeof module === "object" && module.exports) module.exports = api;
  g.JefreyWACore = api;
})(typeof globalThis !== "undefined" ? globalThis : typeof self !== "undefined" ? self : this);
