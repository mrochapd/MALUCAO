/* Malucão Eventos — comportamentos da interface (sem dependências além do Bootstrap). */
(function () {
  "use strict";

  // ---------------------------------------------------------------- Menu lateral (celular)
  const sidebar = document.querySelector(".sidebar");
  const fundo = document.querySelector(".sidebar-fundo");
  const botoesMenu = document.querySelectorAll("[data-abrir-menu]");
  function menu(abrir) {
    if (!sidebar) return;
    sidebar.classList.toggle("aberta", abrir);
    if (fundo) fundo.classList.toggle("visivel", abrir);
    document.body.classList.toggle("menu-aberto", abrir);
    botoesMenu.forEach((b) => b.setAttribute("aria-expanded", String(abrir)));
    if (abrir) { const f = sidebar.querySelector("[data-fechar-menu]"); if (f) f.focus(); }
  }
  botoesMenu.forEach((btn) => btn.addEventListener("click", () => menu(!sidebar.classList.contains("aberta"))));
  document.querySelectorAll("[data-fechar-menu]").forEach((btn) => btn.addEventListener("click", () => menu(false)));
  if (fundo) fundo.addEventListener("click", () => menu(false));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") menu(false); });
  window.matchMedia("(min-width: 992px)").addEventListener("change", (e) => { if (e.matches) menu(false); });

  // ---------------------------------------------------------------- Login: foco e mostrar senha
  // No celular o foco automático abriria o teclado e esconderia a tela; só focamos no computador.
  const focoDesktop = document.querySelector("[data-foco-desktop]");
  if (focoDesktop && window.matchMedia("(min-width: 861px) and (hover: hover)").matches) focoDesktop.focus();
  document.querySelectorAll("[data-mostrar-senha]").forEach((btn) =>
    btn.addEventListener("click", () => {
      const campo = document.getElementById(btn.dataset.mostrarSenha);
      const mostrar = campo.type === "password";
      campo.type = mostrar ? "text" : "password";
      btn.setAttribute("aria-pressed", String(mostrar));
      btn.setAttribute("aria-label", mostrar ? "Ocultar senha" : "Mostrar senha");
      btn.querySelector("i").className = mostrar ? "bi bi-eye-slash" : "bi bi-eye";
    })
  );

  // ---------------------------------------------------------------- Máscara e verificação de CPF
  const digitos = (v) => (v || "").replace(/\D/g, "");
  const formatarCPF = (v) => {
    const d = digitos(v).slice(0, 11);
    return d
      .replace(/^(\d{3})(\d)/, "$1.$2")
      .replace(/^(\d{3})\.(\d{3})(\d)/, "$1.$2.$3")
      .replace(/\.(\d{3})(\d)/, ".$1-$2");
  };
  function cpfValido(valor) {
    const c = digitos(valor);
    if (c.length !== 11 || /^(\d)\1+$/.test(c)) return false;
    for (const t of [9, 10]) {
      let soma = 0;
      for (let i = 0; i < t; i++) soma += Number(c[i]) * (t + 1 - i);
      let d = (soma * 10) % 11;
      if (d === 10) d = 0;
      if (d !== Number(c[t])) return false;
    }
    return true;
  }

  document.querySelectorAll('[data-mascara="cpf"]').forEach((campo) => {
    const alerta = document.querySelector(".alerta-cpf");
    const urlVerificar = campo.dataset.verificar;
    let timer;
    campo.addEventListener("input", () => {
      campo.value = formatarCPF(campo.value);
      campo.classList.remove("is-valid", "is-invalid");
      if (alerta) alerta.style.display = "none";
      clearTimeout(timer);
      if (digitos(campo.value).length !== 11) return;
      if (!cpfValido(campo.value)) {
        campo.classList.add("is-invalid");
        return;
      }
      campo.classList.add("is-valid");
      if (!urlVerificar || !alerta) return;
      timer = setTimeout(async () => {
        const url = new URL(urlVerificar, window.location.origin);
        url.searchParams.set("cpf", digitos(campo.value));
        if (campo.dataset.excluir) url.searchParams.set("excluir", campo.dataset.excluir);
        try {
          const r = await fetch(url, { headers: { "X-Requested-With": "fetch" } });
          const dados = await r.json();
          if (dados.existe) {
            campo.classList.replace("is-valid", "is-invalid");
            alerta.querySelector("[data-nome]").textContent = dados.nome;
            alerta.querySelector("[data-link]").href = dados.url;
            alerta.querySelector("[data-link-inscricao]").href = dados.url_inscricao;
            alerta.style.display = "block";
          }
        } catch (e) { /* sem conexão: a validação do servidor continua valendo */ }
      }, 300);
    });
    if (campo.value) campo.value = formatarCPF(campo.value);
  });

  // ---------------------------------------------------------------- Inscrição: evento → pacote → modalidades
  const raiz = document.querySelector("[data-inscricao]");
  if (raiz) {
    const opcoes = JSON.parse(document.getElementById("opcoes-eventos").textContent);
    const selecionadas = new Set(JSON.parse(document.getElementById("modalidades-selecionadas").textContent));
    let pacoteAtual = JSON.parse(document.getElementById("pacote-selecionado").textContent);
    const prefixo = raiz.dataset.prefixo ? raiz.dataset.prefixo + "-" : "";
    const selEvento = raiz.querySelector(`select[name="${prefixo}evento"]`);
    const boxPacotes = raiz.querySelector("[data-pacotes]");
    const boxModalidades = raiz.querySelector("[data-modalidades]");
    const avisoEvento = raiz.querySelector("[data-aviso-evento]");
    const regra = raiz.querySelector("[data-regra]");
    const passos = raiz.querySelectorAll("[data-depende-evento]");
    const avisoSexo = raiz.querySelector("[data-aviso-sexo]");
    // sexo: do próprio formulário (cadastro) ou do atleta já cadastrado (data-sexo)
    const radiosSexo = document.querySelectorAll('input[name="sexo"]');
    const sexoAtual = () => {
      const marcado = [...radiosSexo].find((r) => r.checked);
      return marcado ? marcado.value : (raiz.dataset.sexo || "");
    };
    radiosSexo.forEach((r) => r.addEventListener("change", () => renderModalidades()));
    const aceitaSexo = (m, sexo) =>
      !sexo || (m.naipe === "masculino" ? sexo === "M" : m.naipe === "feminino" ? sexo === "F" : true);
    const bloqueio = (m) => (m.naipe === "masculino" ? "Só masculino" : "Só feminino");
    const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

    // guarda as marcações atuais antes de reconstruir a lista
    boxModalidades.addEventListener("change", (e) => {
      if (e.target.name !== prefixo + "modalidades") return;
      e.target.checked ? selecionadas.add(e.target.value) : selecionadas.delete(e.target.value);
      aplicarRegras();
    });
    boxPacotes.addEventListener("change", (e) => {
      if (e.target.name !== prefixo + "pacote") return;
      pacoteAtual = e.target.value;
      renderModalidades();
    });
    selEvento.addEventListener("change", () => { pacoteAtual = ""; render(); });

    function eventoAtual() { return opcoes[selEvento.value]; }
    function pacoteInfo() {
      const ev = eventoAtual();
      return ev ? ev.pacotes.find((p) => String(p.id) === String(pacoteAtual)) : null;
    }

    function render() {
      const ev = eventoAtual();
      passos.forEach((p) => (p.hidden = !ev));
      if (avisoEvento) {
        avisoEvento.hidden = !ev || ev.aceita;
        if (ev && !ev.aceita) avisoEvento.querySelector("span").textContent = `Inscrições fechadas: ${ev.motivo}.`;
      }
      if (!ev) { boxPacotes.innerHTML = ""; boxModalidades.innerHTML = ""; return; }
      if (!ev.pacotes.length) {
        boxPacotes.innerHTML = '<p class="text-muted mb-0">Nenhum pacote ativo vinculado a este evento. Cadastre um pacote primeiro.</p>';
      } else {
        if (ev.pacotes.length === 1 && !pacoteAtual) pacoteAtual = String(ev.pacotes[0].id);
        boxPacotes.innerHTML = '<div class="pacote-opcoes">' + ev.pacotes.map((p) => `
          <div class="pacote-opcao"><label>
            <input type="radio" name="${prefixo}pacote" value="${p.id}" ${String(p.id) === String(pacoteAtual) ? "checked" : ""} required>
            <div class="d-flex justify-content-between align-items-start gap-2">
              <span class="nome">${esc(p.nome)}</span><span class="valor">R$ ${esc(p.valor)}</span>
            </div>
            ${p.max ? `<div class="small mt-1"><i class="bi bi-info-circle"></i> Até ${p.max} modalidade(s)</div>` : ""}
            ${p.beneficios.length ? "<ul>" + p.beneficios.map((b) => `<li>${esc(b)}</li>`).join("") + "</ul>" : ""}
          </label></div>`).join("") + "</div>";
      }
      renderModalidades();
    }

    function renderModalidades() {
      const ev = eventoAtual();
      if (!ev) return;
      const pac = pacoteInfo();
      const permitidas = pac && pac.permitidas.length ? new Set(pac.permitidas.map(String)) : null;
      const lista = ev.modalidades.filter((m) => !permitidas || permitidas.has(String(m.id)));
      const sexo = sexoAtual();
      if (avisoSexo) avisoSexo.hidden = Boolean(sexo);
      // desmarca o que não vale para o sexo escolhido
      lista.forEach((m) => { if (!aceitaSexo(m, sexo)) selecionadas.delete(String(m.id)); });
      if (!lista.length) {
        boxModalidades.innerHTML = '<p class="text-muted mb-0">Nenhuma modalidade disponível para este evento/pacote.</p>';
      } else {
        boxModalidades.innerHTML = '<div class="grade-checks">' + lista.map((m) => {
          const ok = aceitaSexo(m, sexo);
          return `
          <div class="opcao-check"><label title="${esc(m.tipo)} · ${esc(m.naipe_txt)}">
            <input class="form-check-input" type="checkbox" name="${prefixo}modalidades" value="${m.id}"
              ${selecionadas.has(String(m.id)) ? "checked" : ""} ${ok ? "" : "disabled data-bloqueada"}>
            <span>${esc(m.nome)}</span>
            ${ok ? `<small>${esc(m.naipe_txt)}</small>` : `<small class="bloqueio">${bloqueio(m)}</small>`}
          </label></div>`;
        }).join("") + "</div>";
      }
      aplicarRegras();
    }

    function aplicarRegras() {
      const pac = pacoteInfo();
      const caixas = boxModalidades.querySelectorAll('input[type="checkbox"]');
      const marcadas = [...caixas].filter((c) => c.checked).length;
      const max = pac && pac.max ? pac.max : null;
      caixas.forEach((c) => (c.disabled = c.hasAttribute("data-bloqueada") || (max !== null && !c.checked && marcadas >= max)));
      if (regra) {
        regra.textContent = max ? `${marcadas} de ${max} modalidade(s) selecionada(s) — limite do pacote.`
                                : `${marcadas} modalidade(s) selecionada(s).`;
      }
    }
    render();
  }

  // ---------------------------------------------------------------- Pacote: modalidades permitidas por evento
  const formPacote = document.querySelector("[data-form-pacote]");
  if (formPacote) {
    const mapa = JSON.parse(document.getElementById("modalidades-por-evento").textContent);
    const sel = formPacote.querySelector('select[name="evento"]');
    const atualizar = () => {
      const ids = new Set((mapa[sel.value] || []).map(String));
      formPacote.querySelectorAll('input[name="modalidades_permitidas"]').forEach((c) => {
        const item = c.closest("div");
        const visivel = !sel.value || ids.has(c.value);
        item.hidden = !visivel;
        if (!visivel) c.checked = false;
      });
    };
    sel.addEventListener("change", atualizar);
    atualizar();
  }

  // ---------------------------------------------------------------- Envio automático de filtros
  document.querySelectorAll("[data-autoenvio]").forEach((form) =>
    form.querySelectorAll("select").forEach((s) => s.addEventListener("change", () => form.requestSubmit()))
  );
})();
