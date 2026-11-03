/**
 * Wrapper seguro do localStorage.
 * Em janela anônima ou com armazenamento bloqueado, o acesso pode lançar
 * exceção; nesse caso o app continua funcionando, só sem persistência.
 */
export const storage = {
  get(key, fallback = null) {
    try {
      const raw = localStorage.getItem(key);
      return raw === null ? fallback : JSON.parse(raw);
    } catch {
      return fallback;
    }
  },

  set(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
      return true;
    } catch {
      return false;
    }
  },

  remove(key) {
    try {
      localStorage.removeItem(key);
    } catch {
      /* ignora */
    }
  },
};
