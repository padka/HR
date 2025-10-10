#!/usr/bin/env node

import { readdirSync, statSync } from "node:fs";
import { resolve, extname, basename, join } from "node:path";

const ROOTS = [
  resolve("backend/apps/admin_ui/static/css"),
  resolve("backend/apps/admin_ui/static/js"),
];

const ISSUE_ALLOWLIST = new Set([
  // Temporary duplicates kept until the UI core unification.
  "liquid-dashboard 2.css",
  "dashboard-calendar 2.js",
  "city-selector 2.js",
  "form-dirty-guard 2.js",
]);

const issues = [];

function walk(dir) {
  for (const entry of readdirSync(dir)) {
    const absolute = join(dir, entry);
    const stats = statSync(absolute);
    if (stats.isDirectory()) {
      walk(absolute);
    } else {
      handleFile(entry, absolute);
    }
  }
}

const seen = new Map();

function normalise(name) {
  return name
    .replace(/\s+\d+(?=\.[^.]+$)/, "")
    .replace(/\s+/g, "-")
    .toLowerCase();
}

function handleFile(filename, absolute) {
  if (![".css", ".js"].includes(extname(filename))) {
    return;
  }

  if (ISSUE_ALLOWLIST.has(filename)) {
    console.warn(`WARN static lint: ${filename} is allow-listed duplicate`);
    return;
  }

  if (filename.includes(" 2.")) {
    issues.push({
      type: "duplicate-name",
      message: `${filename} looks like a manual copy (" 2" suffix)`,
      file: absolute,
    });
  }

  const key = `${extname(filename)}::${normalise(basename(filename, extname(filename)))}`;
  if (seen.has(key)) {
    issues.push({
      type: "duplicate-slug",
      message: `${filename} shares slug with ${basename(seen.get(key))}`,
      file: absolute,
    });
  } else {
    seen.set(key, absolute);
  }
}

for (const root of ROOTS) {
  walk(root);
}

if (issues.length) {
  console.warn("static lint warnings:");
  for (const issue of issues) {
    console.warn(`- [${issue.type}] ${issue.message} → ${issue.file}`);
  }
  console.warn("Set STRICT_STATIC_LINT=1 to treat warnings as errors.");
  if (process.env.STRICT_STATIC_LINT === "1") {
    process.exitCode = 1;
  }
} else {
  console.log("static lint: no duplicate CSS/JS slugs detected");
}
