// Run: node --test tests/cli.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readFileSync, existsSync, writeFileSync, readdirSync, rmSync, symlinkSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve, dirname } from "node:path";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const CLI = join(ROOT, "cli", "tmn-fdekit.mjs");

function sandbox() {
  const home = mkdtempSync(join(tmpdir(), "ns-cli-"));
  const env = { ...process.env, TMN_FDEKIT_HOME_OVERRIDE: home, CLAUDE_CONFIG_DIR: join(home, ".claude"), CODEX_HOME: join(home, ".codex") };
  const run = (...a) => execFileSync("node", [CLI, ...a], { env, cwd: home, encoding: "utf8" });
  return { home, env, run, done: () => rmSync(home, { recursive: true, force: true }) };
}

const SKILLS = readdirSync(join(ROOT, "skills")).filter((d) => existsSync(join(ROOT, "skills", d, "SKILL.md")));

test("install copies every skill and points scripts at the shared copy", () => {
  const s = sandbox();
  try {
    s.run("install", "--target", "claude,codex");
    for (const base of [join(s.home, ".claude", "skills"), join(s.home, ".agents", "skills")]) {
      for (const name of SKILLS) assert.ok(existsSync(join(base, name, "SKILL.md")), `${base}/${name}`);
      const review = readFileSync(join(base, "tmn-pr-review", "SKILL.md"), "utf8");
      assert.match(review, /^name: tmn-pr-review$/m, "name matches the installed folder");
      assert.match(review, /^description: \(tmn\) /m);
      assert.ok(!review.includes("${CLAUDE_PLUGIN_ROOT}"), "placeholder must be rewritten");
      assert.ok(review.includes(join(s.home, ".tmn-fdekit", "plugin", "scripts", "pr_check.py")));
      assert.ok(!existsSync(join(base, "tmn-pr-review", "evals")), "evals are not installed");
    }
    assert.ok(existsSync(join(s.home, ".tmn-fdekit", "plugin", "scripts", "guard.py")));
  } finally { s.done(); }
});

test("install never overwrites a skill it did not install, unless forced", () => {
  const s = sandbox();
  try {
    const mine = join(s.home, ".claude", "skills", "tmn-pr-review");
    mkdirSync(mine, { recursive: true });
    writeFileSync(join(mine, "SKILL.md"), "my own review skill");
    const out = s.run("install", "--target", "claude");
    assert.match(out, /skip .*review/);
    assert.equal(readFileSync(join(mine, "SKILL.md"), "utf8"), "my own review skill");
    s.run("install", "--target", "claude", "--force");
    assert.notEqual(readFileSync(join(mine, "SKILL.md"), "utf8"), "my own review skill");
  } finally { s.done(); }
});

test("every skill is named tmn-<folder> and its description starts with (tmn)", () => {
  for (const name of SKILLS) {
    assert.match(name, /^tmn-/, name);
    const md = readFileSync(join(ROOT, "skills", name, "SKILL.md"), "utf8");
    assert.match(md, new RegExp(`^name: ${name}$`, "m"), name);
    assert.match(md, /^description: \(tmn\) \S/m, name);
  }
});

test("the 200-character Claude.ai description keeps when-to-use wording for every skill", async () => {
  const { shortDescription } = await import(CLI);
  for (const name of SKILLS) {
    const md = readFileSync(join(ROOT, "skills", name, "SKILL.md"), "utf8");
    const short = shortDescription(/^description:\s*(.*)$/m.exec(md)[1]);
    assert.ok(short.length <= 200, name);
    assert.match(short, /^\(tmn\) /, name);
    assert.match(short, /\b(Use|Load this) (when|whenever|for|after|before|at)\b/, `${name}: ${short}`);
  }
});

test("install removes skills left under the old tmn-fdekit-<skill> names, and nothing else", () => {
  const s = sandbox();
  try {
    const base = join(s.home, ".claude", "skills");
    const old = join(base, "tmn-fdekit-review");
    const theirs = join(base, "tmn-fdekit-notes");
    for (const d of [old, theirs]) mkdirSync(d, { recursive: true });
    writeFileSync(join(old, ".tmn-fdekit-installed"), "old\n");
    writeFileSync(join(theirs, "SKILL.md"), "not ours");
    s.run("install", "--target", "claude");
    assert.ok(!existsSync(old), "old marked install removed");
    assert.ok(existsSync(join(theirs, "SKILL.md")), "unmarked folder kept");
    assert.ok(existsSync(join(base, "tmn-pr-review", "SKILL.md")));
  } finally { s.done(); }
});

test("project install and uninstall", () => {
  const s = sandbox();
  try {
    s.run("install", "--target", "cursor", "--project");
    assert.ok(existsSync(join(s.home, ".cursor", "skills", "tmn-verify", "SKILL.md")));
    s.run("uninstall", "--target", "cursor", "--project");
    assert.ok(!existsSync(join(s.home, ".cursor", "skills", "tmn-verify")));
  } finally { s.done(); }
});

test("hooks merge into settings, keep the user's hooks, and stay idempotent", () => {
  const s = sandbox();
  try {
    const file = join(s.home, ".claude", "settings.json");
    mkdirSync(dirname(file), { recursive: true });
    writeFileSync(file, JSON.stringify({ model: "x", hooks: { Stop: [{ hooks: [{ type: "command", command: "say done" }] }] } }));
    s.run("hooks");
    s.run("hooks");
    const st = JSON.parse(readFileSync(file, "utf8"));
    assert.equal(st.model, "x");
    assert.equal(st.hooks.Stop.length, 2, "user's Stop hook + one tmn-fdekit group");
    assert.equal(st.hooks.PreToolUse.length, 2);
    assert.ok(JSON.stringify(st.hooks.PreToolUse).includes("guard.py"));
    assert.ok(existsSync(file + ".tmn-fdekit.bak"));
    s.run("hooks", "--remove");
    const after = JSON.parse(readFileSync(file, "utf8"));
    assert.equal(after.hooks.Stop.length, 1);
    assert.ok(!JSON.stringify(after).includes("guard.py"));
  } finally { s.done(); }
});

test("codex hooks go to hooks.json in Claude's shape", () => {
  const s = sandbox();
  try {
    const out = s.run("hooks", "--target", "codex");
    const h = JSON.parse(readFileSync(join(s.home, ".codex", "hooks.json"), "utf8"));
    assert.ok(JSON.stringify(h.hooks.PreToolUse).includes("guard.py"));
    assert.match(out, /approve/);
    assert.throws(() => s.run("hooks", "--target", "cursor"), /enforce skill/);
  } finally { s.done(); }
});

test("zip builds one self-contained upload per skill", () => {
  const s = sandbox();
  try {
    s.run("zip", "--out", join(s.home, "dist"));
    for (const name of SKILLS) assert.ok(existsSync(join(s.home, "dist", `${name}.zip`)), name);
    const listing = execFileSync("python3", ["-c", "import zipfile,sys;print('\\n'.join(zipfile.ZipFile(sys.argv[1]).namelist()))", join(s.home, "dist", "tmn-pr-review.zip")], { encoding: "utf8" });
    assert.match(listing, /^tmn-pr-review\/SKILL\.md$/m);
    assert.match(listing, /^tmn-pr-review\/scripts\/gate\.py$/m);
    assert.doesNotMatch(listing, /evals\//);
    const md = execFileSync("python3", ["-c", "import zipfile,sys;print(zipfile.ZipFile(sys.argv[1]).read('tmn-pr-review/SKILL.md').decode())", join(s.home, "dist", "tmn-pr-review.zip")], { encoding: "utf8" });
    assert.ok(!md.includes("CLAUDE_PLUGIN_ROOT"));
    assert.match(md, /^name: tmn-pr-review$/m);
    const desc = /^description: (.*)$/m.exec(md)[1];
    assert.ok(desc.length <= 200, `claude.ai caps descriptions at 200, got ${desc.length}`);
    assert.match(desc, /review/i);
  } finally { s.done(); }
});

test("targets sharing a folder are installed once", () => {
  const s = sandbox();
  try {
    const out = s.run("install", "--target", "codex,agents");
    assert.match(out, /same folder as above/);
  } finally { s.done(); }
});

test("runs when started through a bin symlink, as npx does", () => {
  const s = sandbox();
  try {
    const bin = join(s.home, "tmn-fdekit");
    symlinkSync(CLI, bin);
    const out = execFileSync("node", [bin, "list"], { env: s.env, encoding: "utf8" });
    assert.match(out, /Tier 1/);
  } finally { s.done(); }
});

test("unknown target fails loudly", () => {
  const s = sandbox();
  try {
    assert.throws(() => s.run("install", "--target", "nope"), /unknown target/);
  } finally { s.done(); }
});
