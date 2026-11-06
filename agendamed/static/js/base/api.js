/* AgendaMed — cliente da API (a conversa com o servidor).
 *
 * Toda chamada ao servidor passa pelo objeto `api` (get, post, put, patch, del), que
 * envia o token de acesso e transforma respostas de erro em ApiError.
 *
 * Os arquivos de js/ são carregados pelo index.html, em ordem, e compartilham as mesmas
 * variáveis globais: uma função declarada aqui pode ser usada nos arquivos seguintes.
 */
"use strict";

/**
 * Erro devolvido pela API: o status HTTP, a mensagem e, quando houver, os erros de cada
 * campo (`errors`).
 */
class ApiError extends Error {
  constructor(status, message, errors = []) {
    super(message);
    this.status = status;
    this.errors = errors;
  }
}

/** Nome com que o token de acesso fica guardado no navegador (localStorage). */
const TOKEN_KEY = "agendamed.token";

/**
 * Cliente da API. Uso: await api.get("/patients", {q: "ana"}),
 * api.post("/appointments", dados), api.del("/doctors/3")...
 * Erros viram ApiError; um 401 com sessão aberta encerra a sessão (session.expire).
 */
const api = {
  /** Token de acesso guardado no navegador (null se não houver ou se bloqueado). */
  get token() {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set token(value) {
    try {
      if (value) localStorage.setItem(TOKEN_KEY, value);
      else localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* armazenamento indisponível (ex.: navegação privada) */
    }
  },

  /**
   * Faz a chamada HTTP: envia o token, manda o corpo como JSON e devolve o JSON da
   * resposta. Respostas de erro viram ApiError.
   */
  async request(method, path, body) {
    const headers = { Accept: "application/json" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    const token = this.token;
    if (token) headers.Authorization = `Bearer ${token}`;

    let response;
    try {
      response = await fetch(path, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new ApiError(
        0,
        "Sem conexão com o servidor. Verifique se a API está rodando.",
      );
    }

    const data = await response.json().catch(() => null);
    if (!response.ok) {
      if (response.status === 401 && token && path !== "/auth/login")
        session.expire();
      throw new ApiError(
        response.status,
        data?.detail || "Erro inesperado no servidor.",
        data?.errors || [],
      );
    }
    return data ?? {}; // 204 (ex.: excluir) não tem corpo
  },

  /** GET com parâmetros na query string (os vazios são ignorados). */
  get(path, params) {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params || {})) {
      if (value !== undefined && value !== null && value !== "")
        query.set(key, value);
    }
    const qs = query.toString();
    return this.request("GET", qs ? `${path}?${qs}` : path);
  },

  /** POST com corpo JSON. */
  post(path, body = {}) {
    return this.request("POST", path, body);
  },

  /** PUT com corpo JSON. */
  put(path, body = {}) {
    return this.request("PUT", path, body);
  },

  /** PATCH com corpo JSON (só os campos que mudam). */
  patch(path, body = {}) {
    return this.request("PATCH", path, body);
  },

  /** DELETE. */
  del(path) {
    return this.request("DELETE", path);
  },
};
