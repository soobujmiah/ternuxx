# Optional AI tool setup

The installer offers AI **setup recipe/prerequisite** entries in the optional apps
lists. These install only the displayed package-manager prerequisites. They do not
run a downloaded script, install an agent, collect credentials or sign in. The plan
and menu labels distinguish this from ordinary curated app installation. Agents
have separate publishers, release channels and login requirements; their workload
support in PRoot needs device acceptance.

| Tool | Native Termux suggestion | Managed Debian/Ubuntu suggestion |
|---|---|---|
| Codex | Owner-used community Android ARM64 build, `@mmmbuto/codex-cli-termux@next`; Node.js LTS prerequisite | Upstream Linux Codex; Node.js/npm prerequisites |
| Hermes | Official signed Termux canary channel; experimental, current upstream broken-package notice | Upstream Linux installation; curl/Git/CA/libatomic prerequisites |
| Claude Code | Not offered; use a managed guest | Official Linux installation; curl/CA prerequisites |

## Codex

The owner reports using this Native command successfully:

```sh
pkg install nodejs-lts -y
npm install -g @mmmbuto/codex-cli-termux@next
codex --version
codex login
```

This is a community Android build, not an OpenAI-published Android package. `next`
is a mutable npm channel, so this recipe is not an exact-version managed transaction.
Check the [package publisher](https://www.npmjs.com/package/@mmmbuto/codex-cli-termux)
and [maintainer's install guide](https://github.com/DioNanos/codex-termux/blob/main/docs/install.md).
Ternuxx preserves your existing agent installation and configuration.

Inside the selected Debian/Ubuntu guest, after the selected Node.js/npm prerequisites
are installed:

```sh
npm install -g @openai/codex
codex --version
codex
```

Use the [OpenAI Codex repository](https://github.com/openai/codex#quickstart) for
current install/login instructions. Keep guest commands inside the guest terminal;
a Linux binary is not the Native Android binary.

## Hermes

The owner supplied the [official Termux guide](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/getting-started/termux.md).
It defines signed `stable` and `canary` APT channels. As checked on 2026-10-26, it
also states that the Termux package is currently broken. Ternuxx therefore offers
a clearly experimental guide rather than silently enrolling an external repository.

For an explicit manual canary test, follow that guide's key download/fingerprint
verification and substitute `canary` / `hermes-canary` for its stable channel and
suite. The documented key fingerprint is
`C572B5FDD1A29CCFA9A912B6840B0848E139156D`; a mismatch must stop setup.
No key, repository, gateway or background service is enabled by choosing the menu
entry. The selected curl/gnupg prerequisites support reviewing that process.

Inside a managed Linux guest, review the [upstream Linux install guide](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/getting-started/installation.md).
Its current CLI recipe is:

```sh
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
```

That installer owns its runtimes/dependencies and may offer additional setup. Run
it explicitly inside the intended guest. PRoot is not listed as a separately
qualified upstream target; verify actual operation before relying on it.

## Claude Code (PRoot only)

Open the intended Debian/Ubuntu guest terminal and review the
[Anthropic setup guide](https://code.claude.com/docs/en/setup). Its current Linux
recipe is:

```sh
curl -fsSL https://claude.ai/install.sh | bash
claude --version
claude
```

The upstream guide lists Debian/Ubuntu and ARM64. That does not establish Android
PRoot workload or sandbox acceptance; test those on the device. Ternuxx does not
start an agent or automatically complete a provider/account login.
