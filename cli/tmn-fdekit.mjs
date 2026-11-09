#!/usr/bin/env node
// tmn-fdekit installer. Zero dependencies; Node 18+.
//
//   npx github:teamnebula-ai/tmn-fdekit list
//   npx github:teamnebula-ai/tmn-fdekit install [--target claude,codex,...|auto|all] [--project] [--link]
//   npx github:teamnebula-ai/tmn-fdekit hooks   [--target claude|codex] [--project] [--remove]   # hooks without the plugin system
//   npx github:teamnebula-ai/tmn-fdekit zip     [--out dist]      # one upload zip per skill (Claude.ai / Desktop)
//   npx github:teamnebula-ai/tmn-fdekit doctor
//   npx github:teamnebula-ai/tmn-fdekit uninstall [--target ...] [--project]
//
// Skills are copied, not linked, unless --link is given, so an npx cache cleanup can't
// break them. The scripts the skills call are copied once to ~/.tmn-fdekit/plugin and
// every installed SKILL.md points there.

import { cpSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, symlinkSync, writeFileSync, lstatSync, copyFileSync, realpathSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";

const PKG = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const HOME = process.env.TMN_FDEKIT_HOME_OVERRIDE || homedir();
const SHARED = process.env.TMN_FDEKIT_PLUGIN_DIR || join(HOME, ".tmn-fdekit", "plugin");
const MARK = ".tmn-fdekit-installed";
// Every skill is named tmn-<skill> in its own folder and frontmatter, so it installs under that
// name everywhere. Versions before 0.4 installed as tmn-fdekit-<skill>; install and uninstall
// remove those old folders (only ones this installer marked).
const LEGACY_PREFIX = "tmn-fdekit-";
function removeLegacy(base) {
  if (!existsSync(base)) return 0;
  let n = 0;
  for (const d of readdirSync(base)) {
    const p = join(base, d);
    if (d.startsWith(LEGACY_PREFIX) && (existsSync(join(p, MARK)) || isLink(p))) { rmSync(p, { recursive: true, force: true }); n++; }
  }
  return n;
}

// Where each agent reads Agent Skills (folders with SKILL.md). `detect` decides "auto".
export const TARGETS = {
  claude: {
    label: "Claude Code",
    user: () => join(process.env.CLAUDE_CONFIG_DIR || join(HOME, ".claude"), "skills"),
    project: (cwd) => join(cwd, ".claude", "skills"),
    detect: () => existsSync(process.env.CLAUDE_CONFIG_DIR || join(HOME, ".claude")),
  },
  codex: {
    label: "OpenAI Codex",
    user: () => join(HOME, ".agents", "skills"),
    project: (cwd) => join(cwd, ".agents", "skills"),
    detect: () => existsSync(process.env.CODEX_HOME || join(HOME, ".codex")),
  },
  cursor: {
    label: "Cursor",
    user: () => join(HOME, ".cursor", "skills"),
    project: (cwd) => join(cwd, ".cursor", "skills"),
    detect: () => existsSync(join(HOME, ".cursor")),
  },
  gemini: {
    label: "Gemini CLI",
    user: () => join(HOME, ".gemini", "skills"),
    project: (cwd) => join(cwd, ".gemini", "skills"),
    detect: () => existsSync(join(HOME, ".gemini")),
  },
  copilot: {
    label: "GitHub Copilot",
    user: () => join(HOME, ".copilot", "skills"),
    project: (cwd) => join(cwd, ".github", "skills"),
    detect: () => existsSync(join(HOME, ".copilot")),
  },
  devin: {
    label: "Windsurf / Devin Desktop",
    user: () => join(HOME, ".config", "devin", "skills"),
    project: (cwd) => join(cwd, ".devin", "skills"),
    detect: () => existsSync(join(HOME, ".config", "devin")) || existsSync(join(HOME, ".codeium")),
  },
  opencode: {
    label: "OpenCode",
    user: () => join(HOME, ".config", "opencode", "skills"),
    project: (cwd) => join(cwd, ".opencode", "skills"),
    detect: () => existsSync(join(HOME, ".config", "opencode")),
  },
  amp: {
    label: "Amp",
    user: () => join(HOME, ".config", "amp", "skills"),
    project: (cwd) => join(cwd, ".agents", "skills"),
    detect: () => existsSync(join(HOME, ".config", "amp")),
  },
  agents: {
    label: "Any agent reading ~/.agents/skills",
    user: () => join(HOME, ".agents", "skills"),
    project: (cwd) => join(cwd, ".agents", "skills"),
    detect: () => existsSync(join(HOME, ".agents")),
  },
};

function args(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith("--")) {
      const [k, v] = a.slice(2).split("=");
      out[k] = v ?? (argv[i + 1] && !argv[i + 1].startsWith("--") ? argv[++i] : true);
    } else out._.push(a);
  }
  return out;
}

export function skills() {
  const dir = join(PKG, "skills");
  return readdirSync(dir).filter((d) => existsSync(join(dir, d, "SKILL.md"))).sort().map((name) => {
    const text = readFileSync(join(dir, name, "SKILL.md"), "utf8");
    const fm = /^---\n([\s\S]*?)\n---/.exec(text)?.[1] ?? "";
    const desc = /^description:\s*(.*)$/m.exec(fm)?.[1]?.replace(/^['"]|['"]$/g, "") ?? "";
    return { name, description: desc, dir: join(dir, name) };
  });
}

const TIERS = {
  "tmn-staff-bar": 0,
  "tmn-verify": 1, "tmn-pr-review": 1, "tmn-ship-pr": 1, "tmn-respond": 1, "tmn-debug": 1, "tmn-harden-prod": 1,
  "tmn-write": 2, "tmn-slack": 2, "tmn-ui-design": 2, "tmn-docs-site": 2,
  "tmn-setup": 3, "tmn-trace": 3, "tmn-enforce": 3,
};

function pickTargets(opt) {
  const raw = opt.target && opt.target !== true ? String(opt.target) : "auto";
  if (raw === "all") return Object.keys(TARGETS);
  if (raw === "auto") {
    const found = Object.keys(TARGETS).filter((t) => t !== "agents" && TARGETS[t].detect());
    return found.length ? found : ["agents"];
  }
  const list = raw.split(",").map((s) => s.trim()).filter(Boolean);
  const bad = list.filter((t) => !TARGETS[t]);
  if (bad.length) fail(`unknown target: ${bad.join(", ")}. Known: ${Object.keys(TARGETS).join(", ")}, auto, all`);
  return list;
}

function fail(msg) {
  console.error(`tmn-fdekit: ${msg}`);
  process.exit(1);
}

function installShared() {
  mkdirSync(SHARED, { recursive: true });
  for (const d of ["scripts", "templates", "agents", "hooks"]) {
    rmSync(join(SHARED, d), { recursive: true, force: true });
    if (existsSync(join(PKG, d))) cpSync(join(PKG, d), join(SHARED, d), { recursive: true, filter: (s) => !s.includes("__pycache__") });
  }
  copyFileSync(join(PKG, "package.json"), join(SHARED, "package.json"));
  return SHARED;
}

function writeSkill(src, dst, link, name) {
  rmSync(dst, { recursive: true, force: true });
  if (link) {
    symlinkSync(src, dst, "dir");
    return;
  }
  cpSync(src, dst, { recursive: true, filter: (s) => !s.includes(`${join("", "evals")}`) && !s.endsWith(".bundle") });
  const md = join(dst, "SKILL.md");
  // Outside the Claude plugin system there is no ${CLAUDE_PLUGIN_ROOT}: point at the shared copy.
  writeFileSync(md, readFileSync(md, "utf8").replaceAll("${CLAUDE_PLUGIN_ROOT}", SHARED));
  writeFileSync(join(dst, MARK), `installed by tmn-fdekit from ${PKG}\n`);
}

function cmdInstall(opt) {
  const shared = installShared();
  const cwd = process.cwd();
  const list = skills();
  const done = new Set();
  for (const t of pickTargets(opt)) {
    const base = opt.project ? TARGETS[t].project(cwd) : TARGETS[t].user();
    if (done.has(base)) { console.log(`${TARGETS[t].label.padEnd(36)} same folder as above: ${base}`); continue; }
    done.add(base);
    mkdirSync(base, { recursive: true });
    const old = removeLegacy(base);
    if (old) console.log(`  removed ${old} skills installed under the old tmn-fdekit-<skill> names`);
    for (const s of list) {
      const dst = join(base, s.name);
      if (existsSync(dst) && !existsSync(join(dst, MARK)) && !isLink(dst) && !opt.force) {
        console.log(`  skip ${dst} (exists and was not installed by tmn-fdekit; --force to replace)`);
        continue;
      }
      writeSkill(s.dir, dst, opt.link, s.name);
    }
    console.log(`${TARGETS[t].label.padEnd(36)} ${list.length} skills -> ${base}`);
  }
  console.log(`scripts                              -> ${shared}/scripts`);
  console.log(`\nNext: ask your agent to "set up the kit" (the tmn-setup skill) to fit the limits, mode and rules to your team.`);
  console.log(`\nClaude Code users: the plugin gives you the hooks too. Run \`tmn-fdekit hooks\` to add them without it.`);
}

function isLink(p) {
  try { return lstatSync(p).isSymbolicLink(); } catch { return false; }
}

function cmdUninstall(opt) {
  const cwd = process.cwd();
  for (const t of opt.target ? pickTargets(opt) : Object.keys(TARGETS)) {
    const base = opt.project ? TARGETS[t].project(cwd) : TARGETS[t].user();
    let n = removeLegacy(base);
    for (const s of skills()) {
      const dst = join(base, s.name);
      if (existsSync(join(dst, MARK)) || isLink(dst)) { rmSync(dst, { recursive: true, force: true }); n++; }
    }
    if (n) console.log(`${TARGETS[t].label}: removed ${n} skills from ${base}`);
  }
}

export function hookConfig(scriptsDir) {
  const py = (s, extra = "") => `python3 "${join(scriptsDir, s)}"${extra}`;
  return {
    PreToolUse: [
      { matcher: "Bash", hooks: [{ type: "command", command: py("guard.py"), timeout: 30 }, { type: "command", command: py("comms.py"), timeout: 10 }], _ns: 1 },
      { matcher: "mcp__.*[Ss]lack.*", hooks: [{ type: "command", command: py("comms.py"), timeout: 10 }], _ns: 1 },
    ],
    PostToolUse: [{ matcher: "*", hooks: [{ type: "command", command: py("trace.py"), async: true }], _ns: 1 }],
    PostToolUseFailure: [{ matcher: "*", hooks: [{ type: "command", command: py("trace.py"), async: true }], _ns: 1 }],
    SessionStart: [{ hooks: [{ type: "command", command: py("config.py", " snapshot"), timeout: 10 }, { type: "command", command: py("trace.py"), async: true }], _ns: 1 }],
    SubagentStop: [{ hooks: [{ type: "command", command: py("trace.py"), async: true }], _ns: 1 }],
    Stop: [{ hooks: [{ type: "command", command: py("claims.py"), timeout: 10 }, { type: "command", command: py("receipt.py", " --hook"), async: true }], _ns: 1 }],
    SessionEnd: [{ hooks: [{ type: "command", command: py("receipt.py", " --hook") }], _ns: 1 }],
  };
}

function hooksFile(opt) {
  const target = opt.target && opt.target !== true ? String(opt.target) : "claude";
  if (target === "codex") return opt.project ? join(process.cwd(), ".codex", "hooks.json") : join(process.env.CODEX_HOME || join(HOME, ".codex"), "hooks.json");
  if (target !== "claude") fail(`hooks support --target claude or codex. For ${target}, use the enforce skill (CI and git hooks).`);
  return opt.project ? join(process.cwd(), ".claude", "settings.json") : join(process.env.CLAUDE_CONFIG_DIR || join(HOME, ".claude"), "settings.json");
}

function cmdHooks(opt) {
  const shared = installShared();
  const file = hooksFile(opt);
  mkdirSync(dirname(file), { recursive: true });
  let settings = {};
  if (existsSync(file)) {
    try { settings = JSON.parse(readFileSync(file, "utf8")); } catch { fail(`${file} is not valid JSON; fix it first`); }
    copyFileSync(file, `${file}.tmn-fdekit.bak`);
  }
  const ours = (h) => JSON.stringify(h).includes(join(".tmn-fdekit", "plugin")) || JSON.stringify(h).includes(SHARED);
  settings.hooks = settings.hooks || {};
  for (const [ev, groups] of Object.entries(hookConfig(join(shared, "scripts")))) {
    const keep = (settings.hooks[ev] || []).filter((g) => !ours(g));
    settings.hooks[ev] = [...keep, ...groups.map(({ _ns, ...g }) => g)];
  }
  if (opt.remove) for (const ev of Object.keys(settings.hooks)) settings.hooks[ev] = settings.hooks[ev].filter((g) => !ours(g));
  writeFileSync(file, JSON.stringify(settings, null, 2) + "\n");
  console.log(`${opt.remove ? "removed" : "wrote"} tmn-fdekit hooks in ${file} (backup: ${file}.tmn-fdekit.bak)`);
  if (!opt.remove && String(opt.target) === "codex") console.log("Codex asks you to approve each new hook: open /hooks in Codex and approve them.");
  else if (!opt.remove) console.log("Start a new Claude Code session for them to load. Don't combine with the plugin, or every hook runs twice.");
}

export function shortDescription(d, max = 200) {
  if (d.length <= max) return d;
  const head = d.split(" - ")[0].replace(/[.\s]+$/, "");
  const use = /\b(?:Use|Load this) (?:when|whenever|for|after|before|at)\b[^.]*/.exec(d)?.[0] ?? "";
  let out = use ? `${head}. ${use}` : head;
  if (out.length > max) out = out.slice(0, max - 1).replace(/[\s,;]+\S*$/, "") + "…";
  return out.replace(/:/g, " -");
}

function cmdZip(opt) {
  const out = resolve(opt.out && opt.out !== true ? opt.out : "dist");
  mkdirSync(out, { recursive: true });
  const stage = join(out, ".stage");
  for (const s of skills()) {
    rmSync(stage, { recursive: true, force: true });
    const dst = join(stage, s.name);
    cpSync(s.dir, dst, { recursive: true, filter: (p) => !p.includes(`${join("", "evals")}`) });
    // Claude.ai runs bundled scripts from the skill folder, so each zip carries its own copy.
    cpSync(join(PKG, "scripts"), join(dst, "scripts"), { recursive: true, filter: (p) => !p.includes("__pycache__") });
    const md = join(dst, "SKILL.md");
    let text = readFileSync(md, "utf8").replaceAll("${CLAUDE_PLUGIN_ROOT}/scripts", "scripts").replaceAll("${CLAUDE_PLUGIN_ROOT}", ".");
    // Claude.ai caps the description at 200 characters.
    text = text.replace(/^description:\s*(.*)$/m, (_, d) => `description: ${shortDescription(d.replace(/^['"]|['"]$/g, ""))}`);
    writeFileSync(md, text);
    const zip = join(out, `${s.name}.zip`);
    rmSync(zip, { force: true });
    execFileSync("python3", ["-c", "import shutil,sys; shutil.make_archive(sys.argv[1][:-4], 'zip', sys.argv[2], sys.argv[3])", zip, stage, s.name]);
    console.log(`${s.name.padEnd(20)} -> ${zip}`);
  }
  rmSync(stage, { recursive: true, force: true });
}

function cmdDoctor() {
  const has = (cmd, a = ["--version"]) => { try { return execFileSync(cmd, a, { stdio: ["ignore", "pipe", "ignore"] }).toString().split("\n")[0].trim(); } catch { return null; } };
  const rows = [
    ["python3", has("python3"), "required: every hook and script"],
    ["git", has("git"), "required"],
    ["gh", has("gh"), "needed for PR checks, review and merge guard"],
    ["docker", has("docker"), "optional: stack.sh with compose projects"],
    ["shellcheck", has("shellcheck"), "optional: contributors only"],
  ];
  for (const [n, v, why] of rows) console.log(`${v ? "ok  " : "MISS"} ${n.padEnd(11)} ${v ?? ""}${v ? "" : "  <- " + why}`);
  console.log("");
  for (const [t, def] of Object.entries(TARGETS)) {
    const dir = def.user();
    const n = skills().filter((s) => existsSync(join(dir, s.name))).length;
    console.log(`${def.label.padEnd(36)} ${n ? `${n} skills in ${dir}` : "not installed"}`);
  }
  console.log(`shared scripts                       ${existsSync(join(SHARED, "scripts")) ? SHARED : "not installed"}`);
}

function cmdList() {
  const byTier = {};
  for (const s of skills()) (byTier[TIERS[s.name] ?? 9] ||= []).push(s);
  const names = ["always", "the work", "the craft", "setup"];
  for (const t of Object.keys(byTier).sort()) {
    console.log(`\nTier ${t}: ${names[t] ?? "other"}`);
    for (const s of byTier[t]) console.log(`  ${s.name.padEnd(10)} ${s.description.split(" - ")[0].slice(0, 110)}`);
  }
}

const HELP = readFileSync(fileURLToPath(import.meta.url), "utf8").split("\n").slice(1, 14).map((l) => l.replace(/^\/\/ ?/, "")).join("\n");

export function main(argv = process.argv.slice(2)) {
  const opt = args(argv);
  const cmd = opt._[0];
  if (cmd === "list") return cmdList();
  if (cmd === "install") return cmdInstall(opt);
  if (cmd === "uninstall") return cmdUninstall(opt);
  if (cmd === "hooks") return cmdHooks(opt);
  if (cmd === "zip") return cmdZip(opt);
  if (cmd === "doctor") return cmdDoctor();
  console.log(HELP);
  if (cmd && cmd !== "help" && !opt.help) process.exitCode = 2;
}

// npx starts us through a node_modules/.bin symlink, so compare real paths.
const self = realpathSync(fileURLToPath(import.meta.url));
if (process.argv[1] && (() => { try { return realpathSync(process.argv[1]) === self; } catch { return false; } })()) main();
