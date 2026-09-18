/**
 * Unified wallet connector — EIP-6963 injected + WalletConnect v2.
 * Keys stay in the wallet; this API only serves connect-config.
 */

const WC_MODULE = "https://esm.sh/@walletconnect/ethereum-provider@2.17.3";

export class DexWallet {
  constructor(apiBase) {
    this.apiBase = apiBase;
    this.config = null;
    this.provider = null;
    this.trader = null;
    this.connector = null;
    this.wcProvider = null;
    this.injected = new Map();
    this._bound = { accounts: null, chain: null, disconnect: null };
    this._onAccounts = [];
    this._onChain = [];
    this._onDisconnect = [];
  }

  onAccounts(fn) { this._onAccounts.push(fn); }
  onChain(fn) { this._onChain.push(fn); }
  onDisconnect(fn) { this._onDisconnect.push(fn); }

  async loadConfig() {
    const r = await fetch(`${this.apiBase}/v1/dex/wallet/connect-config`);
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || r.statusText);
    this.config = j;
    return j;
  }

  get network() {
    return this.config?.network;
  }

  discoverInjected(timeoutMs = 300) {
    this.injected.clear();
    const onAnnounce = (event) => {
      const { info, provider } = event.detail || {};
      if (!info?.uuid || !provider) return;
      this.injected.set(info.uuid, { info, provider });
    };
    window.addEventListener("eip6963:announceProvider", onAnnounce);
    window.dispatchEvent(new Event("eip6963:requestProvider"));
    return new Promise((resolve) => {
      setTimeout(() => {
        window.removeEventListener("eip6963:announceProvider", onAnnounce);
        if (!this.injected.size && window.ethereum) {
          this.injected.set("legacy", {
            info: { uuid: "legacy", name: "Browser wallet", icon: "", rdns: "eip1193.legacy" },
            provider: window.ethereum,
          });
        }
        resolve([...this.injected.values()]);
      }, timeoutMs);
    });
  }

  listConnectors() {
    const out = [];
    for (const [uuid, row] of this.injected.entries()) {
      out.push({
        kind: "injected",
        id: uuid,
        name: row.info.name || "Injected wallet",
        icon: row.info.icon || "",
        rdns: row.info.rdns || "",
      });
    }
    const wc = this.config?.connectors?.walletconnect;
    if (wc?.enabled && wc.project_id) {
      out.push({ kind: "walletconnect", id: "walletconnect", name: "WalletConnect", icon: "" });
    }
    return out;
  }

  async ensureGalleonChain() {
    if (!this.provider) throw new Error("wallet not connected");
    const net = this.network;
    if (!net) throw new Error("network config not loaded");
    const chainId = await this.provider.request({ method: "eth_chainId" });
    if (chainId.toLowerCase() === net.chainId.toLowerCase()) return;
    try {
      await this.provider.request({
        method: "wallet_switchEthereumChain",
        params: [{ chainId: net.chainId }],
      });
    } catch (e) {
      if (e.code === 4902) {
        await this.provider.request({ method: "wallet_addEthereumChain", params: [net] });
      } else {
        throw e;
      }
    }
  }

  _bindProvider() {
    if (!this.provider) return;
    this._unbindProvider();
    this._bound.accounts = (accs) => {
      this.trader = accs?.[0] || null;
      if (!this.trader) this._emitDisconnect();
      else this._onAccounts.forEach((fn) => fn(this.trader));
    };
    this._bound.chain = () => {
      this.ensureGalleonChain().catch(() => {});
      this._onChain.forEach((fn) => fn());
    };
    this._bound.disconnect = () => this._emitDisconnect();
    this.provider.on?.("accountsChanged", this._bound.accounts);
    this.provider.on?.("chainChanged", this._bound.chain);
    this.provider.on?.("disconnect", this._bound.disconnect);
  }

  _unbindProvider() {
    if (!this.provider) return;
    if (this._bound.accounts) this.provider.removeListener?.("accountsChanged", this._bound.accounts);
    if (this._bound.chain) this.provider.removeListener?.("chainChanged", this._bound.chain);
    if (this._bound.disconnect) this.provider.removeListener?.("disconnect", this._bound.disconnect);
    this._bound = { accounts: null, chain: null, disconnect: null };
  }

  _emitDisconnect() {
    this.trader = null;
    this.provider = null;
    this.connector = null;
    this._onDisconnect.forEach((fn) => fn());
  }

  async connectInjected(uuid) {
    const row = this.injected.get(uuid);
    if (!row?.provider) throw new Error("wallet not found — refresh and try again");
    const accounts = await row.provider.request({ method: "eth_requestAccounts" });
    this.wcProvider = null;
    this.provider = row.provider;
    this.trader = accounts[0];
    this.connector = { kind: "injected", id: uuid, label: row.info.name || "Injected wallet" };
    this._bindProvider();
    await this.ensureGalleonChain();
    return this.trader;
  }

  async connectWalletConnect() {
    const wc = this.config?.connectors?.walletconnect;
    if (!wc?.enabled || !wc.project_id) {
      throw new Error(wc?.hint || "WalletConnect not configured (WALLETCONNECT_PROJECT_ID)");
    }
    const chainId = this.network.chainIdDecimal;
    const { EthereumProvider } = await import(WC_MODULE);
    const provider = await EthereumProvider.init({
      projectId: wc.project_id,
      chains: [chainId],
      optionalChains: [chainId],
      showQrModal: true,
      rpcMap: { [chainId]: this.network.rpcUrls[0] },
      methods: this.config.sign_methods || ["eth_sendTransaction"],
      metadata: this.config.metadata,
    });
    this._unbindProvider();
    if (this.wcProvider && this.wcProvider !== provider) {
      try { await this.wcProvider.disconnect(); } catch (_) { /* stale */ }
    }
    this.wcProvider = provider;
    this.provider = provider;
    const accounts = await provider.enable();
    this.trader = accounts[0];
    this.connector = { kind: "walletconnect", id: "walletconnect", label: "WalletConnect" };
    this._bindProvider();
    await this.ensureGalleonChain();
    return this.trader;
  }

  async connect(connector) {
    if (!this.config) await this.loadConfig();
    if (connector.kind === "walletconnect") return this.connectWalletConnect();
    if (connector.kind === "injected") return this.connectInjected(connector.id);
    throw new Error("unknown connector: " + connector.kind);
  }

  async disconnect() {
    this._unbindProvider();
    if (this.wcProvider) {
      try { await this.wcProvider.disconnect(); } catch (_) { /* ignore */ }
      this.wcProvider = null;
    }
    this.provider = null;
    this.trader = null;
    this.connector = null;
    this._onDisconnect.forEach((fn) => fn());
  }

  async getBalance() {
    if (!this.provider || !this.trader) throw new Error("wallet not connected");
    const hex = await this.provider.request({
      method: "eth_getBalance",
      params: [this.trader, "latest"],
    });
    return BigInt(hex);
  }
}
